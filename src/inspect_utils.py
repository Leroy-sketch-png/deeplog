"""Reusable helpers for Phase A: safe structural inspection of a large CSV.

All functions here operate on small, bounded amounts of data (a binary
prefix and/or the first N logical CSV records) and never load the full
file into memory.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Number of raw bytes read to sniff BOM / encoding / newline / delimiter.
PREFIX_BYTES = 65536

# Known BOM signatures, longest first so we do not match a shorter BOM that
# is a prefix of a longer one.
_BOM_SIGNATURES: List[Tuple[bytes, str]] = [
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
]


@dataclass
class BinaryPrefixReport:
    bytes_read: int
    bom_detected: Optional[str]
    probable_encoding: str
    encoding_confidence_note: str
    newline_convention: str
    probable_delimiter: str
    delimiter_detection_method: str
    quoting_observed: bool
    quote_char_guess: str


@dataclass
class ParsedSampleReport:
    num_columns: int
    column_names: List[str]
    duplicate_column_names: List[str]
    blank_column_names: List[int]
    rows_parsed: int
    row_width_consistent: bool
    row_widths: List[int]
    malformed_rows: List[int] = field(default_factory=list)


def read_binary_prefix(path: Path, num_bytes: int = PREFIX_BYTES) -> bytes:
    """Read only the first ``num_bytes`` bytes of the file. Read-only, safe."""
    with open(path, "rb") as fh:
        return fh.read(num_bytes)


def detect_bom(prefix: bytes) -> Optional[str]:
    for signature, name in _BOM_SIGNATURES:
        if prefix.startswith(signature):
            return name
    return None


def guess_encoding(prefix: bytes) -> Tuple[str, str]:
    """Best-effort encoding guess using only the standard library.

    Returns (encoding_name, confidence_note). This is a heuristic, not a
    guarantee -- documented explicitly in the confidence note.
    """
    bom = detect_bom(prefix)
    if bom:
        return bom, "Detected via byte-order mark (high confidence)."

    # Try strict UTF-8 decode first.
    try:
        prefix.decode("utf-8")
        return "utf-8", "Strict UTF-8 decode succeeded on prefix (no BOM found)."
    except UnicodeDecodeError:
        pass

    # Fall back to latin-1 which never fails to decode (every byte is valid),
    # but flag this clearly as a low-confidence fallback.
    return (
        "latin-1 (fallback)",
        "UTF-8 decode failed on prefix; falling back to latin-1, which "
        "always succeeds but may misinterpret multi-byte characters. "
        "Manual confirmation recommended.",
    )


def detect_newline_convention(prefix: bytes) -> str:
    has_crlf = b"\r\n" in prefix
    has_lone_lf = b"\n" in prefix.replace(b"\r\n", b"")
    has_lone_cr = b"\r" in prefix.replace(b"\r\n", b"")
    if has_crlf and not has_lone_lf and not has_lone_cr:
        return "CRLF"
    if has_lone_lf and not has_crlf and not has_lone_cr:
        return "LF"
    if has_lone_cr and not has_crlf and not has_lone_lf:
        return "CR"
    if has_crlf and has_lone_lf:
        return "mixed (CRLF and LF both observed)"
    return "undetermined"


def detect_delimiter_and_quoting(
    text_prefix: str,
) -> Tuple[str, str, bool, str]:
    """Use csv.Sniffer on a decoded text prefix to guess delimiter/quoting.

    Returns (delimiter, method_note, quoting_observed, quote_char_guess).
    Falls back to comma if sniffing fails, with an explicit note.
    """
    sample = text_prefix[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        quoting_observed = dialect.quotechar in sample
        return (
            dialect.delimiter,
            "Detected via csv.Sniffer on decoded text prefix.",
            quoting_observed,
            dialect.quotechar,
        )
    except csv.Error as exc:
        logger.warning("csv.Sniffer failed to detect dialect: %s", exc)
        return (
            ",",
            f"csv.Sniffer failed ({exc}); defaulted to comma. "
            "Manual confirmation recommended.",
            '"' in sample,
            '"',
        )


def build_binary_prefix_report(path: Path) -> Tuple[BinaryPrefixReport, str, str]:
    """Produce the BinaryPrefixReport plus the decoded text and encoding used."""
    prefix = read_binary_prefix(path)
    bom = detect_bom(prefix)
    encoding, confidence_note = guess_encoding(prefix)

    decode_encoding = encoding.replace(" (fallback)", "")
    try:
        text_prefix = prefix.decode(decode_encoding, errors="replace")
    except LookupError:
        decode_encoding = "latin-1"
        text_prefix = prefix.decode(decode_encoding, errors="replace")

    newline_convention = detect_newline_convention(prefix)
    delimiter, delim_method, quoting_observed, quote_char = detect_delimiter_and_quoting(
        text_prefix
    )

    report = BinaryPrefixReport(
        bytes_read=len(prefix),
        bom_detected=bom,
        probable_encoding=encoding,
        encoding_confidence_note=confidence_note,
        newline_convention=newline_convention,
        probable_delimiter=delimiter,
        delimiter_detection_method=delim_method,
        quoting_observed=quoting_observed,
        quote_char_guess=quote_char,
    )
    return report, text_prefix, decode_encoding


def parse_first_n_records(
    path: Path,
    encoding: str,
    delimiter: str,
    quote_char: str,
    n: int = 10,
) -> Tuple[ParsedSampleReport, List[Dict[str, str]], List[str]]:
    """Parse the header + first n logical records with csv.DictReader.

    Returns (report, redaction-pending raw rows as dicts, error_lines).
    The rows returned here are RAW (not redacted) and must be redacted by
    the caller before saving to disk.
    """
    errors: List[str] = []
    rows: List[Dict[str, str]] = []
    row_widths: List[int] = []
    malformed_rows: List[int] = []

    with open(path, "r", encoding=encoding, errors="replace", newline="") as fh:
        reader = csv.reader(fh, delimiter=delimiter, quotechar=quote_char)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("File appears to be empty; no header row found.")

        num_columns = len(header)
        blank_column_names = [i for i, c in enumerate(header) if not c.strip()]
        seen: Dict[str, int] = {}
        duplicates: List[str] = []
        for c in header:
            seen[c] = seen.get(c, 0) + 1
        duplicates = [c for c, count in seen.items() if count > 1]

        for i, raw_row in enumerate(reader):
            if i >= n:
                break
            row_widths.append(len(raw_row))
            if len(raw_row) != num_columns:
                malformed_rows.append(i)
                errors.append(
                    f"Record {i}: expected {num_columns} fields, got {len(raw_row)}."
                )
            # Build a dict even for malformed rows, padding/truncating so we
            # can still show a redacted example; explicitly flagged above.
            row_dict = {}
            for idx, col in enumerate(header):
                row_dict[col if col else f"_blank_col_{idx}"] = (
                    raw_row[idx] if idx < len(raw_row) else None
                )
            rows.append(row_dict)

    row_width_consistent = len(set(row_widths)) <= 1 if row_widths else True

    report = ParsedSampleReport(
        num_columns=num_columns,
        column_names=header,
        duplicate_column_names=duplicates,
        blank_column_names=blank_column_names,
        rows_parsed=len(rows),
        row_width_consistent=row_width_consistent,
        row_widths=row_widths,
        malformed_rows=malformed_rows,
    )
    return report, rows, errors
