# DeepLog Analytics Engine

## Overview
This repository contains a production-ready Behavioral Analytics Engine for Azure Cloud log data. Engineered to prioritize **actionable SOC intelligence**, **deterministic explainability**, and **strict operational hygiene**, this system bridges the gap between raw statistical anomaly detection and actionable incident response.

While originally conceived as an evaluation of deep learning sequence models, exhaustive empirical analysis proved that a robust, heuristic 5-gram baseline provides identical performance with vastly superior transparency and zero training overhead.

The canonical engine provides strict, human-readable structural and temporal anomaly alerts separated into two specialized tracks:
*   **Track A:** CorrelationId Lifecycle Violations (Cross-boundary shifts, critical deployment failures)
*   **Track B:** Caller Session Drift (Credential hijacking, automation spikes)

---

## Project Structure
This repository strictly adheres to a brutally minimal, product-ready architecture. All legacy research code, toy examples, and transient artifacts have been purged.

```
DeepLog/
├── src/deeplog/               # Core analytic engine module
│   ├── cli.py                 # Command Line Interface
│   └── engine/
│       ├── anomaly_generator.py # Core heuristic scoring and dual-queue sorting
│       ├── diagnostics.py       # Deterministic translation of statistical deviation to causal buckets
│       ├── diagnose_packet.py   # Generates the human-readable markdown packets
│       └── feedback.py          # Ground-truth analyst feedback lifecycle system
├── data/                      # Local storage for raw ingestion and feedback SQLite
├── docs/reports/              # The canonical generated output packets and handoff memos
└── setup.py                   # Standard package configuration
```

---

## How to Use the Product

The system operates via a streamlined Command Line Interface. It handles end-to-end anomaly generation, diagnostic translation, and feedback capture.

### 1. Generate SOC Review Packets
To execute the core engine across the datastore and generate the human-readable dual-track review packets:

```bash
python -m deeplog generate-anomalies
```
**Output:** This command deterministically generates **`docs/reports/diagnosed_review_packet.md`**. This is the canonical, SOC-ready document containing the top prioritized alerts enriched with causal explanations. It also outputs the raw diagnostic CSVs into `artifacts/explainable_anomalies/`.

### 2. Submit Analyst Feedback
Raw detection algorithms cannot safely unlearn or adjust without verified ground truth. SOC Analysts must review the `diagnosed_review_packet.md` and log their verdicts back into the isolated feedback subsystem.

```bash
python -m deeplog submit-feedback \
    --track A \
    --id "0b8882fb-0603-4d9f-9a5b-caced38a7142" \
    --decision CONFIRMED_ANOMALY \
    --reason "Verified cross-tenant credential drift."
```
**Valid Decisions:** `BENIGN_FALSE_POSITIVE`, `CONFIRMED_ANOMALY`, `UNREVIEWED`

This command safely logs the verdict into `data/feedback.sqlite`. This isolated database explicitly decouples human disagreement from the core detector, allowing downstream SIEM suppression without risking dangerous online model retraining.

---

## Canonical Deliverables
For architectural context, operational limitations, and academic reconciliation memos, refer strictly to the documents explicitly tracked in **`docs/reports/artifact_index.json`**. 

The definitive executive summary is available at **`docs/reports/project_handoff_summary.md`**.
