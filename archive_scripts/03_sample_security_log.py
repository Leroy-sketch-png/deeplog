"""Phase C: Bounded, deterministic, stratified representative sample.

Draws a bounded (<= 50,000 row) sample from the source CSV using
stratified reservoir sampling (Algorithm R per stratum) keyed on a
low-cardinality categorical column identified from the Phase B profile
(falls back to a single global reservoir if no such column exists).

Must be run AFTER 02_profile_security_log.py (uses its
artifacts/column_statistics.json and artifacts/schema_profile.csv to pick
the stratification column and compute per-stratum sample budgets).

Sensitive columns are NOT simply blanked in this sample: identifier-like
sensitive columns (e.g. CorrelationId, EventDataId, ResourceId,
SubscriptionId, Caller, CallerIpAddress) are replaced with a stable salted
hash so that grouping/relationship structure is preserved for later
exploratory work, without exposing the raw identifier. Purely-secret
columns (e.g. Authorization) are fully redacted since they carry no
useful grouping signal. The salt is generated fresh for this run via
``os.urandom`` and is never written to disk.
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from src.hashing import generate_run_salt, salted_hash  # noqa: E402
from src.redact import column_is_sensitive_by_name, redact_value_content  # noqa: E402
from src.role_heuristics import classify_column_name  # noqa: E402
from src.sampling import (  # noqa: E402
    StratifiedReservoirSampler,
    compute_proportional_budgets,
)

SOURCE_FILENAME = "logs_output_20260713_180521.csv"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
INSPECTION_SUMMARY_PATH = ARTIFACTS_DIR / "inspection_summary.json"
COLUMN_STATS_PATH = ARTIFACTS_DIR / "column_statistics.json"
MANIFEST_PATH = ARTIFACTS_DIR / "profile_run_manifest.json"

SAMPLE_OUTPUT_PATH = ARTIFACTS_DIR / "representative_sample_redacted.csv"
SAMPLING_METHOD_PATH = ARTIFACTS_DIR / "sampling_method.md"

MAX_SAMPLE_ROWS = 50_000
RANDOM_SEED = 20260722  # fixed for determinism; recorded in sampling_method.md
MAX_STRATIFY_CARDINALITY = 20  # only stratify on columns with <= this many values
FALLBACK_RESERVOIR_FRACTION = 0.02  # slack reservoir for unseen/rare strata

logger = logging.getLogger("sample_security_log")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def pick_stratify_column(column_stats: Dict[str, Any], header: List[str]) -> Optional[str]:
    """Pick a low-cardinality severity/status/event-type-like column to
    stratify on, based on Phase B statistics -- never on name alone.
    """
    best_col = None
    best_count = None
    for col in header:
        stats = column_stats.get(col)
        if not stats:
            continue
        if stats.get("cardinality_capped"):
            continue  # cardinality unknown/too high -- unsafe to stratify on
        if stats.get("is_sensitive_by_name"):
            continue  # never stratify on a sensitive/identifier-like column
        flags = classify_column_name(col)
        if not (flags["severity_status_candidate"] or flags["event_type_candidate"]):
            continue
        distinct = len(stats.get("top_values", []))
        if distinct == 0 or distinct > MAX_STRATIFY_CARDINALITY:
            continue
        if best_count is None or distinct < best_count:
            best_col = col
            best_count = distinct
    return best_col


def main() -> int:
    setup_logging()

    if not COLUMN_STATS_PATH.exists() or not MANIFEST_PATH.exists():
        logger.error(
            "FATAL: Phase B artifacts not found (%s / %s). Run "
            "02_profile_security_log.py first.",
            COLUMN_STATS_PATH, MANIFEST_PATH,
        )
        return 1

    with open(COLUMN_STATS_PATH, "r", encoding="utf-8") as fh:
        column_stats = json.load(fh)
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    header: List[str] = manifest["column_names"]
    encoding: str = manifest["encoding"]
    delimiter: str = manifest["delimiter"]
    quote_char: str = manifest["quote_char"]

    source_path = REPO_ROOT / SOURCE_FILENAME
    if not source_path.exists():
        logger.error("FATAL: source file not found: %s", source_path)
        return 1

    # ------------------------------------------------------------------
    # Determine stratification column + per-stratum budgets
    # ------------------------------------------------------------------
    stratify_col = pick_stratify_column(column_stats, header)

    if stratify_col is not None:
        stratum_counts = {
            entry["value"]: entry["count"]
            for entry in column_stats[stratify_col]["top_values"]
        }
        main_budget = int(MAX_SAMPLE_ROWS * (1 - FALLBACK_RESERVOIR_FRACTION))
        budgets = compute_proportional_budgets(stratum_counts, main_budget)
        fallback_capacity = MAX_SAMPLE_ROWS - sum(budgets.values())
        logger.info(
            "Stratifying sample on column '%s' (%d strata). Budgets: %s",
            stratify_col, len(budgets), budgets,
        )
    else:
        budgets = {}
        fallback_capacity = MAX_SAMPLE_ROWS
        logger.info(
            "No suitable low-cardinality severity/event-type column found; "
            "using a single global reservoir of size %d.", MAX_SAMPLE_ROWS,
        )

    sampler = StratifiedReservoirSampler(
        stratum_budgets=budgets,
        seed_base=RANDOM_SEED,
        fallback_capacity=fallback_capacity,
    )

    # ------------------------------------------------------------------
    # Salt + identifier-hash column selection (never persisted to disk)
    # ------------------------------------------------------------------
    salt = generate_run_salt()
    identifier_hash_columns = {
        col for col in header
        if column_is_sensitive_by_name(col) and classify_column_name(col)["identifier_candidate"]
    }
    fully_redacted_sensitive_columns = {
        col for col in header
        if column_is_sensitive_by_name(col) and col not in identifier_hash_columns
    }
    logger.info("Identifier columns replaced with salted hash: %s", sorted(identifier_hash_columns))
    logger.info("Sensitive columns fully redacted (no hash): %s", sorted(fully_redacted_sensitive_columns))

    # ------------------------------------------------------------------
    # Single streaming pass: offer each row to the sampler
    # ------------------------------------------------------------------
    total_rows = 0
    try:
        with open(source_path, "r", encoding=encoding, errors="replace", newline="") as fh:
            reader = csv.reader(fh, delimiter=delimiter, quotechar=quote_char)
            next(reader)  # skip header
            for row in reader:
                total_rows += 1
                if len(row) != len(header):
                    continue  # skip malformed rows for sampling purposes
                stratum_key = row[header.index(stratify_col)] if stratify_col else "__all__"
                sampler.offer(stratum_key, row)
    except OSError as exc:
        logger.error("FATAL: I/O error while streaming file: %s", exc)
        return 1

    sampled_rows = sampler.all_items()
    logger.info(
        "Sampling complete: %d rows scanned, %d rows sampled (cap=%d).",
        total_rows, len(sampled_rows), MAX_SAMPLE_ROWS,
    )

    # ------------------------------------------------------------------
    # Redact + write output. Preserve original file's row order for
    # readability (sort by the timestamp column if present, else leave as
    # sampled).
    # ------------------------------------------------------------------
    def transform_row(row: List[str]) -> List[str]:
        out = []
        for col, val in zip(header, row):
            if col in identifier_hash_columns:
                out.append(salted_hash(val, salt))
            elif col in fully_redacted_sensitive_columns:
                out.append("[REDACTED]")
            else:
                out.append(redact_value_content(val))
        return out

    transformed = [transform_row(r) for r in sampled_rows]

    time_col_idx = header.index("TimeGenerated") if "TimeGenerated" in header else None
    if time_col_idx is not None:
        transformed.sort(key=lambda r: r[time_col_idx])

    with open(SAMPLE_OUTPUT_PATH, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(transformed)

    # ------------------------------------------------------------------
    # sampling_method.md
    # ------------------------------------------------------------------
    lines = [
        "# Sampling Method (Phase C)",
        "",
        f"- Source rows scanned: {total_rows}",
        f"- Sample rows written: {len(transformed)} (cap = {MAX_SAMPLE_ROWS})",
        f"- Random seed (base): {RANDOM_SEED}",
        f"- Stratification column: {stratify_col or 'none (single global reservoir used)'}",
    ]
    if stratify_col:
        lines.append(f"- Per-stratum budgets: {budgets}")
        lines.append(f"- Fallback reservoir capacity (unseen/rare strata): {fallback_capacity}")
        lines.append(f"- Per-stratum observed vs sampled: {sampler.stratum_summary()}")
    lines.extend([
        "",
        "## Algorithm",
        "- Stratified reservoir sampling (Algorithm R, Vitter 1985) run in a "
        "single streaming pass over the source file.",
        "- Each stratum has its own reservoir with a fixed capacity computed "
        "proportionally to that stratum's observed row count from Phase B "
        "(artifacts/column_statistics.json).",
        "- Deterministic: each stratum's internal RNG is seeded from a fixed "
        f"base seed ({RANDOM_SEED}) combined with the stratum name.",
        "- This is NOT the first 50,000 rows of the file -- every row had a "
        "chance of being retained, and later rows can replace earlier ones "
        "in a stratum's reservoir.",
        "",
        "## Redaction and pseudonymization",
        f"- Identifier-like sensitive columns replaced with a stable salted "
        f"hash (salt generated via os.urandom for this run only, NEVER "
        f"written to disk): {sorted(identifier_hash_columns)}",
        f"- Purely-secret columns fully redacted (no hash, no grouping value): "
        f"{sorted(fully_redacted_sensitive_columns)}",
        "- All other columns passed through content-based redaction "
        "(emails, IPv4/IPv6, GUIDs, auth headers, long mixed alnum tokens).",
        "- Hashing note: salt is process-local and discarded on exit; hashed "
        "values in this sample CANNOT be joined against any other run's "
        "sample or against the source file.",
        "",
        "## Limitations",
        "- Malformed rows (field-count mismatch) were excluded from sampling.",
        "- If no severity/event-type column with <= "
        f"{MAX_STRATIFY_CARDINALITY} distinct values was found, sampling "
        "fell back to a single global reservoir (documented above).",
    ])
    SAMPLING_METHOD_PATH.write_text("\n".join(lines), encoding="utf-8")

    logger.info("Phase C complete. Artifacts written to %s", ARTIFACTS_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
