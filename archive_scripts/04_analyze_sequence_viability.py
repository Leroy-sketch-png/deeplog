from __future__ import annotations

import csv
import hashlib
import json
import logging
import math
import os
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from src.semantic_parsing import (  # noqa: E402
    classify_identity,
    derive_token_e,
    extract_claims_fields,
    extract_properties_fields,
    normalize_activity_status,
    normalize_operation,
    parse_timestamp,
)

SOURCE_FILENAME = "logs_output_20260713_180521.csv"
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "sequence_viability"
DB_SQLITE = ARTIFACTS_DIR / "sequence_viability.sqlite"
DB_DUCKDB = ARTIFACTS_DIR / "sequence_viability.duckdb"

SEMANTIC_PROFILE_PATH = ARTIFACTS_DIR / "semantic_extraction_profile.json"
CORR_STATS_PATH = ARTIFACTS_DIR / "correlation_group_statistics.json"
CORR_SEQ_PATTERNS_PATH = ARTIFACTS_DIR / "correlation_sequence_patterns.csv"
CALLER_SUMMARY_PATH = ARTIFACTS_DIR / "caller_identity_summary.csv"
CALLER_CONCENTRATION_PATH = ARTIFACTS_DIR / "caller_concentration.json"
SESSION_COMPARISON_PATH = ARTIFACTS_DIR / "sessionization_comparison.csv"
RESOURCE_ANALYSIS_PATH = ARTIFACTS_DIR / "resource_sequence_analysis.json"
TOKEN_COMPARISON_PATH = ARTIFACTS_DIR / "tokenization_comparison.csv"
TIME_SPLIT_PATH = ARTIFACTS_DIR / "time_split_analysis.json"
EVAL_STRATEGY_PATH = ARTIFACTS_DIR / "evaluation_strategy.md"
MODELING_RECOMMENDATION_PATH = ARTIFACTS_DIR / "modeling_recommendation.md"
VIABILITY_REPORT_PATH = ARTIFACTS_DIR / "sequence_viability_report.md"
RUN_MANIFEST_PATH = ARTIFACTS_DIR / "run_manifest.json"
ERROR_LOG_PATH = ARTIFACTS_DIR / "errors.log"
INTERNAL_EXAMPLES_PATH = ARTIFACTS_DIR / "internal_sequence_examples.csv"

RANDOM_SEED = 20260722
CHUNK_SIZE = 5000
MAX_PARSE_ERROR_EXAMPLES = 40

logger = logging.getLogger("sequence_viability")


def setup_logging() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(ERROR_LOG_PATH, mode="w", encoding="utf-8"),
        ],
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pct(n: int, d: int) -> float:
    return (100.0 * n / d) if d else 0.0


def percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    vals = sorted(values)
    pos = (len(vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(vals[lo])
    frac = pos - lo
    return float(vals[lo] * (1 - frac) + vals[hi] * frac)


def entropy_from_counts(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    e = 0.0
    for c in counts.values():
        p = c / total
        if p > 0:
            e -= p * math.log2(p)
    return e


def top_n_coverage(counter: Counter[str], n: int) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0
    top = sum(c for _, c in counter.most_common(n))
    return top / total


def is_sensitive_action(operation: str, action_verb: str) -> bool:
    op = (operation or "").upper()
    verb = (action_verb or "").upper()
    if verb in {"LISTKEYS", "DELETE", "MANUALUPGRADE"}:
        return True
    sensitive_terms = [
        "ROLEASSIGNMENTS",
        "AUTHORIZATION",
        "POLICY",
        "NETWORKSECURITYGROUP",
        "NSG",
        "ADMIN",
    ]
    return any(t in op for t in sensitive_terms)


@dataclass
class DBEngine:
    name: str
    conn: Any
    placeholder: str

    def execute(self, sql: str, params: Optional[Sequence[Any]] = None) -> Any:
        if params is None:
            return self.conn.execute(sql)
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> Any:
        return self.conn.executemany(sql, rows)

    def query_all(self, sql: str, params: Optional[Sequence[Any]] = None) -> List[Tuple[Any, ...]]:
        cur = self.execute(sql, params)
        return cur.fetchall()

    def commit(self) -> None:
        self.conn.commit()


def init_engine() -> DBEngine:
    try:
        import duckdb  # type: ignore

        conn = duckdb.connect(str(DB_DUCKDB))
        logger.info("Using DuckDB engine at %s", DB_DUCKDB)
        return DBEngine(name="duckdb", conn=conn, placeholder="?")
    except Exception:
        conn = sqlite3.connect(str(DB_SQLITE))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=FILE;")
        logger.info("DuckDB unavailable; using SQLite engine at %s", DB_SQLITE)
        return DBEngine(name="sqlite", conn=conn, placeholder="?")


def create_schema(db: DBEngine) -> None:
    db.execute("DROP TABLE IF EXISTS events")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            row_id INTEGER,
            timestamp_utc TEXT,
            timestamp_epoch REAL,
            event_date TEXT,
            event_hour INTEGER,

            operation TEXT,
            provider TEXT,
            operation_family TEXT,
            action_verb TEXT,
            activity_status TEXT,
            activity_substatus TEXT,
            status_code TEXT,
            status_message TEXT,
            event_category TEXT,

            caller TEXT,
            caller_ip TEXT,
            subscription TEXT,
            resource_group TEXT,
            resource_entity TEXT,
            resource_type TEXT,
            correlation_id TEXT,

            identity_type TEXT,
            application_id TEXT,
            identity_object_id TEXT,
            identity_provider TEXT,
            managed_identity_resource TEXT,
            managed_identity_alt_resource TEXT,
            level TEXT,
            outcome_class TEXT,
            sensitive_action INTEGER,

            token_a TEXT,
            token_b TEXT,
            token_c TEXT,
            token_d TEXT,
            token_e TEXT,

            raw_operation TEXT,
            raw_properties TEXT,
            raw_claims TEXT
        );
        """
    )
    db.commit()


def insert_chunk(db: DBEngine, rows: List[Tuple[Any, ...]]) -> None:
    if not rows:
        return
    placeholders = ",".join([db.placeholder] * len(rows[0]))
    sql = f"""
        INSERT INTO events VALUES ({placeholders})
    """
    db.executemany(sql, rows)


def ingest_source(db: DBEngine, source_path: Path) -> Dict[str, Any]:
    parse_errors: List[Dict[str, Any]] = []
    total_rows = 0
    rows_inserted = 0
    prop_parse_ok = 0
    prop_parse_fail = 0
    claims_parse_ok = 0
    claims_parse_fail = 0
    ts_parse_fail = 0
    malformed_rows = 0

    chunk: List[Tuple[Any, ...]] = []

    with open(source_path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        for idx, row in enumerate(reader, start=1):
            total_rows += 1

            try:
                props, prop_ok, prop_err = extract_properties_fields(row.get("Properties"))
                claims, claims_ok, claims_err = extract_claims_fields(row.get("Claims"))

                if prop_ok:
                    prop_parse_ok += 1
                else:
                    prop_parse_fail += 1
                    if len(parse_errors) < MAX_PARSE_ERROR_EXAMPLES:
                        parse_errors.append(
                            {
                                "row": idx,
                                "field": "Properties",
                                "error": prop_err,
                                "snippet": str(row.get("Properties", ""))[:220],
                            }
                        )

                if claims_ok:
                    claims_parse_ok += 1
                else:
                    claims_parse_fail += 1
                    if len(parse_errors) < MAX_PARSE_ERROR_EXAMPLES:
                        parse_errors.append(
                            {
                                "row": idx,
                                "field": "Claims",
                                "error": claims_err,
                                "snippet": str(row.get("Claims", ""))[:220],
                            }
                        )

                ts_raw = row.get("TimeGenerated") or props.get("eventSubmissionTimestamp") or ""
                dt, ts_err = parse_timestamp(ts_raw)
                if dt is None:
                    ts_parse_fail += 1
                    ts_utc = ""
                    ts_epoch = None
                    event_date = ""
                    event_hour = None
                    if len(parse_errors) < MAX_PARSE_ERROR_EXAMPLES and ts_err:
                        parse_errors.append(
                            {
                                "row": idx,
                                "field": "TimeGenerated",
                                "error": ts_err,
                                "snippet": str(ts_raw)[:120],
                            }
                        )
                else:
                    ts_utc = dt.isoformat()
                    ts_epoch = dt.timestamp()
                    event_date = dt.date().isoformat()
                    event_hour = dt.hour

                raw_operation = (row.get("OperationNameValue") or "").strip()
                raw_provider = (row.get("ResourceProviderValue") or "").strip()
                operation, provider, operation_family, action_verb, resource_type = normalize_operation(
                    raw_operation, raw_provider
                )

                activity_status = (props.get("activityStatusValue") or "").strip()
                activity_substatus = (props.get("activitySubstatusValue") or "").strip()
                status_code = (props.get("statusCode") or "").strip()
                status_message = (props.get("statusMessage") or "").strip()
                outcome_class = normalize_activity_status(activity_status, activity_substatus, status_code)

                entity = (props.get("entity") or "").strip()
                resource_from_props = (props.get("resource") or "").strip()
                resource_entity = entity or resource_from_props
                event_category = (props.get("eventCategory") or "").strip()

                caller = (row.get("Caller") or "").strip()
                caller_ip = (row.get("CallerIpAddress") or props.get("httpRequest.clientIpAddress") or "").strip()
                subscription = (row.get("SubscriptionId") or "").strip()
                resource_group = (row.get("ResourceGroup") or "").strip()
                correlation_id = (row.get("CorrelationId") or "").strip()
                level = (row.get("Level") or "").strip()

                identity_type = (claims.get("idtyp") or "").strip()
                application_id = (claims.get("appid") or "").strip()
                identity_object_id = (claims.get("object_id") or "").strip()
                identity_provider = (claims.get("identity_provider") or "").strip()
                managed_identity_resource = (claims.get("xms_mirid") or "").strip()
                managed_identity_alt_resource = (claims.get("xms_az_rid") or "").strip()

                token_a = operation
                token_b = f"{operation}|{activity_status}" if operation or activity_status else ""
                token_c = f"{provider}|{operation_family}|{action_verb}" if provider or operation_family or action_verb else ""
                token_d = (
                    f"{provider}|{operation_family}|{action_verb}|{activity_status}"
                    if provider or operation_family or action_verb or activity_status
                    else ""
                )
                token_e = derive_token_e(provider, operation_family, action_verb, event_category)

                sensitive = 1 if is_sensitive_action(operation, action_verb) else 0

                out_row = (
                    idx,
                    ts_utc,
                    ts_epoch,
                    event_date,
                    event_hour,
                    operation,
                    provider,
                    operation_family,
                    action_verb,
                    activity_status,
                    activity_substatus,
                    status_code,
                    status_message,
                    event_category,
                    caller,
                    caller_ip,
                    subscription,
                    resource_group,
                    resource_entity,
                    resource_type,
                    correlation_id,
                    identity_type,
                    application_id,
                    identity_object_id,
                    identity_provider,
                    managed_identity_resource,
                    managed_identity_alt_resource,
                    level,
                    outcome_class,
                    sensitive,
                    token_a,
                    token_b,
                    token_c,
                    token_d,
                    token_e,
                    raw_operation,
                    row.get("Properties") or "",
                    row.get("Claims") or "",
                )
                chunk.append(out_row)

                if len(chunk) >= CHUNK_SIZE:
                    insert_chunk(db, chunk)
                    rows_inserted += len(chunk)
                    db.commit()
                    chunk.clear()

            except Exception as exc:
                malformed_rows += 1
                if len(parse_errors) < MAX_PARSE_ERROR_EXAMPLES:
                    parse_errors.append(
                        {
                            "row": idx,
                            "field": "row",
                            "error": f"row_exception:{exc}",
                            "snippet": str(row)[:220],
                        }
                    )

            if idx % 100000 == 0:
                logger.info("Ingested %d rows", idx)

    if chunk:
        insert_chunk(db, chunk)
        rows_inserted += len(chunk)
        db.commit()

    return {
        "header": header,
        "total_rows_read": total_rows,
        "rows_inserted": rows_inserted,
        "malformed_rows": malformed_rows,
        "properties_parse_success": prop_parse_ok,
        "properties_parse_failure": prop_parse_fail,
        "claims_parse_success": claims_parse_ok,
        "claims_parse_failure": claims_parse_fail,
        "timestamp_parse_failure": ts_parse_fail,
        "parse_error_examples": parse_errors,
    }


def create_indexes(db: DBEngine) -> None:
    idx_sql = [
        # Keep only the highest-impact indexes needed by the heaviest sequence passes.
        "CREATE INDEX IF NOT EXISTS idx_events_corr_ts ON events(correlation_id, timestamp_epoch, row_id)",
        "CREATE INDEX IF NOT EXISTS idx_events_caller_ts ON events(caller, timestamp_epoch, row_id)",
    ]
    for sql in idx_sql:
        logger.info("Building index: %s", sql)
        db.execute(sql)
    db.commit()


def analyze_correlation_groups(db: DBEngine) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    rows = db.query_all(
        """
        SELECT
            correlation_id,
            COUNT(*) AS n,
            MIN(timestamp_epoch) AS min_ts,
            MAX(timestamp_epoch) AS max_ts,
            COUNT(DISTINCT caller) AS d_caller,
            COUNT(DISTINCT operation) AS d_operation,
            COUNT(DISTINCT subscription) AS d_subscription,
            COUNT(DISTINCT resource_entity) AS d_resource_entity,
            COUNT(DISTINCT resource_group) AS d_resource_group
        FROM events
        WHERE correlation_id <> ''
        GROUP BY correlation_id
        """
    )

    group_count = len(rows)
    size_values: List[int] = []
    duration_values: List[float] = []

    bins = {
        "1": 0,
        "2": 0,
        "3": 0,
        "4": 0,
        "5_9": 0,
        "10_19": 0,
        "20_plus": 0,
    }
    dur_bins = {
        "lt_1s": 0,
        "1_10s": 0,
        "10_60s": 0,
        "1_10m": 0,
        "gt_10m": 0,
    }

    multi_caller = 0
    multi_operation = 0
    multi_subscription = 0
    multi_resource_entity = 0
    multi_resource_group = 0

    group_sizes: Dict[str, int] = {}

    for corr_id, n, min_ts, max_ts, dc, dop, dsub, dre, drg in rows:
        n_i = int(n)
        group_sizes[str(corr_id)] = n_i
        size_values.append(n_i)

        if min_ts is not None and max_ts is not None:
            dur = float(max_ts) - float(min_ts)
        else:
            dur = 0.0
        duration_values.append(dur)

        if n_i == 1:
            bins["1"] += 1
        elif n_i == 2:
            bins["2"] += 1
        elif n_i == 3:
            bins["3"] += 1
        elif n_i == 4:
            bins["4"] += 1
        elif 5 <= n_i <= 9:
            bins["5_9"] += 1
        elif 10 <= n_i <= 19:
            bins["10_19"] += 1
        else:
            bins["20_plus"] += 1

        if dur < 1:
            dur_bins["lt_1s"] += 1
        elif dur < 10:
            dur_bins["1_10s"] += 1
        elif dur < 60:
            dur_bins["10_60s"] += 1
        elif dur <= 600:
            dur_bins["1_10m"] += 1
        else:
            dur_bins["gt_10m"] += 1

        if int(dc) > 1:
            multi_caller += 1
        if int(dop) > 1:
            multi_operation += 1
        if int(dsub) > 1:
            multi_subscription += 1
        if int(dre) > 1:
            multi_resource_entity += 1
        if int(drg) > 1:
            multi_resource_group += 1

    # Sequence-level semantics per CorrelationId, sorted by timestamp.
    seq_status_counter: Counter[str] = Counter()
    seq_full_counter: Counter[str] = Counter()
    token_seq_counters = {
        "token_1_operation": Counter(),
        "token_2_operation_status": Counter(),
        "token_3_family_status": Counter(),
        "token_4_provider_verb_status": Counter(),
    }

    token_event_counters = {
        "token_1_operation": Counter(),
        "token_2_operation_status": Counter(),
        "token_3_family_status": Counter(),
        "token_4_provider_verb_status": Counter(),
    }

    token_groups_multi_token = defaultdict(int)
    token_groups_total = defaultdict(int)
    token_groups_len_ge_3 = defaultdict(int)
    token_groups_len_ge = {
        2: defaultdict(int),
        3: defaultdict(int),
        5: defaultdict(int),
        10: defaultdict(int),
    }

    start_no_terminal = 0
    terminal_no_start = 0
    multiple_terminal_states = 0
    start_to_success = 0
    start_to_failure = 0
    start_to_other = 0

    start_no_terminal_ids: List[str] = []
    multi_terminal_ids: List[str] = []

    current_id: Optional[str] = None
    group_rows: List[Tuple[Any, ...]] = []

    ordered = db.execute(
        """
        SELECT correlation_id, timestamp_epoch, row_id,
               operation, activity_status, outcome_class,
               token_a, token_b,
               (operation_family || '|' || activity_status) AS token3,
               (provider || '|' || action_verb || '|' || activity_status) AS token4
        FROM events
        WHERE correlation_id <> ''
        ORDER BY correlation_id, timestamp_epoch, row_id
        """
    )

    def finalize_corr_group(corr_id: str, rows_local: List[Tuple[Any, ...]]) -> None:
        nonlocal start_no_terminal, terminal_no_start, multiple_terminal_states
        nonlocal start_to_success, start_to_failure, start_to_other

        if not rows_local:
            return

        status_seq = []
        full_seq = []
        t1, t2, t3, t4 = [], [], [], []

        first_start_idx = None
        terminal_states: List[str] = []

        for i, (_cid, _ts, _rid, op, astatus, outcome, tok_a, tok_b, tok3, tok4) in enumerate(rows_local):
            st = (astatus or "").strip()
            oc = (outcome or "").strip()
            status_seq.append(st if st else "<blank>")
            full_seq.append((tok_b or "<blank>").strip())
            t1.append((tok_a or "<blank>").strip())
            t2.append((tok_b or "<blank>").strip())
            t3.append((tok3 or "<blank>").strip())
            t4.append((tok4 or "<blank>").strip())

            if st.lower() == "start" and first_start_idx is None:
                first_start_idx = i
            if oc in {"success", "failure", "other_terminal"}:
                terminal_states.append(oc)

        has_start = first_start_idx is not None
        has_terminal = len(terminal_states) > 0

        if has_start and not has_terminal:
            start_no_terminal += 1
            if len(start_no_terminal_ids) < 200:
                start_no_terminal_ids.append(corr_id)
        if has_terminal and not has_start:
            terminal_no_start += 1

        terminal_set = set(terminal_states)
        if len(terminal_set) > 1:
            multiple_terminal_states += 1
            if len(multi_terminal_ids) < 200:
                multi_terminal_ids.append(corr_id)

        if has_start:
            after = [
                (rows_local[j][5] or "").strip()
                for j in range(first_start_idx + 1, len(rows_local))
                if (rows_local[j][5] or "").strip() in {"success", "failure", "other_terminal"}
            ]
            if after:
                if "success" in after:
                    start_to_success += 1
                elif "failure" in after:
                    start_to_failure += 1
                else:
                    start_to_other += 1

        status_seq_key = " > ".join(status_seq)
        full_seq_key = " > ".join(full_seq)
        seq_status_counter[status_seq_key] += 1
        seq_full_counter[full_seq_key] += 1

        token_map = {
            "token_1_operation": t1,
            "token_2_operation_status": t2,
            "token_3_family_status": t3,
            "token_4_provider_verb_status": t4,
        }
        for tk, seq in token_map.items():
            seq_key = " > ".join(seq)
            token_seq_counters[tk][seq_key] += 1
            token_event_counters[tk].update(seq)
            token_groups_total[tk] += 1
            if len(set(seq)) > 1:
                token_groups_multi_token[tk] += 1
            if len(seq) >= 3:
                token_groups_len_ge_3[tk] += 1
            for w in (2, 3, 5, 10):
                if len(seq) >= (w + 1):
                    token_groups_len_ge[w][tk] += 1

    processed = 0
    for r in ordered:
        cid = str(r[0])
        if current_id is None:
            current_id = cid
        if cid != current_id:
            finalize_corr_group(current_id, group_rows)
            group_rows = []
            current_id = cid
        group_rows.append(r)
        processed += 1
        if processed % 250000 == 0:
            logger.info("Phase B sequence pass processed %d rows", processed)

    if current_id is not None and group_rows:
        finalize_corr_group(current_id, group_rows)

    tokenization_metrics: Dict[str, Any] = {}
    for tk in token_seq_counters:
        seq_counter = token_seq_counters[tk]
        evt_counter = token_event_counters[tk]
        total_groups = token_groups_total[tk]
        tokenization_metrics[tk] = {
            "vocabulary_size": len(evt_counter),
            "unique_sequence_count": len(seq_counter),
            "top_1_sequence_coverage": top_n_coverage(seq_counter, 1),
            "top_5_sequence_coverage": top_n_coverage(seq_counter, 5),
            "top_10_sequence_coverage": top_n_coverage(seq_counter, 10),
            "entropy_bits": entropy_from_counts(evt_counter),
            "pct_groups_multi_unique_token": pct(token_groups_multi_token[tk], total_groups),
            "pct_groups_len_ge_3": pct(token_groups_len_ge_3[tk], total_groups),
            "usable_window_2_pct": pct(token_groups_len_ge[2][tk], total_groups),
            "usable_window_3_pct": pct(token_groups_len_ge[3][tk], total_groups),
            "usable_window_5_pct": pct(token_groups_len_ge[5][tk], total_groups),
            "usable_window_10_pct": pct(token_groups_len_ge[10][tk], total_groups),
            "group_denominator": total_groups,
        }

    out = {
        "distinct_correlation_ids_exact": group_count,
        "singleton_groups": bins["1"],
        "singleton_groups_pct": pct(bins["1"], group_count),
        "group_length_buckets": {
            "2": {"count": bins["2"], "pct": pct(bins["2"], group_count)},
            "3": {"count": bins["3"], "pct": pct(bins["3"], group_count)},
            "4": {"count": bins["4"], "pct": pct(bins["4"], group_count)},
            "5_9": {"count": bins["5_9"], "pct": pct(bins["5_9"], group_count)},
            "10_19": {"count": bins["10_19"], "pct": pct(bins["10_19"], group_count)},
            "20_plus": {"count": bins["20_plus"], "pct": pct(bins["20_plus"], group_count)},
        },
        "group_size_stats": {
            "min": min(size_values) if size_values else 0,
            "mean": (sum(size_values) / len(size_values)) if size_values else 0,
            "median": percentile([float(v) for v in size_values], 0.5),
            "p75": percentile([float(v) for v in size_values], 0.75),
            "p90": percentile([float(v) for v in size_values], 0.9),
            "p95": percentile([float(v) for v in size_values], 0.95),
            "p99": percentile([float(v) for v in size_values], 0.99),
            "max": max(size_values) if size_values else 0,
        },
        "group_duration_seconds_stats": {
            "min": min(duration_values) if duration_values else 0,
            "mean": (sum(duration_values) / len(duration_values)) if duration_values else 0,
            "median": percentile(duration_values, 0.5),
            "p75": percentile(duration_values, 0.75),
            "p90": percentile(duration_values, 0.9),
            "p95": percentile(duration_values, 0.95),
            "p99": percentile(duration_values, 0.99),
            "max": max(duration_values) if duration_values else 0,
        },
        "group_duration_buckets": {
            "lt_1s": {"count": dur_bins["lt_1s"], "pct": pct(dur_bins["lt_1s"], group_count)},
            "1_10s": {"count": dur_bins["1_10s"], "pct": pct(dur_bins["1_10s"], group_count)},
            "10_60s": {"count": dur_bins["10_60s"], "pct": pct(dur_bins["10_60s"], group_count)},
            "1_10m": {"count": dur_bins["1_10m"], "pct": pct(dur_bins["1_10m"], group_count)},
            "gt_10m": {"count": dur_bins["gt_10m"], "pct": pct(dur_bins["gt_10m"], group_count)},
        },
        "multi_dimension_groups": {
            "multiple_callers": {"count": multi_caller, "pct": pct(multi_caller, group_count)},
            "multiple_operations": {"count": multi_operation, "pct": pct(multi_operation, group_count)},
            "multiple_subscriptions": {"count": multi_subscription, "pct": pct(multi_subscription, group_count)},
            "multiple_resource_entities": {"count": multi_resource_entity, "pct": pct(multi_resource_entity, group_count)},
            "multiple_resource_groups": {"count": multi_resource_group, "pct": pct(multi_resource_group, group_count)},
        },
        "lifecycle_patterns": {
            "start_no_terminal": {"count": start_no_terminal, "pct": pct(start_no_terminal, group_count)},
            "terminal_no_start": {"count": terminal_no_start, "pct": pct(terminal_no_start, group_count)},
            "multiple_terminal_states": {"count": multiple_terminal_states, "pct": pct(multiple_terminal_states, group_count)},
            "start_to_success": {"count": start_to_success, "pct": pct(start_to_success, group_count)},
            "start_to_failure": {"count": start_to_failure, "pct": pct(start_to_failure, group_count)},
            "start_to_other": {"count": start_to_other, "pct": pct(start_to_other, group_count)},
        },
        "tokenization_metrics": tokenization_metrics,
        "hypothesis_test": {
            "statement": "Most CorrelationId groups represent one Azure operation lifecycle rather than broader behavioral sessions.",
            "supporting_signals": {
                "singleton_pct": pct(bins["1"], group_count),
                "groups_with_multiple_operations_pct": pct(multi_operation, group_count),
                "groups_with_multiple_callers_pct": pct(multi_caller, group_count),
                "start_to_success_or_failure_pct": pct(start_to_success + start_to_failure, group_count),
            },
            "interpretation": "See sequence_viability_report.md for final supported conclusion using these exact metrics.",
        },
        "internal_example_candidate_ids": {
            "start_no_terminal_ids": start_no_terminal_ids,
            "multiple_terminal_ids": multi_terminal_ids,
            "group_sizes": group_sizes,
        },
    }

    pattern_rows: List[Dict[str, Any]] = []
    for seq, c in seq_status_counter.most_common(50):
        pattern_rows.append({"sequence_type": "normalized_status", "sequence": seq, "count": c})
    for seq, c in seq_full_counter.most_common(50):
        pattern_rows.append({"sequence_type": "full_event", "sequence": seq, "count": c})

    return out, pattern_rows


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def analyze_callers(db: DBEngine, total_rows: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    base_rows = db.query_all(
        """
        SELECT
            caller,
            COUNT(*) AS total,
            COUNT(DISTINCT event_date) AS active_days,
            COUNT(DISTINCT operation) AS distinct_operations,
            COUNT(DISTINCT operation_family) AS distinct_operation_families,
            COUNT(DISTINCT provider) AS distinct_providers,
            COUNT(DISTINCT subscription) AS distinct_subscriptions,
            COUNT(DISTINCT resource_group) AS distinct_resource_groups,
            COUNT(DISTINCT resource_type) AS distinct_resource_types,
            COUNT(DISTINCT caller_ip) AS distinct_caller_ips,
            SUM(CASE WHEN outcome_class='success' THEN 1 ELSE 0 END) AS success_count,
            SUM(CASE WHEN outcome_class='failure' THEN 1 ELSE 0 END) AS failure_count,
            SUM(CASE WHEN level='Warning' THEN 1 ELSE 0 END) AS warning_count,
            SUM(CASE WHEN level='Error' THEN 1 ELSE 0 END) AS error_count,
            COUNT(DISTINCT identity_type) AS identity_type_distinct,
            COUNT(DISTINCT application_id) AS application_id_distinct,
            MAX(identity_type) AS sample_identity_type,
            MAX(application_id) AS sample_application_id,
            MAX(identity_object_id) AS sample_object_id,
            MAX(identity_provider) AS sample_identity_provider,
            MAX(managed_identity_resource) AS sample_managed_identity,
            SUM(CASE WHEN managed_identity_resource<>'' OR managed_identity_alt_resource<>'' THEN 1 ELSE 0 END) AS managed_identity_rows
        FROM events
        GROUP BY caller
        """
    )

    hourly_rows = db.query_all(
        """
        SELECT caller, event_date, event_hour, COUNT(*) AS cnt
        FROM events
        GROUP BY caller, event_date, event_hour
        """
    )
    per_caller_hourly: Dict[str, List[int]] = defaultdict(list)
    for caller, _d, _h, cnt in hourly_rows:
        per_caller_hourly[str(caller)].append(int(cnt))

    out_rows: List[Dict[str, Any]] = []
    counts_sorted: List[int] = []

    for r in base_rows:
        (
            caller,
            total,
            active_days,
            distinct_operations,
            distinct_operation_families,
            distinct_providers,
            distinct_subscriptions,
            distinct_resource_groups,
            distinct_resource_types,
            distinct_caller_ips,
            success_count,
            failure_count,
            warning_count,
            error_count,
            _identity_type_distinct,
            appid_distinct,
            sample_idtyp,
            sample_appid,
            sample_oid,
            sample_idp,
            sample_mirid,
            managed_identity_rows,
        ) = r

        caller_s = str(caller)
        total_i = int(total)
        counts_sorted.append(total_i)
        hourly = per_caller_hourly.get(caller_s, [])

        identity_class = classify_identity(
            str(sample_idtyp or ""),
            str(sample_appid or ""),
            str(sample_mirid or ""),
            str(sample_idp or ""),
        )

        out_rows.append(
            {
                "caller": caller_s,
                "total_rows": total_i,
                "active_days": int(active_days),
                "distinct_operations": int(distinct_operations),
                "distinct_operation_families": int(distinct_operation_families),
                "distinct_providers": int(distinct_providers),
                "distinct_subscriptions": int(distinct_subscriptions),
                "distinct_resource_groups": int(distinct_resource_groups),
                "distinct_resource_types": int(distinct_resource_types),
                "distinct_caller_ips": int(distinct_caller_ips),
                "success_rate": float(success_count) / total_i if total_i else 0.0,
                "failure_rate": float(failure_count) / total_i if total_i else 0.0,
                "warning_rate": float(warning_count) / total_i if total_i else 0.0,
                "error_rate": float(error_count) / total_i if total_i else 0.0,
                "events_per_hour_mean": (sum(hourly) / len(hourly)) if hourly else 0.0,
                "events_per_hour_p95": percentile([float(v) for v in hourly], 0.95) if hourly else 0.0,
                "dataset_volume_share": (total_i / total_rows) if total_rows else 0.0,
                "identity_type_claim": str(sample_idtyp or ""),
                "identity_classification": identity_class,
                "application_id": str(sample_appid or ""),
                "application_id_consistency": "single" if int(appid_distinct) <= 1 else "multiple",
                "identity_object_id": str(sample_oid or ""),
                "managed_identity_evidence": "yes" if int(managed_identity_rows) > 0 else "no",
            }
        )

    out_rows.sort(key=lambda x: int(x["total_rows"]), reverse=True)

    shares = [c / total_rows for c in sorted(counts_sorted, reverse=True)] if total_rows else []
    top1 = sum(shares[:1])
    top5 = sum(shares[:5])
    top10 = sum(shares[:10])
    top20 = sum(shares[:20])
    hhi = sum(s * s for s in shares)

    concentration = {
        "total_callers": len(out_rows),
        "share_top_1": top1,
        "share_top_5": top5,
        "share_top_10": top10,
        "share_top_20": top20,
        "hhi_fraction": hhi,
        "hhi_10000_scale": hhi * 10000,
        "callers_lt_10_events": sum(1 for c in counts_sorted if c < 10),
        "callers_lt_100_events": sum(1 for c in counts_sorted if c < 100),
        "callers_lt_1000_events": sum(1 for c in counts_sorted if c < 1000),
        "callers_lt_10000_events": sum(1 for c in counts_sorted if c < 10000),
        "event_denominator": total_rows,
    }

    return out_rows, concentration


class SessionTracker:
    def __init__(self, threshold_seconds: int):
        self.threshold_seconds = threshold_seconds
        self.total_sessions = 0
        self.singleton_sessions = 0
        self.lengths: List[int] = []
        self.durations: List[float] = []
        self.concurrent_corr: List[int] = []
        self.cross_sub = 0
        self.cross_rg = 0
        self.cross_provider = 0
        self.sensitive_sessions = 0

        self.usable = {2: 0, 3: 0, 5: 0, 10: 0}

        self.vocab = {"A": set(), "B": set(), "C": set(), "D": set(), "E": set()}
        self.seq_counters = {
            "A": Counter(),
            "B": Counter(),
            "C": Counter(),
            "D": Counter(),
            "E": Counter(),
        }

        self._current_key: Optional[Tuple[str, ...]] = None
        self._start_ts: Optional[float] = None
        self._last_ts: Optional[float] = None
        self._len = 0
        self._subs: set[str] = set()
        self._rgs: set[str] = set()
        self._providers: set[str] = set()
        self._corrs: set[str] = set()
        self._sensitive = False
        self._tokens = {"A": [], "B": [], "C": [], "D": [], "E": []}

        self.example_sessions: List[Tuple[Tuple[str, ...], float, float, str]] = []
        self.sensitive_example_sessions: List[Tuple[Tuple[str, ...], float, float, str]] = []

    def _finalize(self) -> None:
        if self._current_key is None or self._len == 0:
            return

        self.total_sessions += 1
        self.lengths.append(self._len)
        dur = max(0.0, (self._last_ts or 0.0) - (self._start_ts or 0.0))
        self.durations.append(dur)

        if self._len == 1:
            self.singleton_sessions += 1
        for w in (2, 3, 5, 10):
            if self._len >= (w + 1):
                self.usable[w] += 1

        if len(self._subs) > 1:
            self.cross_sub += 1
        if len(self._rgs) > 1:
            self.cross_rg += 1
        if len(self._providers) > 1:
            self.cross_provider += 1

        corr_count = len([c for c in self._corrs if c])
        self.concurrent_corr.append(corr_count)

        if self._sensitive:
            self.sensitive_sessions += 1

        for tk in ("A", "B", "C", "D", "E"):
            seq = self._tokens[tk]
            self.vocab[tk].update(seq)
            key = " > ".join(seq)
            self.seq_counters[tk][key] += 1

        label = f"session_{self.threshold_seconds}s"
        if len(self.example_sessions) < 6:
            self.example_sessions.append((self._current_key, self._start_ts or 0.0, self._last_ts or 0.0, label))
        if self._sensitive and len(self.sensitive_example_sessions) < 6:
            self.sensitive_example_sessions.append((self._current_key, self._start_ts or 0.0, self._last_ts or 0.0, f"sensitive_{label}"))

        self._current_key = None
        self._start_ts = None
        self._last_ts = None
        self._len = 0
        self._subs.clear()
        self._rgs.clear()
        self._providers.clear()
        self._corrs.clear()
        self._sensitive = False
        self._tokens = {"A": [], "B": [], "C": [], "D": [], "E": []}

    def consume(
        self,
        key: Tuple[str, ...],
        ts: float,
        subscription: str,
        resource_group: str,
        provider: str,
        correlation_id: str,
        sensitive_action: int,
        token_a: str,
        token_b: str,
        token_c: str,
        token_d: str,
        token_e: str,
    ) -> None:
        if self._current_key is None:
            self._current_key = key
            self._start_ts = ts
            self._last_ts = ts
        else:
            if key != self._current_key:
                self._finalize()
                self._current_key = key
                self._start_ts = ts
                self._last_ts = ts
            elif ts - (self._last_ts or ts) > self.threshold_seconds:
                self._finalize()
                self._current_key = key
                self._start_ts = ts
                self._last_ts = ts
            else:
                self._last_ts = ts

        self._len += 1
        self._subs.add(subscription)
        self._rgs.add(resource_group)
        self._providers.add(provider)
        self._corrs.add(correlation_id)
        self._sensitive = self._sensitive or bool(sensitive_action)

        self._tokens["A"].append(token_a or "<blank>")
        self._tokens["B"].append(token_b or "<blank>")
        self._tokens["C"].append(token_c or "<blank>")
        self._tokens["D"].append(token_d or "<blank>")
        self._tokens["E"].append(token_e or "<blank>")

    def close(self) -> None:
        self._finalize()


def analyze_sessionization(db: DBEngine) -> Tuple[List[Dict[str, Any]], Dict[str, List[Tuple[Tuple[str, ...], float, float, str]]]]:
    scopes = {
        "caller": ["caller"],
        "caller_subscription": ["caller", "subscription"],
        "caller_resource_group": ["caller", "resource_group"],
        "caller_ip": ["caller", "caller_ip"],
    }
    thresholds = [300, 900, 1800, 3600]

    out_rows: List[Dict[str, Any]] = []
    internal_examples: Dict[str, List[Tuple[Tuple[str, ...], float, float, str]]] = defaultdict(list)

    for scope_name, cols in scopes.items():
        order_cols = ", ".join(cols + ["timestamp_epoch", "row_id"])
        select_cols = ", ".join(cols)

        trackers = {th: SessionTracker(th) for th in thresholds}

        sql = f"""
            SELECT {select_cols}, timestamp_epoch, subscription, resource_group, provider,
                   correlation_id, sensitive_action, token_a, token_b, token_c, token_d, token_e
            FROM events
            WHERE timestamp_epoch IS NOT NULL
            ORDER BY {order_cols}
        """

        processed_rows = 0
        for r in db.execute(sql):
            key = tuple(str(v or "") for v in r[: len(cols)])
            pos = len(cols)
            ts = float(r[pos])
            subscription = str(r[pos + 1] or "")
            resource_group = str(r[pos + 2] or "")
            provider = str(r[pos + 3] or "")
            correlation_id = str(r[pos + 4] or "")
            sensitive_action = int(r[pos + 5] or 0)
            token_a = str(r[pos + 6] or "")
            token_b = str(r[pos + 7] or "")
            token_c = str(r[pos + 8] or "")
            token_d = str(r[pos + 9] or "")
            token_e = str(r[pos + 10] or "")

            for th in thresholds:
                trackers[th].consume(
                    key,
                    ts,
                    subscription,
                    resource_group,
                    provider,
                    correlation_id,
                    sensitive_action,
                    token_a,
                    token_b,
                    token_c,
                    token_d,
                    token_e,
                )
            processed_rows += 1
            if processed_rows % 300000 == 0:
                logger.info(
                    "Phase D sessionization scope '%s' processed %d rows",
                    scope_name,
                    processed_rows,
                )

        for th in thresholds:
            t = trackers[th]
            t.close()

            total = t.total_sessions
            row = {
                "scope": scope_name,
                "threshold_minutes": int(th / 60),
                "total_sessions": total,
                "singleton_session_pct": pct(t.singleton_sessions, total),
                "session_length_p50": percentile([float(v) for v in t.lengths], 0.5),
                "session_length_p95": percentile([float(v) for v in t.lengths], 0.95),
                "session_length_p99": percentile([float(v) for v in t.lengths], 0.99),
                "session_duration_seconds_p50": percentile(t.durations, 0.5),
                "session_duration_seconds_p95": percentile(t.durations, 0.95),
                "usable_window_2_pct": pct(t.usable[2], total),
                "usable_window_3_pct": pct(t.usable[3], total),
                "usable_window_5_pct": pct(t.usable[5], total),
                "usable_window_10_pct": pct(t.usable[10], total),
                "concurrent_correlation_median": percentile([float(v) for v in t.concurrent_corr], 0.5),
                "concurrent_correlation_p95": percentile([float(v) for v in t.concurrent_corr], 0.95),
                "cross_subscription_pct": pct(t.cross_sub, total),
                "cross_resource_group_pct": pct(t.cross_rg, total),
                "cross_provider_pct": pct(t.cross_provider, total),
                "sensitive_action_session_pct": pct(t.sensitive_sessions, total),
            }

            for tk in ("A", "B", "C", "D", "E"):
                seq_counter = t.seq_counters[tk]
                row[f"token_{tk}_vocab_size"] = len(t.vocab[tk])
                row[f"token_{tk}_unique_sequence_count"] = len(seq_counter)
                row[f"token_{tk}_top1_sequence_coverage"] = top_n_coverage(seq_counter, 1)
                row[f"token_{tk}_top5_sequence_coverage"] = top_n_coverage(seq_counter, 5)
                row[f"token_{tk}_top10_sequence_coverage"] = top_n_coverage(seq_counter, 10)

            out_rows.append(row)
            internal_examples[f"{scope_name}_{int(th/60)}m"].extend(t.example_sessions)
            internal_examples[f"{scope_name}_{int(th/60)}m_sensitive"].extend(t.sensitive_example_sessions)

    return out_rows, internal_examples


def analyze_resources(db: DBEngine) -> Dict[str, Any]:
    total_rows = int(db.query_all("SELECT COUNT(*) FROM events")[0][0])
    non_blank_resource = int(
        db.query_all("SELECT COUNT(*) FROM events WHERE TRIM(COALESCE(resource_entity,'')) <> ''")[0][0]
    )
    distinct_resource = int(
        db.query_all("SELECT COUNT(DISTINCT resource_entity) FROM events WHERE TRIM(COALESCE(resource_entity,'')) <> ''")[0][0]
    )

    rr = db.query_all(
        """
        SELECT resource_entity, COUNT(*) AS n,
               COUNT(DISTINCT operation) AS ops,
               COUNT(DISTINCT caller) AS callers
        FROM events
        WHERE TRIM(COALESCE(resource_entity,'')) <> ''
        GROUP BY resource_entity
        """
    )

    rows_per_resource = [int(r[1]) for r in rr]
    ops_per_resource = [int(r[2]) for r in rr]
    callers_per_resource = [int(r[3]) for r in rr]

    # Resource identity stability within CorrelationId lifecycle groups.
    stable_rows = db.query_all(
        """
        SELECT correlation_id,
               COUNT(DISTINCT resource_entity) AS d_resource,
               SUM(CASE WHEN activity_status='Start' THEN 1 ELSE 0 END) AS starts,
               SUM(CASE WHEN outcome_class IN ('success','failure','other_terminal') THEN 1 ELSE 0 END) AS terminals
        FROM events
        WHERE correlation_id <> ''
        GROUP BY correlation_id
        HAVING starts > 0 AND terminals > 0
        """
    )
    stable_groups = len(stable_rows)
    stable_single_resource = sum(1 for _cid, d_res, _s, _t in stable_rows if int(d_res) <= 1)

    compare_defs = {}
    compare_sql = {
        "resource_entity": "resource_entity",
        "resource_type": "resource_type",
        "resource_group": "resource_group",
        "subscription_plus_resource_type": "(subscription || '|' || resource_type)",
    }
    for name, expr in compare_sql.items():
        qr = db.query_all(
            f"""
            SELECT {expr} AS k, COUNT(*) AS n
            FROM events
            WHERE TRIM(COALESCE({expr},'')) <> ''
            GROUP BY k
            """
        )
        counts = [int(x[1]) for x in qr]
        compare_defs[name] = {
            "group_count": len(counts),
            "rows_per_group_mean": (sum(counts) / len(counts)) if counts else 0,
            "rows_per_group_median": percentile([float(v) for v in counts], 0.5) if counts else 0,
            "rows_per_group_p95": percentile([float(v) for v in counts], 0.95) if counts else 0,
            "groups_with_ge_3_rows_pct": pct(sum(1 for v in counts if v >= 3), len(counts)) if counts else 0,
        }

    return {
        "resource_entity_completeness": {
            "non_blank_rows": non_blank_resource,
            "total_rows": total_rows,
            "non_blank_pct": pct(non_blank_resource, total_rows),
        },
        "resource_entity_cardinality": distinct_resource,
        "resource_entity_rows_per_resource": {
            "mean": (sum(rows_per_resource) / len(rows_per_resource)) if rows_per_resource else 0,
            "median": percentile([float(v) for v in rows_per_resource], 0.5) if rows_per_resource else 0,
            "p95": percentile([float(v) for v in rows_per_resource], 0.95) if rows_per_resource else 0,
        },
        "operations_per_resource": {
            "mean": (sum(ops_per_resource) / len(ops_per_resource)) if ops_per_resource else 0,
            "median": percentile([float(v) for v in ops_per_resource], 0.5) if ops_per_resource else 0,
            "p95": percentile([float(v) for v in ops_per_resource], 0.95) if ops_per_resource else 0,
        },
        "callers_per_resource": {
            "mean": (sum(callers_per_resource) / len(callers_per_resource)) if callers_per_resource else 0,
            "median": percentile([float(v) for v in callers_per_resource], 0.5) if callers_per_resource else 0,
            "p95": percentile([float(v) for v in callers_per_resource], 0.95) if callers_per_resource else 0,
        },
        "resource_identity_stability_start_terminal": {
            "groups_with_start_and_terminal": stable_groups,
            "single_resource_entity_groups": stable_single_resource,
            "single_resource_entity_pct": pct(stable_single_resource, stable_groups),
        },
        "comparison_definitions": compare_defs,
    }


def analyze_tokens(db: DBEngine) -> List[Dict[str, Any]]:
    token_map = {
        "Token A": "token_a",
        "Token B": "token_b",
        "Token C": "token_c",
        "Token D": "token_d",
        "Token E": "token_e",
    }

    total_rows = int(db.query_all("SELECT COUNT(*) FROM events")[0][0])

    out: List[Dict[str, Any]] = []
    for label, col in token_map.items():
        freq_rows = db.query_all(
            f"""
            SELECT {col} AS tok, COUNT(*) AS cnt
            FROM events
            GROUP BY tok
            """
        )
        freq = Counter({str(tok or ""): int(cnt) for tok, cnt in freq_rows})
        missing = freq.get("", 0)
        if "" in freq:
            del freq[""]

        total_non_missing = sum(freq.values())
        rare_event_share_1 = sum(c for c in freq.values() if c <= 1) / total_non_missing if total_non_missing else 0.0
        rare_event_share_5 = sum(c for c in freq.values() if c <= 5) / total_non_missing if total_non_missing else 0.0
        rare_event_share_10 = sum(c for c in freq.values() if c <= 10) / total_non_missing if total_non_missing else 0.0
        rare_event_share_100 = sum(c for c in freq.values() if c <= 100) / total_non_missing if total_non_missing else 0.0

        if label in {"Token B", "Token D"}:
            target_note = "Includes activity status; target becomes operation-lifecycle prediction, not pure operation prediction."
            trivial_risk = "higher"
        else:
            target_note = "Does not directly encode status outcome."
            trivial_risk = "lower"

        interpretability = {
            "Token A": "High (direct operation names, but can be verbose).",
            "Token B": "High for lifecycle investigations; medium for pure behavior profiling.",
            "Token C": "Medium-high (provider + family + verb abstraction).",
            "Token D": "Medium-high, but outcome leakage risk is elevated.",
            "Token E": "Medium (adds category context while avoiding direct outcome status).",
        }[label]

        out.append(
            {
                "token_design": label,
                "column_used": col,
                "vocabulary_size": len(freq),
                "missing_rate": missing / total_rows if total_rows else 0.0,
                "top1_coverage": top_n_coverage(freq, 1),
                "top5_coverage": top_n_coverage(freq, 5),
                "top10_coverage": top_n_coverage(freq, 10),
                "top20_coverage": top_n_coverage(freq, 20),
                "rare_event_share_le_1": rare_event_share_1,
                "rare_event_share_le_5": rare_event_share_5,
                "rare_event_share_le_10": rare_event_share_10,
                "rare_event_share_le_100": rare_event_share_100,
                "entropy_bits": entropy_from_counts(freq),
                "next_event_prediction_suitability": "good" if len(freq) < 5000 else "challenging",
                "trivial_prediction_risk": trivial_risk,
                "outcome_encoding_note": target_note,
                "analyst_interpretability": interpretability,
            }
        )

    return out


def split_bounds(db: DBEngine) -> Tuple[float, float, float]:
    min_ts, max_ts = db.query_all("SELECT MIN(timestamp_epoch), MAX(timestamp_epoch) FROM events WHERE timestamp_epoch IS NOT NULL")[0]
    mn = float(min_ts)
    mx = float(max_ts)
    span = mx - mn
    b1 = mn + 0.70 * span
    b2 = mn + 0.85 * span
    return mn, b1, b2


def count_distinct_in_period(db: DBEngine, col: str, where_clause: str, params: Sequence[Any]) -> set[str]:
    rows = db.query_all(f"SELECT DISTINCT {col} FROM events WHERE {where_clause}", params)
    return {str(r[0] or "") for r in rows if str(r[0] or "") != ""}


def value_distribution(db: DBEngine, col: str, where_clause: str, params: Sequence[Any], topk: int = 200) -> Dict[str, int]:
    rows = db.query_all(
        f"""
        SELECT {col} AS v, COUNT(*) AS c
        FROM events
        WHERE {where_clause}
        GROUP BY v
        ORDER BY c DESC
        LIMIT {topk}
        """,
        params,
    )
    return {str(v or ""): int(c) for v, c in rows}


def tvd(d1: Dict[str, int], d2: Dict[str, int]) -> float:
    k = set(d1.keys()) | set(d2.keys())
    s1 = sum(d1.values())
    s2 = sum(d2.values())
    if s1 == 0 or s2 == 0:
        return 0.0
    return 0.5 * sum(abs((d1.get(x, 0) / s1) - (d2.get(x, 0) / s2)) for x in k)


def analyze_time_splits(db: DBEngine) -> Dict[str, Any]:
    mn, b1, b2 = split_bounds(db)

    train_where = "timestamp_epoch >= ? AND timestamp_epoch < ?"
    val_where = "timestamp_epoch >= ? AND timestamp_epoch < ?"
    test_where = "timestamp_epoch >= ?"

    token_defs = {
        "lifecycle_correlation_token_d": "token_d",
        "actor_behavior_token_c": "token_c",
    }

    result = {
        "split_strategy": {
            "method": "chronological_70_15_15_by_time_span",
            "train_start_epoch": mn,
            "validation_start_epoch": b1,
            "test_start_epoch": b2,
            "note": "Baseline training period is not assumed normal without security-team validation.",
        },
        "definitions": {},
    }

    train_callers = count_distinct_in_period(db, "caller", train_where, [mn, b1])
    val_callers = count_distinct_in_period(db, "caller", val_where, [b1, b2])
    test_callers = count_distinct_in_period(db, "caller", test_where, [b2])

    train_resources = count_distinct_in_period(db, "resource_entity", train_where + " AND resource_entity<>''", [mn, b1])
    val_resources = count_distinct_in_period(db, "resource_entity", val_where + " AND resource_entity<>''", [b1, b2])
    test_resources = count_distinct_in_period(db, "resource_entity", test_where + " AND resource_entity<>''", [b2])

    drift_cols = ["operation", "provider", "caller", "activity_status", "resource_group"]
    drift = {}
    for col in drift_cols:
        d_train = value_distribution(db, col, train_where, [mn, b1])
        d_test = value_distribution(db, col, test_where, [b2])
        drift[col] = {"tvd_train_vs_test_topk": tvd(d_train, d_test)}

    for def_name, token_col in token_defs.items():
        train_tokens = count_distinct_in_period(db, token_col, train_where + f" AND {token_col}<>''", [mn, b1])
        val_tokens = count_distinct_in_period(db, token_col, val_where + f" AND {token_col}<>''", [b1, b2])
        test_tokens = count_distinct_in_period(db, token_col, test_where + f" AND {token_col}<>''", [b2])

        val_unseen = {t for t in val_tokens if t not in train_tokens}
        test_unseen = {t for t in test_tokens if t not in train_tokens}

        train_n = int(db.query_all(f"SELECT COUNT(*) FROM events WHERE {train_where}", [mn, b1])[0][0])
        val_n = int(db.query_all(f"SELECT COUNT(*) FROM events WHERE {val_where}", [b1, b2])[0][0])
        test_n = int(db.query_all(f"SELECT COUNT(*) FROM events WHERE {test_where}", [b2])[0][0])

        corr_train = int(
            db.query_all(
                "SELECT COUNT(DISTINCT correlation_id) FROM events WHERE " + train_where + " AND correlation_id<>''",
                [mn, b1],
            )[0][0]
        )
        corr_val = int(
            db.query_all(
                "SELECT COUNT(DISTINCT correlation_id) FROM events WHERE " + val_where + " AND correlation_id<>''",
                [b1, b2],
            )[0][0]
        )
        corr_test = int(
            db.query_all(
                "SELECT COUNT(DISTINCT correlation_id) FROM events WHERE " + test_where + " AND correlation_id<>''",
                [b2],
            )[0][0]
        )

        result["definitions"][def_name] = {
            "token_column": token_col,
            "event_counts": {"train": train_n, "validation": val_n, "test": test_n},
            "sequence_proxy_counts_correlation_groups": {
                "train": corr_train,
                "validation": corr_val,
                "test": corr_test,
            },
            "vocabulary": {
                "train": len(train_tokens),
                "validation": len(val_tokens),
                "test": len(test_tokens),
                "validation_unseen_tokens": len(val_unseen),
                "test_unseen_tokens": len(test_unseen),
                "validation_unseen_rate": (len(val_unseen) / len(val_tokens)) if val_tokens else 0.0,
                "test_unseen_rate": (len(test_unseen) / len(test_tokens)) if test_tokens else 0.0,
            },
            "caller_coverage": {
                "train": len(train_callers),
                "validation": len(val_callers),
                "test": len(test_callers),
                "validation_unseen_rate": (len([c for c in val_callers if c not in train_callers]) / len(val_callers))
                if val_callers
                else 0.0,
                "test_unseen_rate": (len([c for c in test_callers if c not in train_callers]) / len(test_callers))
                if test_callers
                else 0.0,
            },
            "resource_coverage": {
                "train": len(train_resources),
                "validation": len(val_resources),
                "test": len(test_resources),
                "validation_unseen_rate": (len([r for r in val_resources if r not in train_resources]) / len(val_resources))
                if val_resources
                else 0.0,
                "test_unseen_rate": (len([r for r in test_resources if r not in train_resources]) / len(test_resources))
                if test_resources
                else 0.0,
            },
            "distribution_drift": drift,
        }

    return result


def write_markdown_evaluation(path: Path) -> None:
    content = """# Evaluation Strategy

## Weak-Signal Inventory

| Signal | Classification | Notes |
|---|---|---|
| Level | event outcome | Operational severity level, not confirmed anomaly ground truth. |
| activityStatusValue | event outcome | Lifecycle state; useful context and weak triage overlay only. |
| activitySubstatusValue | contextual feature | Supplementary status detail; not anomaly truth. |
| statusCode | contextual feature | API/operation result metadata; can indicate failure mode, not anomaly truth. |
| Sensitive action category | heuristic risk indicator | Useful prioritization signal for analyst review. |
| Unusual caller-operation pairing | possible weak label | Behavioral novelty indicator; noisy without analyst validation. |
| Unusual IP | possible weak label | Requires environment baseline context to reduce false positives. |
| Unusual resource-group access | possible weak label | Scope-based novelty indicator; not direct truth. |
| Unusual time-of-day | possible weak label | Behavioral context, high false-positive risk alone. |
| New operation for caller | possible weak label | Good exploratory marker; not proof of maliciousness. |
| Incident or analyst labels | valid ground truth | Currently unavailable in this dataset. |

## Level 1: Unsupervised Technical Evaluation

- Next-event prediction accuracy and top-k recall.
- Sequence cross-entropy/perplexity on chronological holdout.
- Anomaly score stability over time and under drift.
- Drift-aware monitoring by operation/provider/caller distributions.

## Level 2: Weak-Label Triage Evaluation

- Overlay weak signals (status, sensitive action, novelty markers) to measure triage utility.
- Report alert density: alerts/day and alerts per 10,000 events.
- Never treat weak signals as confirmed truth; use them as prioritization overlays.

## Level 3: Security Validation

- Security team reviews ranked alerts with documented dispositions.
- Track top-k analyst precision, false-positive burden, and repeat-alert suppression.
- Evaluate lead time and coverage across callers and operation families.

## Recommended Operational Metrics

- Alerts per day.
- Alerts per 10,000 events.
- Top-k analyst precision.
- Event-level detection rate.
- Session-level detection rate.
- False-positive burden.
- Lead time.
- Repeat-alert suppression rate.
- Coverage across callers and operation families.
"""
    path.write_text(content, encoding="utf-8")


def write_markdown_modeling(path: Path) -> None:
    content = """# Modeling Recommendation

## Candidate Methods Compared

1. Frequency rarity baseline.
2. Caller-operation rarity baseline.
3. Caller-resource novelty baseline.
4. N-gram next-event model.
5. Markov transition model.
6. DeepLog-style LSTM.
7. Tabular Isolation Forest (event-level context features).
8. Hybrid sequence-plus-context scorer.

## Recommended Implementation Order

1. **Caller-operation rarity + sensitive-action weighting**
   - Fast, interpretable, and robust for sparse 14-day history.
2. **Markov/n-gram transition baseline on sequence tokens**
   - Captures local order with lower data requirements than LSTM.
3. **Hybrid scorer (sequence likelihood + contextual novelty)**
   - Combines transition anomalies with caller/resource/IP novelty.
4. **DeepLog-style LSTM (modified target and evaluation plan)**
   - Proceed only after baseline calibration, token finalization, and security-team review workflow.

## Why LSTM Is Not First

- Only ~14 days of data and no validated anomaly labels.
- Observable lifecycle duplication within CorrelationId can make sequence prediction trivially easy if status is encoded in target token.
- Concentrated caller/resource usage requires careful baselineing to avoid excessive false positives.
- Security-team interpretability and operational alert volume control are prerequisites before a higher-complexity model.

## Practical Recommendation

Proceed with a two-layer design:
- Layer 1: operation-lifecycle modeling (CorrelationId-centric, lifecycle-aware token).
- Layer 2: actor-behavior modeling (caller session-centric, context-rich novelty).

Adopt LSTM only after these baseline layers demonstrate stable and reviewable alert behavior.
"""
    path.write_text(content, encoding="utf-8")


def write_sequence_viability_report(path: Path, corr: Dict[str, Any], sessions_csv: Path) -> None:
    singleton_pct = corr["singleton_groups_pct"]
    multi_ops_pct = corr["multi_dimension_groups"]["multiple_operations"]["pct"]
    start_pair_pct = corr["lifecycle_patterns"]["start_to_success"]["pct"] + corr["lifecycle_patterns"]["start_to_failure"]["pct"]

    conclusion = ""
    if singleton_pct > 50 and multi_ops_pct < 40:
        conclusion = (
            "Evidence supports that many CorrelationId groups are narrow lifecycle traces, often singletons or small operation-status chains, "
            "rather than broad actor sessions."
        )
    else:
        conclusion = (
            "CorrelationId groups show mixed behavior; a non-trivial subset forms broader multi-operation chains, so lifecycle-only framing is incomplete."
        )

    content = f"""# Sequence Viability Report

## Strongest CorrelationId Conclusion

- Exact CorrelationId metrics indicate: singleton_pct={singleton_pct:.2f}%, multiple_operations_pct={multi_ops_pct:.2f}%, start_to_success_or_failure_pct={start_pair_pct:.2f}%.
- Conclusion: {conclusion}

## Modeling Unit Guidance

- Use CorrelationId groups for operation-lifecycle modeling where lifecycle transitions are the explicit target.
- Use caller-centered time-bounded sessions for actor-behavior modeling where concurrent workflows and context shifts matter.

## Recommended Token Direction

- Lifecycle layer: Token D (`provider|operation_family|action_verb|activity_status`) when lifecycle prediction is intended.
- Actor-behavior layer: Token C (`provider|operation_family|action_verb`) to reduce outcome leakage.

## Baseline Before LSTM

- Start with caller-operation rarity + Markov/n-gram transition scorer.
- Introduce DeepLog-style LSTM only after baseline calibration and security-review integration.

## References

- Correlation statistics: correlation_group_statistics.json
- Session comparison table: {sessions_csv.name}
- Token comparison table: tokenization_comparison.csv
"""
    path.write_text(content, encoding="utf-8")


def build_internal_examples(
    db: DBEngine,
    corr_stats: Dict[str, Any],
    session_examples: Dict[str, List[Tuple[Tuple[str, ...], float, float, str]]],
) -> None:
    candidate = corr_stats.get("internal_example_candidate_ids", {})
    group_sizes: Dict[str, int] = candidate.get("group_sizes", {})
    start_no_terminal_ids: List[str] = candidate.get("start_no_terminal_ids", [])
    multi_terminal_ids: List[str] = candidate.get("multiple_terminal_ids", [])

    sorted_by_size = sorted(group_sizes.items(), key=lambda kv: kv[1], reverse=True)
    longest_ids = [cid for cid, _n in sorted_by_size[:10]]

    # Representative 20 by deterministic stratified draw over size buckets.
    buckets = defaultdict(list)
    for cid, n in group_sizes.items():
        if n == 1:
            b = "1"
        elif n <= 3:
            b = "2_3"
        elif n <= 9:
            b = "4_9"
        elif n <= 19:
            b = "10_19"
        else:
            b = "20_plus"
        buckets[b].append(cid)

    rng = random.Random(RANDOM_SEED)
    representative: List[str] = []
    for b in ["1", "2_3", "4_9", "10_19", "20_plus"]:
        ids = sorted(buckets[b])
        rng.shuffle(ids)
        representative.extend(ids[:4])
    representative = representative[:20]

    selected_corr_groups: List[Tuple[str, str]] = []
    selected_corr_groups.extend((cid, "representative_correlation_group") for cid in representative)
    selected_corr_groups.extend((cid, "longest_correlation_group") for cid in longest_ids)
    selected_corr_groups.extend((cid, "start_without_terminal_group") for cid in start_no_terminal_ids[:10])
    selected_corr_groups.extend((cid, "multiple_terminal_state_group") for cid in multi_terminal_ids[:10])

    # Deduplicate while preserving first label encountered.
    dedup_corr: Dict[str, str] = {}
    for cid, label in selected_corr_groups:
        if cid not in dedup_corr:
            dedup_corr[cid] = label

    fieldnames = [
        "internal_only",
        "example_type",
        "group_or_session_id",
        "scope",
        "threshold_minutes",
        "row_id",
        "timestamp_utc",
        "caller",
        "caller_ip",
        "subscription",
        "resource_group",
        "correlation_id",
        "operation",
        "provider",
        "operation_family",
        "action_verb",
        "activity_status",
        "activity_substatus",
        "status_code",
        "event_category",
        "resource_entity",
        "resource_type",
        "level",
        "outcome_class",
        "sensitive_action",
    ]

    with open(INTERNAL_EXAMPLES_PATH, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()

        for cid, label in dedup_corr.items():
            rows = db.query_all(
                """
                SELECT row_id, timestamp_utc, caller, caller_ip, subscription, resource_group, correlation_id,
                       operation, provider, operation_family, action_verb, activity_status, activity_substatus,
                       status_code, event_category, resource_entity, resource_type, level, outcome_class, sensitive_action
                FROM events
                WHERE correlation_id = ?
                ORDER BY timestamp_epoch, row_id
                """,
                [cid],
            )
            gid = f"corr:{cid}"
            for r in rows:
                writer.writerow(
                    {
                        "internal_only": "INTERNAL_USE_ONLY",
                        "example_type": label,
                        "group_or_session_id": gid,
                        "scope": "correlation_id",
                        "threshold_minutes": "",
                        "row_id": r[0],
                        "timestamp_utc": r[1],
                        "caller": r[2],
                        "caller_ip": r[3],
                        "subscription": r[4],
                        "resource_group": r[5],
                        "correlation_id": r[6],
                        "operation": r[7],
                        "provider": r[8],
                        "operation_family": r[9],
                        "action_verb": r[10],
                        "activity_status": r[11],
                        "activity_substatus": r[12],
                        "status_code": r[13],
                        "event_category": r[14],
                        "resource_entity": r[15],
                        "resource_type": r[16],
                        "level": r[17],
                        "outcome_class": r[18],
                        "sensitive_action": r[19],
                    }
                )

        # Session examples from each threshold/scope key.
        for key, session_list in session_examples.items():
            # keep a bounded subset
            for session in session_list[:3]:
                scope_tag = key
                sess_key, start_ts, end_ts, label = session
                if not sess_key:
                    continue
                caller = sess_key[0]
                where = "caller = ? AND timestamp_epoch >= ? AND timestamp_epoch <= ?"
                params: List[Any] = [caller, start_ts, end_ts]

                rows = db.query_all(
                    f"""
                    SELECT row_id, timestamp_utc, caller, caller_ip, subscription, resource_group, correlation_id,
                           operation, provider, operation_family, action_verb, activity_status, activity_substatus,
                           status_code, event_category, resource_entity, resource_type, level, outcome_class, sensitive_action
                    FROM events
                    WHERE {where}
                    ORDER BY timestamp_epoch, row_id
                    """,
                    params,
                )

                gid = f"session:{scope_tag}:{caller}:{int(start_ts)}:{int(end_ts)}"
                threshold_minutes = ""
                if "_" in key and key.endswith("m"):
                    try:
                        threshold_minutes = key.split("_")[-1].replace("m", "")
                    except Exception:
                        threshold_minutes = ""
                for r in rows:
                    writer.writerow(
                        {
                            "internal_only": "INTERNAL_USE_ONLY",
                            "example_type": label,
                            "group_or_session_id": gid,
                            "scope": scope_tag,
                            "threshold_minutes": threshold_minutes,
                            "row_id": r[0],
                            "timestamp_utc": r[1],
                            "caller": r[2],
                            "caller_ip": r[3],
                            "subscription": r[4],
                            "resource_group": r[5],
                            "correlation_id": r[6],
                            "operation": r[7],
                            "provider": r[8],
                            "operation_family": r[9],
                            "action_verb": r[10],
                            "activity_status": r[11],
                            "activity_substatus": r[12],
                            "status_code": r[13],
                            "event_category": r[14],
                            "resource_entity": r[15],
                            "resource_type": r[16],
                            "level": r[17],
                            "outcome_class": r[18],
                            "sensitive_action": r[19],
                        }
                    )


def main() -> int:
    setup_logging()
    random.seed(RANDOM_SEED)

    started = datetime.now(timezone.utc)
    source_path = REPO_ROOT / SOURCE_FILENAME
    if not source_path.exists():
        logger.error("FATAL: source file not found: %s", source_path)
        return 1

    db = init_engine()
    create_schema(db)

    logger.info("Phase A: Ingest + semantic extraction")
    semantic_profile = ingest_source(db, source_path)
    logger.info("Rows inserted: %d", semantic_profile["rows_inserted"])

    create_indexes(db)

    # Persist semantic profile now.
    semantic_profile_out = {
        "source_file": str(source_path.name),
        "total_rows_read": semantic_profile["total_rows_read"],
        "rows_inserted": semantic_profile["rows_inserted"],
        "malformed_rows": semantic_profile["malformed_rows"],
        "properties_parse": {
            "success": semantic_profile["properties_parse_success"],
            "failure": semantic_profile["properties_parse_failure"],
            "success_rate": semantic_profile["properties_parse_success"]
            / semantic_profile["rows_inserted"]
            if semantic_profile["rows_inserted"]
            else 0.0,
        },
        "claims_parse": {
            "success": semantic_profile["claims_parse_success"],
            "failure": semantic_profile["claims_parse_failure"],
            "success_rate": semantic_profile["claims_parse_success"]
            / semantic_profile["rows_inserted"]
            if semantic_profile["rows_inserted"]
            else 0.0,
        },
        "timestamp_parse_failure": semantic_profile["timestamp_parse_failure"],
        "parse_error_examples_bounded": semantic_profile["parse_error_examples"],
    }
    SEMANTIC_PROFILE_PATH.write_text(json.dumps(semantic_profile_out, indent=2), encoding="utf-8")

    logger.info("Phase B: Exact CorrelationId analysis")
    corr_stats, corr_patterns = analyze_correlation_groups(db)
    CORR_STATS_PATH.write_text(json.dumps(corr_stats, indent=2), encoding="utf-8")
    write_csv(CORR_SEQ_PATTERNS_PATH, corr_patterns, ["sequence_type", "sequence", "count"])

    logger.info("Phase C: Caller concentration and identity")
    caller_rows, caller_concentration = analyze_callers(db, int(semantic_profile["rows_inserted"]))
    write_csv(
        CALLER_SUMMARY_PATH,
        caller_rows,
        [
            "caller",
            "total_rows",
            "active_days",
            "distinct_operations",
            "distinct_operation_families",
            "distinct_providers",
            "distinct_subscriptions",
            "distinct_resource_groups",
            "distinct_resource_types",
            "distinct_caller_ips",
            "success_rate",
            "failure_rate",
            "warning_rate",
            "error_rate",
            "events_per_hour_mean",
            "events_per_hour_p95",
            "dataset_volume_share",
            "identity_type_claim",
            "identity_classification",
            "application_id",
            "application_id_consistency",
            "identity_object_id",
            "managed_identity_evidence",
        ],
    )
    CALLER_CONCENTRATION_PATH.write_text(json.dumps(caller_concentration, indent=2), encoding="utf-8")

    logger.info("Phase D: Caller-centered sessionization")
    session_rows, session_examples = analyze_sessionization(db)
    write_csv(SESSION_COMPARISON_PATH, session_rows, list(session_rows[0].keys()) if session_rows else ["scope"])

    logger.info("Phase E: Resource-centered viability")
    resource_out = analyze_resources(db)
    RESOURCE_ANALYSIS_PATH.write_text(json.dumps(resource_out, indent=2), encoding="utf-8")

    logger.info("Phase F: Event-token comparison")
    token_rows = analyze_tokens(db)
    write_csv(TOKEN_COMPARISON_PATH, token_rows, list(token_rows[0].keys()) if token_rows else ["token_design"])

    logger.info("Phase G: Time-based split feasibility")
    split_out = analyze_time_splits(db)
    TIME_SPLIT_PATH.write_text(json.dumps(split_out, indent=2), encoding="utf-8")

    logger.info("Phase H + I: Evaluation and modeling docs")
    write_markdown_evaluation(EVAL_STRATEGY_PATH)
    write_markdown_modeling(MODELING_RECOMMENDATION_PATH)
    write_sequence_viability_report(VIABILITY_REPORT_PATH, corr_stats, SESSION_COMPARISON_PATH)

    logger.info("Internal bounded examples")
    build_internal_examples(db, corr_stats, session_examples)

    ended = datetime.now(timezone.utc)

    manifest = {
        "run_started_utc": started.isoformat(),
        "run_finished_utc": ended.isoformat(),
        "engine": db.name,
        "random_seed": RANDOM_SEED,
        "chunk_size": CHUNK_SIZE,
        "max_parse_error_examples": MAX_PARSE_ERROR_EXAMPLES,
        "source_file": SOURCE_FILENAME,
        "source_size_bytes": source_path.stat().st_size,
        "source_mtime": datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "script_hashes_sha256": {
            "04_analyze_sequence_viability.py": sha256_file(REPO_ROOT / "04_analyze_sequence_viability.py"),
            "src/semantic_parsing.py": sha256_file(REPO_ROOT / "src" / "semantic_parsing.py"),
        },
        "artifacts": [
            str(p.name)
            for p in [
                SEMANTIC_PROFILE_PATH,
                CORR_STATS_PATH,
                CORR_SEQ_PATTERNS_PATH,
                CALLER_SUMMARY_PATH,
                CALLER_CONCENTRATION_PATH,
                SESSION_COMPARISON_PATH,
                RESOURCE_ANALYSIS_PATH,
                TOKEN_COMPARISON_PATH,
                TIME_SPLIT_PATH,
                EVAL_STRATEGY_PATH,
                MODELING_RECOMMENDATION_PATH,
                VIABILITY_REPORT_PATH,
                RUN_MANIFEST_PATH,
                ERROR_LOG_PATH,
                INTERNAL_EXAMPLES_PATH,
            ]
        ],
        "consistency_checks": {
            "total_rows_inserted": semantic_profile["rows_inserted"],
            "caller_summary_row_count": len(caller_rows),
            "sessionization_rows": len(session_rows),
            "tokenization_rows": len(token_rows),
        },
    }
    RUN_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    logger.info("All outputs written to %s", ARTIFACTS_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
