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
| `top_lifecycle_anomalies.csv` | Track A: CorrelationId lifecycle violations (scored + ranked) |
| `top_actor_anomalies.csv` | Track B: Caller session drift (scored + ranked) |
| `manifest.json` | Run metadata and event counts |

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

Verdicts are written to `data/feedback.sqlite`. This database is intentionally decoupled from the detector — logging disagreement does not change the model.

---

## Input CSV Schema

The engine auto-detects two CSV schemas. You do **not** need to preprocess your export.

### Native Azure Activity Log (from Log Analytics / Azure Monitor)

| Column | Description |
|---|---|
| `TimeGenerated` | ISO8601 timestamp (e.g. `2026-07-13T09:59:09.530875+00:00`) |
| `OperationNameValue` | Azure operation (e.g. `MICROSOFT.SQL/SERVERS/DATABASES/WRITE`) |
| `ResourceProviderValue` | Resource provider (e.g. `MICROSOFT.SQL`) |
| `Caller` | Identity UPN or ObjectId |
| `CallerIpAddress` | Source IP address |
| `SubscriptionId` | Subscription ID |
| `ResourceGroup` | Resource group name |
| `CorrelationId` | Azure correlation ID |

`resource_type` is derived from `OperationNameValue` automatically.

### Pre-processed Format

| Column | Description |
|---|---|
| `timestamp_epoch` | Unix epoch float |
| `operation` | Operation string |
| `provider` | Resource provider |
| `caller` | Identity |
| `caller_ip` | Source IP |
| `subscription` | Subscription ID |
| `resource_group` | Resource group |
| `resource_type` | Resource type |
| `correlation_id` | Correlation ID |

---

## What It Detects

The engine applies a **caller-conditioned 5-gram model** on a strict 70/15/15 chronological split. Empirically verified to match LSTM accuracy on this dataset with full deterministic explainability.

**Track A — CorrelationId Lifecycle**
- Unseen operation sequences for a caller (structural violation)
- Timing deviations (Z-score > 5σ from historical baseline)
- Cross-boundary context shifts (providers, resource groups, subscriptions mid-lifecycle)

**Track B — Caller 30-Minute Session Drift**
- Net-new operations, IPs, resource groups, or subscriptions never seen in training
- Extreme volume spikes or off-hours activity

Each alert is translated into a deterministic causal category (e.g. `Lateral Boundary Crossing`, `Possible Credential/Token Compromise`) for direct SOC triage.

---

## Repository Structure

```
src/deeplog/
├── cli.py                    # Entry point: analyze | submit-feedback
└── engine/
    ├── anomaly_generator.py  # Core 5-gram scoring engine (auto-detects Azure CSV schema)
    ├── diagnostics.py        # Statistical score → causal category mapping
    ├── diagnose_packet.py    # Markdown SOC packet generator
    └── feedback.py           # Analyst verdict persistence (SQLite)
tests/
└── test_smoke.py             # Integration smoke tests (synthetic data)
docs/
├── reports/                  # Product-facing: handoff summary, limitations, SOC packet
└── research/                 # Academic context: paper reviews, reconciliation memos
```

---

## Documentation

| Document | Purpose |
|---|---|
| [project_handoff_summary.md](docs/reports/project_handoff_summary.md) | Executive summary: what is proven, what is not |
| [operational_limitations.md](docs/reports/operational_limitations.md) | Known constraints (zero-day bias, threshold saturation, etc.) |
| [DeepLog_ByeBye_Findings_Report.md](docs/research/DeepLog_ByeBye_Findings_Report.md) | Paper review: DeepLog (CCS 2017) and ByeBye |
| [paper_vs_project_scope.md](docs/research/paper_vs_project_scope.md) | What the papers prove vs. what this implementation proves |
