# DeepLog Analytics Engine

Behavioral anomaly detection for Azure Cloud Activity Logs.  
Deterministic. Explainable. SOC-ready. No training infrastructure required.

---

## Install

```bash
pip install .
```

Requires Python ≥ 3.9. The only runtime dependency is `numpy`.

---

## Quickstart

### 1. Analyze a log export

Point the engine at any Azure Activity Log CSV export:

```bash
deeplog analyze --input path/to/activity_logs.csv --output-dir ./reports
```

**Output** — written to `./reports/`:
| File | Contents |
|---|---|
| `diagnosed_review_packet.md` | Human-readable SOC triage packet with causal explanations |
| `top_lifecycle_anomalies.csv` | Track A: CorrelationId lifecycle violations |
| `top_actor_anomalies.csv` | Track B: Caller session drift |
| `manifest.json` | Run metadata |

Validate your CSV schema without scoring:
```bash
deeplog analyze --input logs.csv --dry-run
```

### 2. Submit analyst feedback

After reviewing the packet, log your verdict:

```bash
deeplog submit-feedback \
    --track A \
    --id "0b8882fb-0603-4d9f-9a5b-caced38a7142" \
    --decision CONFIRMED_ANOMALY \
    --reason "Verified cross-tenant lateral movement."
```

Valid decisions: `CONFIRMED_ANOMALY` | `BENIGN_FALSE_POSITIVE` | `UNREVIEWED`

Verdicts are written to `data/feedback.sqlite` (override with `--db path/to/db.sqlite`).  
This database is intentionally decoupled from the detector — logging disagreement does not change the model.

---

## Input CSV Schema

The input CSV must contain these columns (case-insensitive, spaces or underscores accepted):

| Column | Description |
|---|---|
| `timestamp_epoch` | Unix epoch timestamp (float) |
| `operation` | Azure operation type |
| `provider` | Resource provider |
| `caller` | Identity (UPN or ObjectId) |
| `caller_ip` | Source IP address |
| `subscription` | Subscription ID |
| `resource_group` | Resource group name |
| `resource_type` | Resource type |
| `correlation_id` | Azure correlation ID |

---

## What It Detects

The engine applies a **caller-conditioned 5-gram model** on a strict 70/15/15 chronological split, surfacing anomalies across two tracks:

**Track A — CorrelationId Lifecycle**
- Unseen operation sequences for a caller
- Timing deviations (Z-score > 5σ from historical baseline)
- Cross-boundary context shifts (providers, resource groups, subscriptions)

**Track B — Caller 30-Minute Session Drift**
- Net-new operations, IPs, resource groups, subscriptions never seen in training
- Extreme volume spikes or off-hours activity

Each alert is automatically translated into a deterministic causal category (e.g., "Critical Deployment/Migration Shift", "Lateral Boundary Crossing") for direct SOC triage.

---

## Repository Structure

```
src/deeplog/
├── cli.py                    # Entry point: analyze | submit-feedback
└── engine/
    ├── anomaly_generator.py  # Core 5-gram scoring engine
    ├── diagnostics.py        # Statistical → causal category mapping
    ├── diagnose_packet.py    # Markdown SOC packet generator
    └── feedback.py           # Analyst verdict persistence
tests/
└── test_smoke.py             # Integration smoke tests
docs/reports/                 # Handoff memos and academic reconciliation docs
```

---

## Handoff Documentation

| Document | Purpose |
|---|---|
| [project_handoff_summary.md](docs/reports/project_handoff_summary.md) | Executive summary: what is proven, what is not |
| [paper_vs_project_scope.md](docs/reports/paper_vs_project_scope.md) | Academic paper vs. implementation scope |
| [operational_limitations.md](docs/reports/operational_limitations.md) | Known constraints |
| [verdict_effectiveness_report.md](docs/reports/verdict_effectiveness_report.md) | Diagnosis bucket precision analysis |
