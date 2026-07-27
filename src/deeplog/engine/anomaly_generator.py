#!/usr/bin/env python3
"""
DeepLog Analytics Engine — Core Anomaly Generator

Detects behavioral anomalies across two tracks:
  Track A: CorrelationId lifecycle violations (unseen sequences, timing, boundary crossings)
  Track B: Caller session drift (new entities, off-hours, volume spikes)

Accepts any Azure Activity Log CSV with the standard schema columns.
Performs a strict 70/15/15 chronological train-val-test split internally.
"""

import csv
import json
import logging
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("deeplog.engine")

# ---------------------------------------------------------------------------
# Column mapping: Azure Activity Log native → internal field names
# ---------------------------------------------------------------------------
# The engine auto-detects two CSV schemas:
#   1. Native Azure Activity Log export (from Log Analytics / Azure Monitor)
#   2. Pre-processed format (with timestamp_epoch, operation, etc.)
#
# Native Azure columns and their internal mapping:
AZURE_NATIVE_MAP = {
    "timegenerated": "timestamp_iso",
    "operationnamevalue": "operation",
    "resourceprovidervalue": "provider",
    "caller": "caller",
    "calleripaddress": "caller_ip",
    "subscriptionid": "subscription",
    "resourcegroup": "resource_group",
    "correlationid": "correlation_id",
    # ResourceId is often empty in Azure exports; resource_type derived from operation
}

# Pre-processed / generic columns
GENERIC_MAP = {
    "timestamp_epoch": "timestamp_epoch",
    "operation": "operation",
    "provider": "provider",
    "caller": "caller",
    "caller_ip": "caller_ip",
    "subscription": "subscription",
    "resource_group": "resource_group",
    "resource_type": "resource_type",
    "correlation_id": "correlation_id",
}

# Minimum columns required for either schema to work
_AZURE_REQUIRED = {"timegenerated", "operationnamevalue", "caller", "correlationid"}
_GENERIC_REQUIRED = {"timestamp_epoch", "operation", "caller", "correlation_id"}


# ---------------------------------------------------------------------------
# Atomic write helpers
# ---------------------------------------------------------------------------


def _atomic_write(target: Path, write_fn) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    write_fn(tmp)
    tmp.replace(target)
    logger.info(f"Written: {target}")


def _write_csv(target: Path, headers: List[str], rows: List[List[Any]]) -> None:
    def _w(p):
        with p.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(headers)
            csv.writer(f).writerows(rows)

    _atomic_write(target, _w)


def _write_text(target: Path, content: str) -> None:
    _atomic_write(target, lambda p: p.write_text(content, encoding="utf-8"))


def _write_json(target: Path, data: Any) -> None:
    _atomic_write(
        target, lambda p: p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------


def _parse_iso_epoch(iso_str: str) -> Optional[float]:
    """Parse an ISO8601 timestamp string to Unix epoch seconds."""
    if not iso_str:
        return None
    try:
        s = iso_str.strip()
        # Python's fromisoformat handles most Azure formats
        dt = datetime.fromisoformat(s)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _derive_resource_type(operation: str) -> str:
    """Derive resource_type from Azure operation name (e.g. MICROSOFT.SQL/SERVERS/DATABASES/WRITE → MICROSOFT.SQL/SERVERS/DATABASES)."""
    parts = operation.rsplit("/", 1)
    return parts[0] if len(parts) > 1 else operation


# ---------------------------------------------------------------------------
# CSV loading with auto-schema detection
# ---------------------------------------------------------------------------


def _normalize_header(raw: str) -> str:
    return raw.strip().lower().replace(" ", "_").replace("-", "_")


def load_events(csv_path: Path) -> List[Dict]:
    """
    Load events from a CSV file, auto-detecting whether it is a native
    Azure Activity Log export or a pre-processed format.
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {csv_path}\n"
            "Provide a path to an Azure Activity Log CSV export via --input."
        )

    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        raw_reader = csv.DictReader(f)
        if raw_reader.fieldnames is None:
            raise ValueError(f"CSV file appears empty: {csv_path}")

        norm_headers = {_normalize_header(h) for h in raw_reader.fieldnames}

        # Detect schema
        is_azure_native = _AZURE_REQUIRED.issubset(norm_headers)
        is_generic = _GENERIC_REQUIRED.issubset(norm_headers)

        if not is_azure_native and not is_generic:
            raise ValueError(
                f"CSV schema not recognized.\n"
                f"Found columns: {sorted(norm_headers)}\n\n"
                f"Expected EITHER native Azure Activity Log columns:\n"
                f"  {sorted(_AZURE_REQUIRED)}\n"
                f"OR pre-processed columns:\n"
                f"  {sorted(_GENERIC_REQUIRED)}"
            )

        schema = "azure_native" if is_azure_native else "generic"
        logger.info(f"Detected CSV schema: {schema}")

        events = []
        skipped = 0
        for raw_row in raw_reader:
            row = {_normalize_header(k): v for k, v in raw_row.items()}

            # --- Parse timestamp ---
            if schema == "azure_native":
                epoch = _parse_iso_epoch(row.get("timegenerated", ""))
            else:
                try:
                    epoch = float(row.get("timestamp_epoch", ""))
                except (ValueError, TypeError):
                    epoch = _parse_iso_epoch(row.get("timestamp", ""))

            if epoch is None:
                skipped += 1
                continue

            # --- Extract fields ---
            if schema == "azure_native":
                op = (row.get("operationnamevalue") or "UNKNOWN").strip().upper()
                prov = (row.get("resourceprovidervalue") or "UNKNOWN").strip().upper()
                ip = (row.get("calleripaddress") or "UNKNOWN").strip()
                sub = (row.get("subscriptionid") or "UNKNOWN").strip()
                rg = (row.get("resourcegroup") or "UNKNOWN").strip()
                corr = (row.get("correlationid") or "UNKNOWN").strip()
                rtype = _derive_resource_type(op)
            else:
                op = (row.get("operation") or "UNKNOWN").strip().upper()
                prov = (row.get("provider") or "UNKNOWN").strip().upper()
                ip = (
                    row.get("caller_ip") or row.get("calleripaddress") or "UNKNOWN"
                ).strip()
                sub = (
                    row.get("subscription") or row.get("subscriptionid") or "UNKNOWN"
                ).strip()
                rg = (
                    row.get("resource_group") or row.get("resourcegroup") or "UNKNOWN"
                ).strip()
                corr = (
                    row.get("correlation_id") or row.get("correlationid") or "UNKNOWN"
                ).strip()
                rtype = (
                    (row.get("resource_type") or _derive_resource_type(op))
                    .strip()
                    .upper()
                )

            caller = (row.get("caller") or "UNKNOWN").strip()

            events.append(
                {
                    "t": epoch,
                    "op": op,
                    "prov": prov,
                    "caller": caller,
                    "ip": ip,
                    "sub": sub,
                    "rg": rg,
                    "rtype": rtype,
                    "corr": corr,
                }
            )

    if skipped:
        logger.warning(f"Skipped {skipped:,} rows with unparseable timestamps")
    if not events:
        raise ValueError(f"No valid events loaded from {csv_path}")

    events.sort(key=lambda e: e["t"])
    logger.info(f"Loaded {len(events):,} events from {csv_path}")
    return events


# ---------------------------------------------------------------------------
# Core training
# ---------------------------------------------------------------------------


def _train(train_events: List[Dict]) -> Dict:
    """Build the caller-conditioned 5-gram model and session baselines."""
    ngrams: Dict[Tuple, int] = defaultdict(int)
    op_dur_sum: Dict[str, float] = defaultdict(float)
    op_dur_sq: Dict[str, float] = defaultdict(float)
    op_dur_cnt: Dict[str, int] = defaultdict(int)
    op_idx_sum: Dict[str, float] = defaultdict(float)
    op_idx_sq: Dict[str, float] = defaultdict(float)
    op_idx_cnt: Dict[str, int] = defaultdict(int)

    caller_ops: Dict[str, set] = defaultdict(set)
    caller_provs: Dict[str, set] = defaultdict(set)
    caller_subs: Dict[str, set] = defaultdict(set)
    caller_rgs: Dict[str, set] = defaultdict(set)
    caller_types: Dict[str, set] = defaultdict(set)
    caller_ips: Dict[str, set] = defaultdict(set)

    session_counts: Dict[str, list] = defaultdict(list)
    session_hours: Dict[str, list] = defaultdict(list)
    seen_sessions: set = set()

    corr_state: Dict[str, Dict] = {}

    logger.info(f"Training on {len(train_events):,} events...")
    for i, e in enumerate(train_events):
        t, op, prov, caller = e["t"], e["op"], e["prov"], e["caller"]
        ip, sub, rg, rtype, corr = e["ip"], e["sub"], e["rg"], e["rtype"], e["corr"]

        # Track A — CorrelationId n-gram
        if corr not in corr_state:
            corr_state[corr] = {"start": t, "count": 0, "hist": ["START"] * 4}
        cs = corr_state[corr]
        cs["count"] += 1
        hist = cs["hist"]
        ngram = (caller, hist[-4], hist[-3], hist[-2], hist[-1], op)
        ngrams[ngram] += 1
        cs["hist"].append(op)
        elapsed = t - cs["start"]
        op_dur_sum[op] += elapsed
        op_dur_sq[op] += elapsed**2
        op_dur_cnt[op] += 1
        op_idx_sum[op] += cs["count"]
        op_idx_sq[op] += cs["count"] ** 2
        op_idx_cnt[op] += 1

        # Track B — caller session
        caller_ops[caller].add(op)
        caller_provs[caller].add(prov)
        caller_subs[caller].add(sub)
        caller_rgs[caller].add(rg)
        caller_types[caller].add(rtype)
        caller_ips[caller].add(ip)
        sess_id = int(t // 1800)
        sess_key = (caller, sess_id)
        if sess_key not in seen_sessions:
            seen_sessions.add(sess_key)
            session_counts[caller].append(0)
            session_hours[caller].append((t % 86400) / 3600.0)
        session_counts[caller][-1] += 1

    # Finalize means/stds
    def _mean_std(sums, sq_sums, cnts):
        out_mean, out_std = {}, {}
        for k, cnt in cnts.items():
            m = sums[k] / cnt
            v = max(0, sq_sums[k] / cnt - m**2)
            out_mean[k] = m
            out_std[k] = math.sqrt(v)
        return out_mean, out_std

    op_dur_mean, op_dur_std = _mean_std(op_dur_sum, op_dur_sq, op_dur_cnt)
    op_idx_mean, op_idx_std = _mean_std(op_idx_sum, op_idx_sq, op_idx_cnt)

    caller_mean_rate, caller_std_rate, caller_mean_hour = {}, {}, {}
    for c, counts in session_counts.items():
        m = sum(counts) / len(counts)
        v = max(0, sum((x - m) ** 2 for x in counts) / len(counts))
        caller_mean_rate[c] = m
        caller_std_rate[c] = math.sqrt(v)
        caller_mean_hour[c] = sum(session_hours[c]) / len(session_hours[c])

    max_ngram = max(ngrams.values()) if ngrams else 1

    return {
        "ngrams": ngrams,
        "max_ngram": max_ngram,
        "op_dur_mean": op_dur_mean,
        "op_dur_std": op_dur_std,
        "op_idx_mean": op_idx_mean,
        "op_idx_std": op_idx_std,
        "caller_ops": caller_ops,
        "caller_provs": caller_provs,
        "caller_subs": caller_subs,
        "caller_rgs": caller_rgs,
        "caller_types": caller_types,
        "caller_ips": caller_ips,
        "caller_mean_rate": caller_mean_rate,
        "caller_std_rate": caller_std_rate,
        "caller_mean_hour": caller_mean_hour,
    }


# ---------------------------------------------------------------------------
# Core scoring
# ---------------------------------------------------------------------------


def _score(test_events: List[Dict], model: Dict) -> Tuple[Dict, Dict]:
    ngrams = model["ngrams"]
    max_ngram = model["max_ngram"]
    op_dur_mean = model["op_dur_mean"]
    op_dur_std = model["op_dur_std"]
    op_idx_mean = model["op_idx_mean"]
    op_idx_std = model["op_idx_std"]
    caller_ops = model["caller_ops"]
    caller_provs = model["caller_provs"]
    caller_subs = model["caller_subs"]
    caller_rgs = model["caller_rgs"]
    caller_types = model["caller_types"]
    caller_ips = model["caller_ips"]
    caller_mean_rate = model["caller_mean_rate"]
    caller_std_rate = model["caller_std_rate"]
    caller_mean_hour = model["caller_mean_hour"]

    track_a: Dict[str, Dict] = {}
    track_a_state: Dict[str, Dict] = {}
    track_b: Dict[tuple, Dict] = {}

    logger.info(f"Scoring {len(test_events):,} test events...")
    for e in test_events:
        t, op, prov, caller = e["t"], e["op"], e["prov"], e["caller"]
        ip, sub, rg, rtype, corr = e["ip"], e["sub"], e["rg"], e["rtype"], e["corr"]

        # ----- Track A -----
        if corr not in track_a_state:
            track_a_state[corr] = {
                "start": t,
                "end": t,
                "count": 0,
                "caller": caller,
                "hist": ["START"] * 4,
                "provs": set(),
                "rgs": set(),
                "subs": set(),
                "ops": [],
            }
            track_a[corr] = {
                "struct": 0.0,
                "rarity": 0.0,
                "dur_dev": 0.0,
                "len_dev": 0.0,
                "context": 0.0,
            }
        cs = track_a_state[corr]
        sa = track_a[corr]
        cs["end"] = t
        cs["count"] += 1
        cs["provs"].add(prov)
        cs["rgs"].add(rg)
        cs["subs"].add(sub)
        cs["ops"].append(op)

        hist = cs["hist"]
        ngram = (caller, hist[-4], hist[-3], hist[-2], hist[-1], op)
        elapsed = t - cs["start"]
        seq_idx = cs["count"]

        sv = 1.0 if ngram not in ngrams else 0.0
        sr = 1.0 - (ngrams.get(ngram, 0) / max_ngram)
        dd = (
            min(
                abs(elapsed - op_dur_mean.get(op, elapsed))
                / (op_dur_std.get(op, 1) + 1e-6)
                / 5,
                1.0,
            )
            if op in op_dur_mean
            else 1.0
        )
        ld = (
            min(
                abs(seq_idx - op_idx_mean.get(op, seq_idx))
                / (op_idx_std.get(op, 1) + 1e-6)
                / 5,
                1.0,
            )
            if op in op_idx_mean
            else 1.0
        )

        cs["hist"].append(op)
        sa["struct"] = max(sa["struct"], sv)
        sa["rarity"] = max(sa["rarity"], sr)
        sa["dur_dev"] = max(sa["dur_dev"], dd)
        sa["len_dev"] = max(sa["len_dev"], ld)

        # ----- Track B -----
        sess_key = (caller, int(t // 1800))
        if sess_key not in track_b:
            track_b[sess_key] = {
                "start": t,
                "end": t,
                "count": 0,
                "caller": caller,
                "new_op": 0.0,
                "new_prov": 0.0,
                "new_sub": 0.0,
                "new_rg": 0.0,
                "new_type": 0.0,
                "new_ip": 0.0,
                "ops": set(),
            }
        sb = track_b[sess_key]
        sb["end"] = t
        sb["count"] += 1
        sb["ops"].add(op)
        if op not in caller_ops.get(caller, set()):
            sb["new_op"] = 1.0
        if prov not in caller_provs.get(caller, set()):
            sb["new_prov"] = 1.0
        if sub not in caller_subs.get(caller, set()):
            sb["new_sub"] = 1.0
        if rg not in caller_rgs.get(caller, set()):
            sb["new_rg"] = 1.0
        if rtype not in caller_types.get(caller, set()):
            sb["new_type"] = 1.0
        if ip not in caller_ips.get(caller, set()):
            sb["new_ip"] = 1.0

    # Finalize Track A context flags
    for corr, cs in track_a_state.items():
        if len(cs["provs"]) > 1 or len(cs["rgs"]) > 1 or len(cs["subs"]) > 1:
            track_a[corr]["context"] = 1.0

    # Finalize Track B activity/hour deviations
    for sess_key, sb in track_b.items():
        caller = sb["caller"]
        cnt = sb["count"]
        m_cnt = caller_mean_rate.get(caller, 0.0)
        s_cnt = caller_std_rate.get(caller, 1.0)
        sb["act_dev"] = min(abs(cnt - m_cnt) / (s_cnt + 1e-6) / 5.0, 1.0)
        hr = (sb["start"] % 86400) / 3600.0
        m_hr = caller_mean_hour.get(caller, hr)
        sb["hr_dev"] = min(abs(hr - m_hr), 24 - abs(hr - m_hr)) / 12.0

    return track_a, track_a_state, track_b


# ---------------------------------------------------------------------------
# Ranking & output
# ---------------------------------------------------------------------------


def _rank_and_write(
    track_a: Dict, track_a_state: Dict, track_b: Dict, output_dir: Path
) -> None:
    def _ts(epoch: float) -> str:
        return datetime.fromtimestamp(epoch, timezone.utc).isoformat()

    # --- Track A ---
    structs = [s["struct"] for s in track_a.values()]
    raritys = [s["rarity"] for s in track_a.values()]
    durs = [s["dur_dev"] for s in track_a.values()]
    lens = [s["len_dev"] for s in track_a.values()]
    ctxs = [s["context"] for s in track_a.values()]
    logger.info(f"=== Track A Score Percentiles (p50/p90/p99) ===")
    logger.info(f"Struct:  {np.percentile(structs, [50, 90, 99])}")
    logger.info(f"Rarity:  {np.percentile(raritys, [50, 90, 99])}")
    logger.info(f"Duration:{np.percentile(durs,    [50, 90, 99])}")
    logger.info(f"Length:  {np.percentile(lens,    [50, 90, 99])}")
    logger.info(f"Context non-zero: {sum(1 for c in ctxs if c > 0)}")

    a_grouped = defaultdict(list)
    for corr, s in track_a.items():
        cs = track_a_state[corr]
        seq_context = " -> ".join(cs["ops"][-10:])
        pattern_key = (cs["caller"], seq_context, s["struct"], s["context"])
        a_grouped[pattern_key].append((corr, s, cs))

    a_rows = []
    for pattern_key, group in a_grouped.items():
        # Pick the representative (first) correlation ID
        corr, s, cs = group[0]
        pattern_count = len(group)

        tot = s["struct"] + s["rarity"] + s["dur_dev"] + s["len_dev"] + s["context"]

        eff_sig = 0
        if s["struct"] == 1.0:
            eff_sig += 1
        if s["rarity"] > 0.8 and s["struct"] < 0.5:
            eff_sig += 1
        if s["dur_dev"] > 0.8 and s["struct"] < 0.5:
            eff_sig += 1
        if s["context"] > 0:
            eff_sig += 1
        if s["len_dev"] > 0.8:
            eff_sig += 1

        parts = []
        if s["struct"] > 0.5:
            parts.append("unseen sequence")
        if s["dur_dev"] > 0.5:
            parts.append("unusual timing")
        if s["context"] > 0.5:
            parts.append("cross-boundary context shift")
        expl = (
            "CorrelationId exhibited " + " and ".join(parts)
            if parts
            else "Minor deviation."
        )

        seq_context = " -> ".join(cs["ops"][:10])
        a_rows.append(
            [
                f"{_ts(cs['start'])} — {_ts(cs['end'])}",
                cs["caller"],
                corr,
                round(tot, 3),
                eff_sig,
                pattern_count,
                round(s["struct"], 3),
                round(s["rarity"], 3),
                round(s["dur_dev"], 3),
                round(s["len_dev"], 3),
                round(s["context"], 3),
                expl,
                seq_context,
            ]
        )

    a_rows.sort(key=lambda x: (x[3], x[4]), reverse=True)
    top_total_a = a_rows[:20]
    ctx_ranked = sorted(a_rows, key=lambda x: (x[10], x[3], x[4]), reverse=True)
    top_context_a = [x for x in ctx_ranked if x[10] > 0 and x not in top_total_a][:20]

    a_headers = [
        "timestamp_range",
        "caller",
        "correlation_id",
        "total_score",
        "effective_signal_count",
        "pattern_count",
        "structural_violation",
        "sequence_rarity",
        "duration_deviation",
        "length_deviation",
        "context_inconsistency",
        "explanation",
        "sequence_context",
    ]
    _write_csv(
        output_dir / "top_lifecycle_anomalies.csv",
        a_headers,
        top_total_a + top_context_a,
    )

    # --- Track B ---
    b_rows = []
    for (caller, _), sb in track_b.items():
        tot = (
            sb["new_op"]
            + sb["new_prov"]
            + sb["new_sub"]
            + sb["new_rg"]
            + sb["new_type"]
            + sb["new_ip"]
            + sb["act_dev"]
            + sb["hr_dev"]
        )

        eff_sig = 0
        signals = {}
        if sb["new_op"] > 0:
            eff_sig += 1
            signals["New Operations"] = sb["new_op"]
        if sb["new_ip"] > 0:
            eff_sig += 1
            signals["New IP"] = sb["new_ip"]
        if sb["act_dev"] > 0.8:
            eff_sig += 1
            signals["Activity Spike"] = sb["act_dev"]
        if sb["hr_dev"] > 0.8:
            eff_sig += 1
            signals["Hour Deviation"] = sb["hr_dev"]
        if (
            sb["new_prov"] > 0
            or sb["new_sub"] > 0
            or sb["new_rg"] > 0
            or sb["new_type"] > 0
        ):
            eff_sig += 1
            signals["Context/Role Expansion"] = max(
                sb["new_prov"], sb["new_sub"], sb["new_rg"], sb["new_type"]
            )

        dominant_signal = (
            max(signals.items(), key=lambda x: x[1])[0] if signals else "None"
        )

        parts = []
        if sb["new_op"] > 0:
            parts.append("new operations")
        if sb["new_ip"] > 0:
            parts.append("new IP")
        if sb["act_dev"] > 0.8:
            parts.append("volume spike")
        if sb["hr_dev"] > 0.8:
            parts.append("unusual hour")
        expl = "Caller session: " + ", ".join(parts) if parts else "Minor deviation."
        b_rows.append(
            [
                f"{_ts(sb['start'])} — {_ts(sb['end'])}",
                caller,
                round(tot, 3),
                eff_sig,
                dominant_signal,
                round(sb["new_op"], 3),
                round(sb["new_prov"], 3),
                round(sb["new_sub"], 3),
                round(sb["new_rg"], 3),
                round(sb["new_type"], 3),
                round(sb["new_ip"], 3),
                round(sb["act_dev"], 3),
                round(sb["hr_dev"], 3),
                expl,
                ", ".join(list(sb["ops"])[:10]),
            ]
        )
    b_rows.sort(key=lambda x: (x[2], x[3]), reverse=True)

    b_headers = [
        "timestamp_range",
        "caller",
        "total_score",
        "effective_signal_count",
        "dominant_signal",
        "new_op",
        "new_prov",
        "new_sub",
        "new_rg",
        "new_type",
        "new_ip",
        "activity_dev",
        "hour_dev",
        "explanation",
        "session_context",
    ]
    _write_csv(output_dir / "top_actor_anomalies.csv", b_headers, b_rows[:100])

    _write_json(
        output_dir / "manifest.json",
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "track_a_scored": len(track_a),
            "track_b_scored": len(track_b),
            "track_a_deduplicated_patterns": len(a_grouped),
        },
    )

    logger.info(f"Artifacts written to {output_dir}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def train_and_score(input_path: Path, output_dir: Path, dry_run: bool = False) -> None:
    """
    Full pipeline: load → split → train → score → write artifacts.

    Parameters
    ----------
    input_path : Path
        Path to an Azure Activity Log CSV export.
    output_dir : Path
        Directory where output artifacts (CSVs, manifest) will be written.
    dry_run : bool
        If True, validate input and exit without scoring.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    events = load_events(input_path)

    if dry_run:
        logger.info(f"Dry run complete. {len(events):,} events validated. Schema OK.")
        return

    # Chronological 70 / 15 / 15 split
    t_min = events[0]["t"]
    t_max = events[-1]["t"]
    span = t_max - t_min
    b1 = t_min + 0.70 * span  # end of train
    b2 = t_min + 0.85 * span  # start of test

    train_events = [e for e in events if e["t"] < b1]
    test_events = [e for e in events if e["t"] >= b2]

    logger.info(
        f"Split — Train: {len(train_events):,} | Val: skipped | Test: {len(test_events):,}"
    )

    if not train_events:
        raise ValueError("Training set is empty. Check the input CSV timestamps.")
    if not test_events:
        raise ValueError(
            "Test set is empty. Dataset may be too small for a 70/15/15 split."
        )

    model = _train(train_events)
    track_a, track_a_state, track_b = _score(test_events, model)
    _rank_and_write(track_a, track_a_state, track_b, output_dir)
