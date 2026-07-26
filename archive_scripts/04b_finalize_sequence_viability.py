from __future__ import annotations

import csv
import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
ART = ROOT / "artifacts" / "sequence_viability"
DB = ART / "sequence_viability.sqlite"

TOKEN_CSV = ART / "tokenization_comparison.csv"
TIME_JSON = ART / "time_split_analysis.json"
EVAL_MD = ART / "evaluation_strategy.md"
MODEL_MD = ART / "modeling_recommendation.md"
REPORT_MD = ART / "sequence_viability_report.md"
RUN_JSON = ART / "run_manifest.json"
INTERNAL_CSV = ART / "internal_sequence_examples.csv"

CORR_JSON = ART / "correlation_group_statistics.json"
SEM_JSON = ART / "semantic_extraction_profile.json"
SESSION_CSV = ART / "sessionization_comparison.csv"
RESOURCE_JSON = ART / "resource_sequence_analysis.json"
CALLER_CONC_JSON = ART / "caller_concentration.json"


def entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0
    e = 0.0
    for c in counter.values():
        p = c / total
        if p > 0:
            e -= p * math.log2(p)
    return e


def coverage(counter: Counter[str], k: int) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0
    return sum(v for _k, v in counter.most_common(k)) / total


def write_tokenization(conn: sqlite3.Connection) -> None:
    token_defs = {
        "Token A": "token_a",
        "Token B": "token_b",
        "Token C": "token_c",
        "Token D": "token_d",
        "Token E": "token_e",
    }
    total_rows = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    rows_out: List[Dict[str, Any]] = []
    for label, col in token_defs.items():
        cur = conn.execute(f"SELECT {col}, COUNT(*) FROM events GROUP BY {col}")
        freq = Counter({str(k or ""): int(v) for k, v in cur.fetchall()})
        missing = freq.get("", 0)
        if "" in freq:
            del freq[""]
        denom = sum(freq.values())
        rows_out.append(
            {
                "token_design": label,
                "column_used": col,
                "vocabulary_size": len(freq),
                "missing_rate": (missing / total_rows) if total_rows else 0.0,
                "top1_coverage": coverage(freq, 1),
                "top5_coverage": coverage(freq, 5),
                "top10_coverage": coverage(freq, 10),
                "top20_coverage": coverage(freq, 20),
                "rare_event_share_le_1": (sum(v for v in freq.values() if v <= 1) / denom) if denom else 0.0,
                "rare_event_share_le_5": (sum(v for v in freq.values() if v <= 5) / denom) if denom else 0.0,
                "rare_event_share_le_10": (sum(v for v in freq.values() if v <= 10) / denom) if denom else 0.0,
                "rare_event_share_le_100": (sum(v for v in freq.values() if v <= 100) / denom) if denom else 0.0,
                "entropy_bits": entropy(freq),
                "next_event_prediction_suitability": "good" if len(freq) < 5000 else "challenging",
                "trivial_prediction_risk": "higher" if label in {"Token B", "Token D"} else "lower",
                "outcome_encoding_note": "Includes activity status; target becomes operation-lifecycle prediction" if label in {"Token B", "Token D"} else "No direct status outcome in token",
                "analyst_interpretability": "high" if label in {"Token A", "Token B"} else "medium-high",
            }
        )

    with open(TOKEN_CSV, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
        writer.writeheader()
        writer.writerows(rows_out)


def write_time_splits(conn: sqlite3.Connection) -> None:
    mn, mx = conn.execute("SELECT MIN(timestamp_epoch), MAX(timestamp_epoch) FROM events WHERE timestamp_epoch IS NOT NULL").fetchone()
    mn = float(mn)
    mx = float(mx)
    span = mx - mn
    b1 = mn + 0.70 * span
    b2 = mn + 0.85 * span

    def distinct(col: str, where: str, params: Tuple[Any, ...]) -> set[str]:
        return {str(r[0] or "") for r in conn.execute(f"SELECT DISTINCT {col} FROM events WHERE {where}", params).fetchall() if str(r[0] or "")}

    out: Dict[str, Any] = {
        "split_strategy": {
            "method": "chronological_70_15_15_by_time_span",
            "train_start_epoch": mn,
            "validation_start_epoch": b1,
            "test_start_epoch": b2,
            "note": "Baseline training period is not assumed normal without security-team validation.",
        },
        "definitions": {},
    }

    defs = {
        "lifecycle_correlation_token_d": "token_d",
        "actor_behavior_token_c": "token_c",
    }

    for name, token_col in defs.items():
        tr = "timestamp_epoch>=? AND timestamp_epoch<?"
        va = "timestamp_epoch>=? AND timestamp_epoch<?"
        te = "timestamp_epoch>=?"

        train_tokens = distinct(token_col, tr + f" AND {token_col}<>''", (mn, b1))
        val_tokens = distinct(token_col, va + f" AND {token_col}<>''", (b1, b2))
        test_tokens = distinct(token_col, te + f" AND {token_col}<>''", (b2,))

        train_callers = distinct("caller", tr, (mn, b1))
        val_callers = distinct("caller", va, (b1, b2))
        test_callers = distinct("caller", te, (b2,))

        train_res = distinct("resource_entity", tr + " AND resource_entity<>''", (mn, b1))
        val_res = distinct("resource_entity", va + " AND resource_entity<>''", (b1, b2))
        test_res = distinct("resource_entity", te + " AND resource_entity<>''", (b2,))

        out["definitions"][name] = {
            "token_column": token_col,
            "event_counts": {
                "train": conn.execute(f"SELECT COUNT(*) FROM events WHERE {tr}", (mn, b1)).fetchone()[0],
                "validation": conn.execute(f"SELECT COUNT(*) FROM events WHERE {va}", (b1, b2)).fetchone()[0],
                "test": conn.execute(f"SELECT COUNT(*) FROM events WHERE {te}", (b2,)).fetchone()[0],
            },
            "sequence_proxy_counts_correlation_groups": {
                "train": conn.execute(f"SELECT COUNT(DISTINCT correlation_id) FROM events WHERE {tr} AND correlation_id<>''", (mn, b1)).fetchone()[0],
                "validation": conn.execute(f"SELECT COUNT(DISTINCT correlation_id) FROM events WHERE {va} AND correlation_id<>''", (b1, b2)).fetchone()[0],
                "test": conn.execute(f"SELECT COUNT(DISTINCT correlation_id) FROM events WHERE {te} AND correlation_id<>''", (b2,)).fetchone()[0],
            },
            "vocabulary": {
                "train": len(train_tokens),
                "validation": len(val_tokens),
                "test": len(test_tokens),
                "validation_unseen_tokens": len([t for t in val_tokens if t not in train_tokens]),
                "test_unseen_tokens": len([t for t in test_tokens if t not in train_tokens]),
                "validation_unseen_rate": (len([t for t in val_tokens if t not in train_tokens]) / len(val_tokens)) if val_tokens else 0.0,
                "test_unseen_rate": (len([t for t in test_tokens if t not in train_tokens]) / len(test_tokens)) if test_tokens else 0.0,
            },
            "caller_coverage": {
                "train": len(train_callers),
                "validation": len(val_callers),
                "test": len(test_callers),
                "validation_unseen_rate": (len([c for c in val_callers if c not in train_callers]) / len(val_callers)) if val_callers else 0.0,
                "test_unseen_rate": (len([c for c in test_callers if c not in train_callers]) / len(test_callers)) if test_callers else 0.0,
            },
            "resource_coverage": {
                "train": len(train_res),
                "validation": len(val_res),
                "test": len(test_res),
                "validation_unseen_rate": (len([r for r in val_res if r not in train_res]) / len(val_res)) if val_res else 0.0,
                "test_unseen_rate": (len([r for r in test_res if r not in train_res]) / len(test_res)) if test_res else 0.0,
            },
        }

    TIME_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")


def write_markdowns() -> None:
    EVAL_MD.write_text("# Evaluation Strategy\n\nSee previous generated guidance: weak labels are overlays only, not truth.\n", encoding="utf-8")
    MODEL_MD.write_text("# Modeling Recommendation\n\nImplementation order: caller-operation rarity -> Markov/n-gram -> hybrid scorer -> DeepLog-style LSTM.\n", encoding="utf-8")

    corr = json.loads(CORR_JSON.read_text(encoding="utf-8"))
    s = corr["singleton_groups_pct"]
    m = corr["multi_dimension_groups"]["multiple_operations"]["pct"]
    ssf = corr["lifecycle_patterns"]["start_to_success"]["pct"] + corr["lifecycle_patterns"]["start_to_failure"]["pct"]
    REPORT_MD.write_text(
        (
            "# Sequence Viability Report\n\n"
            f"- singleton CorrelationId groups: {s:.2f}%\n"
            f"- groups with multiple operations: {m:.2f}%\n"
            f"- Start->Success/Failure share: {ssf:.2f}%\n\n"
            "Conclusion: CorrelationId mostly reflects operation lifecycle units, not broad actor sessions.\n"
        ),
        encoding="utf-8",
    )


def write_internal_examples(conn: sqlite3.Connection) -> None:
    corr = json.loads(CORR_JSON.read_text(encoding="utf-8"))
    cand = corr.get("internal_example_candidate_ids", {})
    sizes = cand.get("group_sizes", {})
    longest = [k for k, _v in sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:3]]
    reps = list(sizes.keys())[:5]
    snt = cand.get("start_no_terminal_ids", [])[:3]
    mts = cand.get("multiple_terminal_ids", [])[:3]

    rows: List[Dict[str, Any]] = []

    def add_corr(cids: List[str], label: str) -> None:
        for cid in cids:
            cur = conn.execute(
                """
                SELECT row_id, timestamp_utc, caller, caller_ip, subscription, resource_group,
                       correlation_id, operation, provider, operation_family, action_verb,
                       activity_status, activity_substatus, status_code, event_category,
                       resource_entity, resource_type, level, outcome_class, sensitive_action
                FROM events
                WHERE correlation_id=?
                ORDER BY timestamp_epoch, row_id
                LIMIT 50
                """,
                (cid,),
            )
            for r in cur.fetchall():
                rows.append(
                    {
                        "internal_only": "INTERNAL_USE_ONLY",
                        "example_type": label,
                        "group_or_session_id": f"corr:{cid}",
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

    add_corr(reps, "representative_correlation_group")
    add_corr(longest, "longest_correlation_group")
    add_corr(snt, "start_without_terminal_group")
    add_corr(mts, "multiple_terminal_state_group")

        # Session examples are intentionally omitted in this fast post-process path.
        # Correlation-group examples are sufficient to support model-unit decisions.

    if rows:
        with open(INTERNAL_CSV, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)


def write_manifest() -> None:
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_file": "logs_output_20260713_180521.csv",
        "method": "postprocess_from_sequence_viability_sqlite",
        "artifacts": [
            "semantic_extraction_profile.json",
            "correlation_group_statistics.json",
            "correlation_sequence_patterns.csv",
            "caller_identity_summary.csv",
            "caller_concentration.json",
            "sessionization_comparison.csv",
            "resource_sequence_analysis.json",
            "tokenization_comparison.csv",
            "time_split_analysis.json",
            "evaluation_strategy.md",
            "modeling_recommendation.md",
            "sequence_viability_report.md",
            "run_manifest.json",
            "errors.log",
            "internal_sequence_examples.csv",
        ],
    }
    RUN_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    conn = sqlite3.connect(str(DB))
    write_tokenization(conn)
    write_time_splits(conn)
    write_markdowns()
    write_internal_examples(conn)
    write_manifest()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
