"""Phase B: Streaming dataset profile of a large local security-log CSV.

Processes the CSV in a single streaming pass using the standard-library
``csv`` module (never loading the full file into memory). All per-column
value trackers are bounded (capped cardinality, hashed values for
sensitive columns) so memory stays flat regardless of file size.

Run with:

    python 02_profile_security_log.py

Must be run AFTER 01_inspect_security_log.py (reuses its encoding/delimiter
detection from artifacts/inspection_summary.json for consistency; falls
back to re-detecting if that file is missing).
"""

from __future__ import annotations

import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from src.inspect_utils import build_binary_prefix_report  # noqa: E402
from src.profile_utils import (  # noqa: E402
    ColumnStats,
    DuplicateRowTracker,
    MAX_DUPLICATE_ROW_HASHES,
    CARDINALITY_CAP,
)
from src.redact import column_is_sensitive_by_name, redact_value_content  # noqa: E402
from src.role_heuristics import classify_all_columns  # noqa: E402
from src.sysinfo import get_peak_memory_mb  # noqa: E402

SCRIPT_VERSION = "1.0.0"
SOURCE_FILENAME = "logs_output_20260713_180521.csv"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
INSPECTION_SUMMARY_PATH = ARTIFACTS_DIR / "inspection_summary.json"

CHUNK_SIZE = 100_000            # progress-log cadence, in rows
PROGRESS_LOG_INTERVAL_SEC = 30  # also log at least this often
MAX_LOGGED_PARSE_ERRORS = 500   # cap individual error lines written to log

SCHEMA_PROFILE_PATH = ARTIFACTS_DIR / "schema_profile.csv"
COLUMN_STATS_PATH = ARTIFACTS_DIR / "column_statistics.json"
DATA_QUALITY_REPORT_PATH = ARTIFACTS_DIR / "data_quality_report.md"
PROFILE_ERRORS_LOG_PATH = ARTIFACTS_DIR / "profile_errors.log"
MANIFEST_PATH = ARTIFACTS_DIR / "profile_run_manifest.json"

logger = logging.getLogger("profile_security_log")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def load_phase_a_config() -> Optional[Dict[str, Any]]:
    """Reuse Phase A's detected encoding/delimiter/quote-char if available."""
    if not INSPECTION_SUMMARY_PATH.exists():
        return None
    try:
        with open(INSPECTION_SUMMARY_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not reuse Phase A config: %s", exc)
        return None


def format_ts(ts: Optional[datetime]) -> Optional[str]:
    return ts.isoformat() if ts is not None else None


def main() -> int:  # noqa: C901 (single-pass profiler; complexity is inherent)
    setup_logging()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_ERRORS_LOG_PATH.write_text("", encoding="utf-8")

    start_time = datetime.now()
    start_monotonic = time.monotonic()

    source_path = REPO_ROOT / SOURCE_FILENAME
    error_lines: List[str] = []

    def log_error(msg: str) -> None:
        logger.warning(msg)
        if len(error_lines) < MAX_LOGGED_PARSE_ERRORS:
            error_lines.append(msg)
        elif len(error_lines) == MAX_LOGGED_PARSE_ERRORS:
            error_lines.append("Further errors suppressed (cap reached).")

    if not source_path.exists():
        msg = f"FATAL: source file not found: {source_path}"
        logger.error(msg)
        PROFILE_ERRORS_LOG_PATH.write_text(msg + "\n", encoding="utf-8")
        return 1

    stat = source_path.stat()

    # ----------------------------------------------------------------
    # Determine encoding/delimiter/quote char (reuse Phase A if present)
    # ----------------------------------------------------------------
    phase_a = load_phase_a_config()
    if phase_a is not None:
        encoding = phase_a["decode_encoding_used"]
        delimiter = phase_a["binary_prefix_report"]["probable_delimiter"]
        quote_char = phase_a["binary_prefix_report"]["quote_char_guess"] or '"'
        config_source = "reused_from_phase_a"
        logger.info("Reusing Phase A config: encoding=%s delimiter=%r", encoding, delimiter)
    else:
        logger.warning("Phase A summary not found; re-detecting from scratch.")
        prefix_report, _text, encoding = build_binary_prefix_report(source_path)
        delimiter = prefix_report.probable_delimiter
        quote_char = prefix_report.quote_char_guess or '"'
        config_source = "re_detected"

    # ----------------------------------------------------------------
    # Read header, prepare per-column accumulators
    # ----------------------------------------------------------------
    try:
        with open(source_path, "r", encoding=encoding, errors="replace", newline="") as fh:
            reader = csv.reader(fh, delimiter=delimiter, quotechar=quote_char)
            header = next(reader)
    except (OSError, StopIteration, csv.Error) as exc:
        msg = f"FATAL: could not read header: {exc}"
        logger.error(msg)
        PROFILE_ERRORS_LOG_PATH.write_text(msg + "\n", encoding="utf-8")
        return 1

    num_columns = len(header)
    role_flags = classify_all_columns(header)
    sensitive_flags = {col: column_is_sensitive_by_name(col) for col in header}

    column_stats: Dict[str, ColumnStats] = {
        col: ColumnStats(name=col, is_sensitive=sensitive_flags[col]) for col in header
    }
    timestamp_candidate_cols = {
        col for col in header if role_flags[col]["timestamp_candidate"]
    }

    logger.info(
        "Header parsed: %d columns. Timestamp candidates: %s",
        num_columns,
        sorted(timestamp_candidate_cols),
    )
    logger.info(
        "Sensitive-by-name columns (hashed cardinality, no raw values retained): %s",
        sorted(c for c, s in sensitive_flags.items() if s),
    )

    dup_tracker = DuplicateRowTracker(cap=MAX_DUPLICATE_ROW_HASHES)

    total_rows = 0
    malformed_row_count = 0
    rows_with_fewer_fields = 0
    rows_with_more_fields = 0

    last_log_time = start_monotonic
    last_log_rows = 0

    # ----------------------------------------------------------------
    # Single streaming pass
    # ----------------------------------------------------------------
    try:
        with open(source_path, "r", encoding=encoding, errors="replace", newline="") as fh:
            reader = csv.reader(fh, delimiter=delimiter, quotechar=quote_char)
            next(reader)  # skip header (already parsed above)

            row_iter = iter(reader)
            while True:
                try:
                    row = next(row_iter)
                except StopIteration:
                    break
                except csv.Error as exc:
                    malformed_row_count += 1
                    log_error(f"Row {total_rows}: csv.Error while parsing: {exc}")
                    continue

                total_rows += 1
                width = len(row)

                if width != num_columns:
                    malformed_row_count += 1
                    if width < num_columns:
                        rows_with_fewer_fields += 1
                    else:
                        rows_with_more_fields += 1
                    if malformed_row_count <= MAX_LOGGED_PARSE_ERRORS:
                        log_error(
                            f"Row {total_rows}: expected {num_columns} fields, got {width}."
                        )

                # Update per-column stats using positional zip (best-effort
                # even for malformed rows, using whatever fields exist).
                for idx, col in enumerate(header):
                    value = row[idx] if idx < width else None
                    column_stats[col].update(
                        value, is_timestamp_candidate=col in timestamp_candidate_cols
                    )

                # Duplicate detection only for well-formed rows.
                if width == num_columns:
                    dup_tracker.observe("\x1f".join(row))

                # Progress logging: every CHUNK_SIZE rows or every N seconds.
                now = time.monotonic()
                if total_rows - last_log_rows >= CHUNK_SIZE or (now - last_log_time) >= PROGRESS_LOG_INTERVAL_SEC:
                    elapsed = now - start_monotonic
                    rate = total_rows / elapsed if elapsed > 0 else 0.0
                    logger.info(
                        "Progress: %d rows processed (%d malformed) | %.0f rows/sec | elapsed %.1fs",
                        total_rows,
                        malformed_row_count,
                        rate,
                        elapsed,
                    )
                    last_log_time = now
                    last_log_rows = total_rows
    except OSError as exc:
        msg = f"FATAL: I/O error while streaming file: {exc}"
        logger.error(msg)
        log_error(msg)
        PROFILE_ERRORS_LOG_PATH.write_text("\n".join(error_lines) + "\n", encoding="utf-8")
        return 1

    finish_time = datetime.now()
    elapsed_total = time.monotonic() - start_monotonic
    logger.info(
        "Streaming pass complete: %d rows, %d malformed, elapsed %.1fs",
        total_rows,
        malformed_row_count,
        elapsed_total,
    )

    # ----------------------------------------------------------------
    # Build schema_profile.csv + column_statistics.json
    # ----------------------------------------------------------------
    schema_rows: List[Dict[str, Any]] = []
    detailed_stats: Dict[str, Any] = {}

    for col in header:
        cs = column_stats[col]
        non_null = cs.total_count - cs.null_or_blank_count
        len_mean, len_std = cs.length_mean_std()

        numeric_attempts = cs.numeric_success_count + cs.numeric_fail_count
        numeric_rate = (cs.numeric_success_count / numeric_attempts) if numeric_attempts else None

        ts_attempts = cs.timestamp_success_count + cs.timestamp_fail_count
        ts_rate = (cs.timestamp_success_count / ts_attempts) if ts_attempts else None

        # Dtype guess heuristic.
        if col in timestamp_candidate_cols and ts_rate is not None and ts_rate >= 0.95:
            dtype_guess = "timestamp"
        elif numeric_rate is not None and numeric_rate >= 0.95:
            dtype_guess = "numeric"
        elif not cs.cardinality_capped and cs.total_count > 0 and len(cs.value_counts) <= max(50, int(0.05 * cs.total_count)):
            dtype_guess = "categorical"
        else:
            dtype_guess = "text_or_high_cardinality"

        flags = role_flags[col]

        schema_rows.append({
            "column_name": col,
            "dtype_guess": dtype_guess,
            "is_sensitive_by_name": cs.is_sensitive,
            "total_count": cs.total_count,
            "non_null_count": non_null,
            "null_or_blank_pct": round(100.0 * cs.null_or_blank_count / cs.total_count, 4) if cs.total_count else None,
            "distinct_count_or_cap": cs.approx_cardinality_label(),
            "cardinality_capped": cs.cardinality_capped,
            "len_min": cs.len_min,
            "len_max": cs.len_max,
            "len_mean": round(len_mean, 2) if len_mean is not None else None,
            "len_std": round(len_std, 2) if len_std is not None else None,
            "numeric_success_pct": round(100.0 * numeric_rate, 2) if numeric_rate is not None else None,
            "numeric_min": cs.numeric_min,
            "numeric_max": cs.numeric_max,
            "timestamp_success_pct": round(100.0 * ts_rate, 2) if ts_rate is not None else None,
            "timestamp_min": format_ts(cs.timestamp_min),
            "timestamp_max": format_ts(cs.timestamp_max),
            "timestamp_out_of_order_count": cs.timestamp_out_of_order_count if col in timestamp_candidate_cols else None,
            "timestamp_duplicate_count": cs.timestamp_duplicate_count if col in timestamp_candidate_cols else None,
            "inconsistent_casing_detected": cs.inconsistent_casing_detected(),
            "timestamp_candidate": flags["timestamp_candidate"],
            "identifier_candidate": flags["identifier_candidate"],
            "event_type_candidate": flags["event_type_candidate"],
            "message_or_blob_candidate": flags["message_or_blob_candidate"],
            "severity_status_candidate": flags["severity_status_candidate"],
        })

        # Top values: NEVER include raw values for sensitive columns (they
        # are already one-way hashes at this point). For non-sensitive
        # columns, defensively redact content before persisting.
        if cs.is_sensitive:
            top_values_out = [{"hashed_value": v, "count": c} for v, c in cs.top_values()]
            top_values_note = "Sensitive column: values are one-way hashes, not raw data."
        else:
            top_values_out = [
                {"value": redact_value_content(v), "count": c} for v, c in cs.top_values()
            ]
            top_values_note = "Non-sensitive column; values defensively content-redacted."

        detailed_stats[col] = {
            "is_sensitive_by_name": cs.is_sensitive,
            "role_flags": flags,
            "total_count": cs.total_count,
            "null_or_blank_count": cs.null_or_blank_count,
            "placeholder_counts": cs.placeholder_counts,
            "distinct_count_or_cap": cs.approx_cardinality_label(),
            "cardinality_capped": cs.cardinality_capped,
            "cardinality_cap_value": CARDINALITY_CAP,
            "top_values": top_values_out,
            "top_values_note": top_values_note,
            "length_stats": {
                "min": cs.len_min, "max": cs.len_max,
                "mean": len_mean, "std": len_std,
            },
            "numeric_stats": {
                "success_count": cs.numeric_success_count,
                "fail_count": cs.numeric_fail_count,
                "success_rate": numeric_rate,
                "min": cs.numeric_min,
                "max": cs.numeric_max,
            },
            "timestamp_stats": {
                "is_candidate": col in timestamp_candidate_cols,
                "success_count": cs.timestamp_success_count,
                "fail_count": cs.timestamp_fail_count,
                "success_rate": ts_rate,
                "min": format_ts(cs.timestamp_min),
                "max": format_ts(cs.timestamp_max),
                "out_of_order_count": cs.timestamp_out_of_order_count,
                "duplicate_timestamp_count": cs.timestamp_duplicate_count,
            },
            "inconsistent_casing_detected": cs.inconsistent_casing_detected(),
        }

    # Write schema_profile.csv
    with open(SCHEMA_PROFILE_PATH, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(schema_rows[0].keys()))
        writer.writeheader()
        for row in schema_rows:
            writer.writerow(row)

    # Write column_statistics.json
    with open(COLUMN_STATS_PATH, "w", encoding="utf-8") as fh:
        json.dump(detailed_stats, fh, indent=2, default=str)

    # ----------------------------------------------------------------
    # Data quality report (markdown)
    # ----------------------------------------------------------------
    dq_lines = [
        "# Data Quality Report (Phase B)",
        "",
        f"- Total rows processed (attempted): {total_rows}",
        f"- Malformed rows (field-count mismatch): {malformed_row_count} "
        f"({rows_with_fewer_fields} with fewer fields, {rows_with_more_fields} with more fields)",
        f"- Well-formed rows used for duplicate detection: {dup_tracker.rows_considered}",
        f"- Duplicate full-row estimate: {dup_tracker.duplicate_count} "
        f"({'capped/approximate' if dup_tracker.capped else 'exact over parsed rows'})",
        "",
        "## Per-column issues",
        "",
    ]
    for col in header:
        cs = column_stats[col]
        issues: List[str] = []
        if cs.null_or_blank_count:
            issues.append(
                f"{cs.null_or_blank_count} null/blank/placeholder values "
                f"({round(100.0 * cs.null_or_blank_count / cs.total_count, 2)}%)"
            )
        if cs.placeholder_counts:
            issues.append(f"placeholder breakdown: {cs.placeholder_counts}")
        if cs.cardinality_capped:
            issues.append(f"cardinality exceeded cap of {CARDINALITY_CAP} (approximate only)")
        if cs.inconsistent_casing_detected():
            issues.append("inconsistent capitalization/whitespace detected among distinct values")
        if col in timestamp_candidate_cols:
            ts_attempts = cs.timestamp_success_count + cs.timestamp_fail_count
            if ts_attempts:
                rate = cs.timestamp_success_count / ts_attempts
                issues.append(f"timestamp parse success rate: {round(100*rate,2)}%")
            if cs.timestamp_out_of_order_count:
                issues.append(
                    f"{cs.timestamp_out_of_order_count} out-of-order timestamp transitions observed "
                    "(row order is not fully chronological)"
                )
            if cs.timestamp_duplicate_count:
                issues.append(f"{cs.timestamp_duplicate_count} consecutive duplicate timestamps observed")
        if not issues:
            issues.append("no notable issues detected")
        dq_lines.append(f"- **{col}**: {'; '.join(issues)}")

    DATA_QUALITY_REPORT_PATH.write_text("\n".join(dq_lines), encoding="utf-8")

    # ----------------------------------------------------------------
    # Errors log + manifest
    # ----------------------------------------------------------------
    PROFILE_ERRORS_LOG_PATH.write_text(
        ("\n".join(error_lines) + "\n") if error_lines else "No parse errors recorded.\n",
        encoding="utf-8",
    )

    peak_mem_mb = get_peak_memory_mb()

    manifest = {
        "source_filename": SOURCE_FILENAME,
        "source_size_bytes": stat.st_size,
        "source_modification_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "script_version": SCRIPT_VERSION,
        "start_time": start_time.isoformat(),
        "finish_time": finish_time.isoformat(),
        "elapsed_seconds": round(elapsed_total, 2),
        "config_source": config_source,
        "encoding": encoding,
        "delimiter": delimiter,
        "quote_char": quote_char,
        "chunk_size_rows_for_progress_logging": CHUNK_SIZE,
        "progress_log_interval_sec": PROGRESS_LOG_INTERVAL_SEC,
        "num_columns": num_columns,
        "column_names": header,
        "timestamp_candidate_columns": sorted(timestamp_candidate_cols),
        "sensitive_by_name_columns": sorted(c for c, s in sensitive_flags.items() if s),
        "rows_processed": total_rows,
        "malformed_rows": malformed_row_count,
        "rows_with_fewer_fields": rows_with_fewer_fields,
        "rows_with_more_fields": rows_with_more_fields,
        "duplicate_row_tracking": dup_tracker.summary(),
        "peak_memory_mb": peak_mem_mb,
        "approximations_and_caps": {
            "cardinality_cap_per_column": CARDINALITY_CAP,
            "duplicate_row_hash_cap": MAX_DUPLICATE_ROW_HASHES,
            "max_logged_parse_errors": MAX_LOGGED_PARSE_ERRORS,
            "adaptive_chunk_sizing": (
                "Not implemented: all in-memory accumulators are pre-bounded "
                "by design (capped cardinality dicts, hashed sensitive "
                "values, running sum/sumsq for length stats), so memory use "
                "stays flat regardless of file size and no memory-pressure "
                "fallback was triggered or required."
            ),
        },
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, default=str)

    logger.info("Phase B complete. Artifacts written to %s", ARTIFACTS_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
