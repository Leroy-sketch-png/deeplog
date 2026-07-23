"""Phase A: Safe structural inspection of a large local security-log CSV.

This script performs a bounded, read-only inspection of the source CSV:
  * Confirms the file exists and records size / modification time.
  * Sniffs a small binary prefix for BOM, encoding, newline convention,
    delimiter, and quoting behavior.
  * Parses ONLY the header and first 10 logical CSV records using the
    standard-library ``csv`` module (a real CSV parser, not ``split(",")``).
  * Writes redacted summaries/samples to ``artifacts/``.

It never loads the whole file into memory and never modifies the source
file. Run with:

    python 01_inspect_security_log.py

Configuration constants (encoding overrides, sample size, etc.) are declared
at the top of ``main`` and are echoed into the summary JSON for
reproducibility.
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from src.inspect_utils import (  # noqa: E402
    build_binary_prefix_report,
    parse_first_n_records,
)
from src.redact import redact_row  # noqa: E402

SOURCE_FILENAME = "logs_output_20260713_180521.csv"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
NUM_SAMPLE_RECORDS = 10

SUMMARY_PATH = ARTIFACTS_DIR / "inspection_summary.json"
SAMPLE_CSV_PATH = ARTIFACTS_DIR / "first_10_rows_redacted.csv"
NOTES_PATH = ARTIFACTS_DIR / "inspection_notes.md"
ERRORS_LOG_PATH = ARTIFACTS_DIR / "inspection_errors.log"

logger = logging.getLogger("inspect_security_log")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def append_error_log(message: str) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(ERRORS_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(message.rstrip("\n") + "\n")


def main() -> int:
    setup_logging()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    # Start each run with a clean errors log so it reflects only this run.
    ERRORS_LOG_PATH.write_text("", encoding="utf-8")

    source_path = REPO_ROOT / SOURCE_FILENAME

    # ------------------------------------------------------------------
    # 1. Confirm file exists
    # ------------------------------------------------------------------
    if not source_path.exists():
        msg = f"FATAL: source file not found: {source_path}"
        logger.error(msg)
        append_error_log(msg)
        return 1

    try:
        stat = source_path.stat()
    except OSError as exc:
        msg = f"FATAL: could not stat source file: {exc}"
        logger.error(msg)
        append_error_log(msg)
        return 1

    file_size_bytes = stat.st_size
    file_size_gib = file_size_bytes / (1024 ** 3)
    modification_time_iso = None
    try:
        import datetime

        modification_time_iso = datetime.datetime.fromtimestamp(
            stat.st_mtime
        ).isoformat()
    except (OSError, OverflowError, ValueError) as exc:
        logger.warning("Could not convert modification time: %s", exc)
        append_error_log(f"WARNING: could not convert mtime: {exc}")

    logger.info(
        "Source file found: %s (%.3f GiB, modified %s)",
        source_path,
        file_size_gib,
        modification_time_iso,
    )

    # ------------------------------------------------------------------
    # 2/3. Binary prefix inspection (BOM, encoding, newline, delimiter)
    # ------------------------------------------------------------------
    try:
        prefix_report, _text_prefix, decode_encoding = build_binary_prefix_report(
            source_path
        )
    except OSError as exc:
        msg = f"FATAL: could not read binary prefix: {exc}"
        logger.error(msg)
        append_error_log(msg)
        return 1

    logger.info(
        "Binary prefix inspected: encoding=%s delimiter=%r newline=%s quoting=%s",
        prefix_report.probable_encoding,
        prefix_report.probable_delimiter,
        prefix_report.newline_convention,
        prefix_report.quoting_observed,
    )

    # ------------------------------------------------------------------
    # 4. Parse header + first 10 logical records with a real CSV parser
    # ------------------------------------------------------------------
    try:
        parsed_report, raw_rows, parse_errors = parse_first_n_records(
            path=source_path,
            encoding=decode_encoding,
            delimiter=prefix_report.probable_delimiter,
            quote_char=prefix_report.quote_char_guess or '"',
            n=NUM_SAMPLE_RECORDS,
        )
    except ValueError as exc:
        msg = f"FATAL: failed to parse header/sample records: {exc}"
        logger.error(msg)
        append_error_log(msg)
        return 1
    except (OSError, csv.Error) as exc:
        msg = f"FATAL: CSV parser error while reading sample records: {exc}"
        logger.error(msg)
        append_error_log(msg)
        return 1

    for err in parse_errors:
        logger.warning("Malformed sample record: %s", err)
        append_error_log(f"WARNING: {err}")

    if parsed_report.duplicate_column_names:
        msg = f"Duplicate column names detected: {parsed_report.duplicate_column_names}"
        logger.warning(msg)
        append_error_log(f"WARNING: {msg}")

    if parsed_report.blank_column_names:
        msg = f"Blank column name(s) at index: {parsed_report.blank_column_names}"
        logger.warning(msg)
        append_error_log(f"WARNING: {msg}")

    if not parsed_report.row_width_consistent:
        msg = (
            "Row width is NOT consistent across the first "
            f"{NUM_SAMPLE_RECORDS} records: widths={parsed_report.row_widths}"
        )
        logger.warning(msg)
        append_error_log(f"WARNING: {msg}")

    # ------------------------------------------------------------------
    # 5/6. Redact sample rows and write outputs
    # ------------------------------------------------------------------
    redacted_rows = [redact_row(row) for row in raw_rows]

    with open(SAMPLE_CSV_PATH, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(redacted_rows[0].keys()) if redacted_rows else parsed_report.column_names,
        )
        writer.writeheader()
        for row in redacted_rows:
            writer.writerow(row)

    summary: Dict[str, Any] = {
        "source_file": str(source_path),
        "source_size_bytes": file_size_bytes,
        "source_size_gib": round(file_size_gib, 4),
        "source_modification_time": modification_time_iso,
        "sample_records_requested": NUM_SAMPLE_RECORDS,
        "sample_records_parsed": parsed_report.rows_parsed,
        "binary_prefix_report": asdict(prefix_report),
        "decode_encoding_used": decode_encoding,
        "num_columns": parsed_report.num_columns,
        "column_names": parsed_report.column_names,
        "duplicate_column_names": parsed_report.duplicate_column_names,
        "blank_column_name_indices": parsed_report.blank_column_names,
        "row_width_consistent_in_sample": parsed_report.row_width_consistent,
        "row_widths_in_sample": parsed_report.row_widths,
        "malformed_row_indices_in_sample": parsed_report.malformed_rows,
        "notes": (
            "This summary is based ONLY on a binary prefix and the first "
            f"{NUM_SAMPLE_RECORDS} logical CSV records. It is not a full-file "
            "profile; see 02_profile_security_log.py for streaming statistics."
        ),
    }

    with open(SUMMARY_PATH, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    notes_lines = [
        "# Inspection Notes (Phase A)",
        "",
        f"- Source file: `{SOURCE_FILENAME}`",
        f"- Source size: {file_size_gib:.3f} GiB ({file_size_bytes} bytes)",
        f"- Modification time: {modification_time_iso}",
        f"- Probable encoding: {prefix_report.probable_encoding}",
        f"  - {prefix_report.encoding_confidence_note}",
        f"- Newline convention: {prefix_report.newline_convention}",
        f"- Probable delimiter: {prefix_report.probable_delimiter!r}",
        f"  - {prefix_report.delimiter_detection_method}",
        f"- Quoting observed in prefix: {prefix_report.quoting_observed} "
        f"(quote char guess: {prefix_report.quote_char_guess!r})",
        f"- Number of columns: {parsed_report.num_columns}",
        f"- Column names: {parsed_report.column_names}",
        f"- Duplicate column names: {parsed_report.duplicate_column_names or 'none'}",
        f"- Blank column name indices: {parsed_report.blank_column_names or 'none'}",
        f"- Row width consistent across first {NUM_SAMPLE_RECORDS} records: "
        f"{parsed_report.row_width_consistent}",
        f"- Malformed record indices in sample: {parsed_report.malformed_rows or 'none'}",
        "",
        "## Assumptions",
        "- Encoding/delimiter/quoting were detected heuristically from a "
        f"{prefix_report.bytes_read}-byte prefix; they are NOT guaranteed to "
        "hold for the entire 3.7+ GB file. Phase B will surface parse "
        "failure rates across the full file.",
        "- No column meaning is assumed here; column names are reported "
        "verbatim (redacted values only).",
        "",
        "## Files produced",
        f"- `{SUMMARY_PATH.relative_to(REPO_ROOT)}`",
        f"- `{SAMPLE_CSV_PATH.relative_to(REPO_ROOT)}`",
        f"- `{NOTES_PATH.relative_to(REPO_ROOT)}` (this file)",
        f"- `{ERRORS_LOG_PATH.relative_to(REPO_ROOT)}`",
    ]
    NOTES_PATH.write_text("\n".join(notes_lines), encoding="utf-8")

    logger.info("Phase A complete. Artifacts written to %s", ARTIFACTS_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
