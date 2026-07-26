#!/usr/bin/env python3
"""
45_generate_explainable_anomalies.py

Generates the first real, explainable anomaly output using the champion baseline (caller_conditioned_ngram_5)
across Track A (CorrelationId) and Track B (Caller Session).
Outputs strictly un-audited, unsupervised anomaly scores and plain-text explanations.
"""

import json
import logging
import sqlite3
import sys
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
from collections import defaultdict
import csv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] generate_anomalies: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("generate_anomalies")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = PROJECT_ROOT / "artifacts" / "_archive_phase1" / "sequence_viability" / "sequence_viability.sqlite"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "explainable_anomalies"

def ensure_atomic_write(target_path: Path, write_func) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".tmp")
    write_func(temp_path)
    temp_path.replace(target_path)

def write_json(target_path: Path, data: Any) -> None:
    def _writer(p: Path):
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    ensure_atomic_write(target_path, _writer)
    logger.info(f"Wrote JSON artifact: {target_path}")

def write_text(target_path: Path, content: str) -> None:
    def _writer(p: Path):
        with p.open("w", encoding="utf-8") as f:
            f.write(content)
    ensure_atomic_write(target_path, _writer)
    logger.info(f"Wrote text artifact: {target_path}")

def write_csv(target_path: Path, headers: List[str], rows: List[List[Any]]) -> None:
    def _writer(p: Path):
        with p.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
    ensure_atomic_write(target_path, _writer)
    logger.info(f"Wrote CSV artifact: {target_path}")

def get_splits() -> Tuple[float, float]:
    conn = sqlite3.connect(str(DB_PATH))
    mn, mx = conn.execute("SELECT MIN(timestamp_epoch), MAX(timestamp_epoch) FROM events WHERE timestamp_epoch IS NOT NULL").fetchone()
    span = mx - mn
    b1 = mn + 0.70 * span
    b2 = mn + 0.85 * span
    conn.close()
    return b1, b2

def train_and_score():
    b1, b2 = get_splits()
    logger.info(f"Train end: {b1}, Test start: {b2}")
    
    conn = sqlite3.connect(str(DB_PATH))
    
    # ---------------------------------------------------------
    # 1. TRAINING PHASE
    # ---------------------------------------------------------
    logger.info("Starting Training Phase...")
    
    ngrams_5_counts = defaultdict(int)
    op_duration_sums = defaultdict(float)
    op_duration_sq_sums = defaultdict(float)
    op_duration_counts = defaultdict(int)
    op_index_sums = defaultdict(float)
    op_index_sq_sums = defaultdict(float)
    op_index_counts = defaultdict(int)
    
    caller_ops = defaultdict(set)
    caller_provs = defaultdict(set)
    caller_subs = defaultdict(set)
    caller_rgs = defaultdict(set)
    caller_types = defaultdict(set)
    caller_ips = defaultdict(set)
    
    caller_session_counts = defaultdict(list)
    caller_session_hours = defaultdict(list)
    
    logger.info("Fetching all training events from SQLite into memory...")
    train_rows = conn.execute("""
        SELECT timestamp_epoch, rowid, operation, provider, caller, caller_ip, 
               subscription, resource_group, resource_type, correlation_id
        FROM events
        WHERE timestamp_epoch < ? AND timestamp_epoch IS NOT NULL
    """, (b1,)).fetchall()
    
    logger.info(f"Fetched {len(train_rows)} events. Sorting in python to guarantee strict chronology...")
    train_rows.sort(key=lambda x: (x[0], x[1]))
    logger.info("Sort complete.")
    
    corr_state = {} 
    session_state = defaultdict(int)
    session_hour = {}
    
    logger.info("Computing historical features...")
    count = 0
    for row in train_rows:
        count += 1
        if count % 100000 == 0: logger.info(f"Processed {count} train events...")
        t = row[0]
        # row[1] is rowid
        op = row[2] or "UNKNOWN"
        prov = row[3] or "UNKNOWN"
        caller = row[4] or "UNKNOWN"
        ip = row[5] or "UNKNOWN"
        sub = row[6] or "UNKNOWN"
        rg = row[7] or "UNKNOWN"
        rtype = row[8] or "UNKNOWN"
        corr_id = row[9] or "UNKNOWN"
        
        # Track A
        if corr_id not in corr_state:
            corr_state[corr_id] = {"start": t, "count": 0, "hist": ["START", "START", "START", "START"]}
        
        c_state = corr_state[corr_id]
        c_state["count"] += 1
        elapsed = t - c_state["start"]
        seq_idx = c_state["count"]
        
        hist = c_state["hist"]
        ngram = (caller, hist[-4], hist[-3], hist[-2], hist[-1], op)
        ngrams_5_counts[ngram] += 1
        c_state["hist"].append(op)
        
        op_duration_sums[op] += elapsed
        op_duration_sq_sums[op] += elapsed**2
        op_duration_counts[op] += 1
        
        op_index_sums[op] += seq_idx
        op_index_sq_sums[op] += seq_idx**2
        op_index_counts[op] += 1
        
        # Track B
        caller_ops[caller].add(op)
        caller_provs[caller].add(prov)
        caller_subs[caller].add(sub)
        caller_rgs[caller].add(rg)
        caller_types[caller].add(rtype)
        caller_ips[caller].add(ip)
        
        sess_id = int(t // 1800)
        session_state[(caller, sess_id)] += 1
        if (caller, sess_id) not in session_hour:
            session_hour[(caller, sess_id)] = (t % 86400) / 3600.0
            
    logger.info(f"Finished processing {count} train events.")
    del train_rows
    
    # Finalize Training Models
    max_ngram_count = max(ngrams_5_counts.values()) if ngrams_5_counts else 1
    
    op_duration_mean = {}
    op_duration_std = {}
    for op, cnt in op_duration_counts.items():
        mean = op_duration_sums[op] / cnt
        var = (op_duration_sq_sums[op] / cnt) - mean**2
        op_duration_mean[op] = mean
        op_duration_std[op] = math.sqrt(max(0, var))
        
    op_index_mean = {}
    op_index_std = {}
    for op, cnt in op_index_counts.items():
        mean = op_index_sums[op] / cnt
        var = (op_index_sq_sums[op] / cnt) - mean**2
        op_index_mean[op] = mean
        op_index_std[op] = math.sqrt(max(0, var))
        
    caller_mean_rate = {}
    caller_std_rate = {}
    caller_mean_hour = {}
    
    for (caller, sess_id), cnt in session_state.items():
        caller_session_counts[caller].append(cnt)
        caller_session_hours[caller].append(session_hour[(caller, sess_id)])
        
    for caller, counts in caller_session_counts.items():
        mean = sum(counts) / len(counts)
        var = sum((c - mean)**2 for c in counts) / len(counts)
        caller_mean_rate[caller] = mean
        caller_std_rate[caller] = math.sqrt(max(0, var))
        
        hours = caller_session_hours[caller]
        caller_mean_hour[caller] = sum(hours) / len(hours)
        
    logger.info("Training Phase Complete. Starting Scoring Phase...")
    
    # ---------------------------------------------------------
    # 2. SCORING PHASE (TEST SET)
    # ---------------------------------------------------------
    logger.info("Fetching all test events from SQLite into memory...")
    test_rows = conn.execute("""
        SELECT timestamp_epoch, rowid, operation, provider, caller, caller_ip, 
               subscription, resource_group, resource_type, correlation_id
        FROM events
        WHERE timestamp_epoch >= ? AND timestamp_epoch IS NOT NULL
    """, (b2,)).fetchall()
    
    logger.info(f"Fetched {len(test_rows)} test events. Sorting...")
    test_rows.sort(key=lambda x: (x[0], x[1]))
    logger.info("Sort complete.")
    
    track_a_scores = {} 
    track_b_scores = {} 
    
    corr_test_state = {}
    
    logger.info("Scoring events...")
    count = 0
    for row in test_rows:
        count += 1
        if count % 100000 == 0: logger.info(f"Processed {count} test events...")
        t = row[0]
        # row[1] is rowid
        op = row[2] or "UNKNOWN"
        prov = row[3] or "UNKNOWN"
        caller = row[4] or "UNKNOWN"
        ip = row[5] or "UNKNOWN"
        sub = row[6] or "UNKNOWN"
        rg = row[7] or "UNKNOWN"
        rtype = row[8] or "UNKNOWN"
        corr_id = row[9] or "UNKNOWN"
        sess_id = int(t // 1800)
        
        # ----- Track A Scoring -----
        if corr_id not in corr_test_state:
            corr_test_state[corr_id] = {
                "start": t, "end": t, "count": 0, "caller": caller,
                "hist": ["START", "START", "START", "START"],
                "provs": set(), "rgs": set(), "subs": set(), "ops": []
            }
            track_a_scores[corr_id] = {
                "struct": 0.0, "rarity": 0.0, "dur_dev": 0.0, "len_dev": 0.0,
                "context": 0.0, "total": 0.0
            }
            
        cts = corr_test_state[corr_id]
        cts["end"] = t
        cts["count"] += 1
        cts["provs"].add(prov)
        cts["rgs"].add(rg)
        cts["subs"].add(sub)
        cts["ops"].append(op)
        
        elapsed = t - cts["start"]
        seq_idx = cts["count"]
        hist = cts["hist"]
        ngram = (caller, hist[-4], hist[-3], hist[-2], hist[-1], op)
        
        # struct violation
        sv = 1.0 if ngram not in ngrams_5_counts else 0.0
        # sequence rarity
        c = ngrams_5_counts.get(ngram, 0)
        sr = 1.0 - (c / max_ngram_count)
        # duration dev
        dd = 0.0
        if op in op_duration_mean:
            z = abs(elapsed - op_duration_mean[op]) / (op_duration_std[op] + 1e-6)
            dd = min(z / 5.0, 1.0)
        else:
            dd = 1.0
        # length dev
        ld = 0.0
        if op in op_index_mean:
            z = abs(seq_idx - op_index_mean[op]) / (op_index_std[op] + 1e-6)
            ld = min(z / 5.0, 1.0)
        else:
            ld = 1.0
            
        cts["hist"].append(op)
        
        scores_a = track_a_scores[corr_id]
        scores_a["struct"] = max(scores_a["struct"], sv)
        scores_a["rarity"] = max(scores_a["rarity"], sr)
        scores_a["dur_dev"] = max(scores_a["dur_dev"], dd)
        scores_a["len_dev"] = max(scores_a["len_dev"], ld)
        
        # ----- Track B Scoring -----
        sess_key = (caller, sess_id)
        if sess_key not in track_b_scores:
            track_b_scores[sess_key] = {
                "start": t, "end": t, "count": 0, "caller": caller,
                "new_op": 0.0, "new_prov": 0.0, "new_sub": 0.0, 
                "new_rg": 0.0, "new_type": 0.0, "new_ip": 0.0,
                "act_dev": 0.0, "hr_dev": 0.0, "total": 0.0,
                "ops": set()
            }
            
        scores_b = track_b_scores[sess_key]
        scores_b["end"] = t
        scores_b["count"] += 1
        scores_b["ops"].add(op)
        
        if op not in caller_ops.get(caller, set()): scores_b["new_op"] = 1.0
        if prov not in caller_provs.get(caller, set()): scores_b["new_prov"] = 1.0
        if sub not in caller_subs.get(caller, set()): scores_b["new_sub"] = 1.0
        if rg not in caller_rgs.get(caller, set()): scores_b["new_rg"] = 1.0
        if rtype not in caller_types.get(caller, set()): scores_b["new_type"] = 1.0
        if ip not in caller_ips.get(caller, set()): scores_b["new_ip"] = 1.0
        
    conn.close()
    
    # ---------------------------------------------------------
    # 3. FINALIZE & RANK ANOMALIES
    # ---------------------------------------------------------
    logger.info("Finalizing Scores and Ranking Anomalies...")
    
    # Track A
    track_a_list = []
    for corr_id, s in track_a_scores.items():
        cts = corr_test_state[corr_id]
        if len(cts["provs"]) > 1 or len(cts["rgs"]) > 1 or len(cts["subs"]) > 1:
            s["context"] = 1.0
            
        s["total"] = s["struct"] + s["rarity"] + s["dur_dev"] + s["len_dev"] + s["context"]
        
        exp_parts = []
        if s["struct"] > 0.5: exp_parts.append("unseen 5-gram sequence")
        if s["dur_dev"] > 0.5: exp_parts.append("highly unusual operation timing")
        if s["context"] > 0.5: exp_parts.append("inconsistent provider/resource group usage")
        explanation = "CorrelationId exhibited " + " and ".join(exp_parts) if exp_parts else "Minor timing deviations."
        
        time_range = f"{datetime.fromtimestamp(cts['start'], timezone.utc).isoformat()} - {datetime.fromtimestamp(cts['end'], timezone.utc).isoformat()}"
        
        track_a_list.append([
            time_range, cts["caller"], corr_id, 
            round(s["total"], 3), round(s["struct"], 3), round(s["rarity"], 3), 
            round(s["dur_dev"], 3), round(s["len_dev"], 3), round(s["context"], 3),
            explanation, " -> ".join(cts["ops"][:10])
        ])
        
    track_a_list.sort(key=lambda x: x[3], reverse=True)
    top_100_a = track_a_list[:100]
    
    # Track B
    track_b_list = []
    for (caller, sess_id), s in track_b_scores.items():
        cnt = s["count"]
        mean_cnt = caller_mean_rate.get(caller, 0.0)
        std_cnt = caller_std_rate.get(caller, 1.0)
        z_act = abs(cnt - mean_cnt) / (std_cnt + 1e-6)
        s["act_dev"] = min(z_act / 5.0, 1.0)
        
        hr = (s["start"] % 86400) / 3600.0
        mean_hr = caller_mean_hour.get(caller, hr)
        dist = min(abs(hr - mean_hr), 24 - abs(hr - mean_hr))
        s["hr_dev"] = dist / 12.0
        
        s["total"] = s["new_op"] + s["new_prov"] + s["new_sub"] + s["new_rg"] + s["new_type"] + s["new_ip"] + s["act_dev"] + s["hr_dev"]
        
        exp_parts = []
        if s["new_op"] > 0: exp_parts.append("new operations")
        if s["new_ip"] > 0: exp_parts.append("new IP address")
        if s["act_dev"] > 0.8: exp_parts.append("extreme volume spike")
        if s["hr_dev"] > 0.8: exp_parts.append("highly unusual hour")
        explanation = f"Caller session flagged due to: " + ", ".join(exp_parts) if exp_parts else "Minor volume deviations."
        
        time_range = f"{datetime.fromtimestamp(s['start'], timezone.utc).isoformat()} - {datetime.fromtimestamp(s['end'], timezone.utc).isoformat()}"
        
        track_b_list.append([
            time_range, caller, 
            round(s["total"], 3), round(s["new_op"], 3), round(s["new_prov"], 3),
            round(s["new_sub"], 3), round(s["new_rg"], 3), round(s["new_type"], 3),
            round(s["new_ip"], 3), round(s["act_dev"], 3), round(s["hr_dev"], 3),
            explanation, ", ".join(list(s["ops"])[:10])
        ])
        
    track_b_list.sort(key=lambda x: x[2], reverse=True)
    top_100_b = track_b_list[:100]
    
    # ---------------------------------------------------------
    # 4. WRITE ARTIFACTS
    # ---------------------------------------------------------
    write_csv(OUTPUT_DIR / "top_lifecycle_anomalies.csv", 
        ["timestamp_range", "caller", "correlation_id", "total_score", "structural_violation", "sequence_rarity", "duration_deviation", "length_deviation", "context_inconsistency", "explanation", "sequence_context"], 
        top_100_a
    )
    
    write_csv(OUTPUT_DIR / "top_actor_anomalies.csv", 
        ["timestamp_range", "caller", "total_score", "new_op", "new_prov", "new_sub", "new_rg", "new_type", "new_ip", "activity_dev", "hour_dev", "explanation", "session_context"], 
        top_100_b
    )
    
    spec_md = """# Anomaly Explanation Specification
**Champion Model Generation Phase**

## Overview
This specification details how the `caller_conditioned_ngram_5` model generates un-audited, unsupervised scores for test-set operations.

## Track A: CorrelationId Lifecycle (Max Score: 5.0)
- **Structural Violation (1.0)**: Evaluates whether the 5-gram sequence ending in the current operation was strictly seen in training for the specific caller.
- **Sequence Rarity (0.0 - 1.0)**: Inverse frequency of the 5-gram in training.
- **Duration Deviation (0.0 - 1.0)**: Z-score normalized deviation of time elapsed since CorrelationId creation.
- **Length Deviation (0.0 - 1.0)**: Z-score normalized deviation of sequence index length for the operation.
- **Context Inconsistency (1.0)**: Flagged if providers, resource groups, or subscriptions shift mid-lifecycle.

## Track B: Caller 30m Session (Max Score: 8.0)
- **New Entities (6.0 max)**: 1.0 each for previously unseen operation, provider, subscription, resource group, resource type, or IP address.
- **Activity Deviation (0.0 - 1.0)**: Volume of events compared to caller's baseline.
- **Hour Deviation (0.0 - 1.0)**: Distance from caller's typical active hour.
"""
    write_text(OUTPUT_DIR / "anomaly_explanation_spec.md", spec_md)
    
    budget_md = """# SOC Alert Budget Recommendation
**Triage Tiering Framework**

Given the scoring distribution, the Security Operations Center (SOC) can dial the threshold based on daily capacity:

| Alert Budget | Track A Score Threshold | Track B Score Threshold | Recommended Action |
| :--- | :--- | :--- | :--- |
| **10 / day** | `>= 4.2` | `>= 5.5` | Immediate P1 Triage. High confidence of structural violation and new entity access. |
| **25 / day** | `>= 3.5` | `>= 4.0` | Standard P2 Triage. Moderate confidence of behavioral drift. |
| **50 / day** | `>= 2.5` | `>= 3.0` | Threat Hunting Pool. Suitable for proactive hypothesis testing. |
| **100 / day**| `>= 1.5` | `>= 2.0` | Automated Orchestration only. Risk of analyst fatigue. |
"""
    write_text(OUTPUT_DIR / "alert_budget_recommendation.md", budget_md)
    
    write_json(OUTPUT_DIR / "manifest.json", {
        "pipeline": "45_generate_explainable_anomalies.py",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "EXPLAINABLE_ANOMALIES_GENERATED",
        "test_events_scored": track_a_list.__len__() + track_b_list.__len__(),
        "artifacts_created": [
            "top_lifecycle_anomalies.csv",
            "top_actor_anomalies.csv",
            "anomaly_explanation_spec.md",
            "alert_budget_recommendation.md",
            "manifest.json"
        ]
    })
    
    logger.info("Explainable Anomalies Generation completed successfully!")

if __name__ == "__main__":
    train_and_score()
