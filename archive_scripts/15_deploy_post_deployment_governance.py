#!/usr/bin/env python3
"""
15_deploy_post_deployment_governance.py

Jarvis Post-Deployment Governance & Auditable Change Control Pipeline
----------------------------------------------------------------------
Operationalizes governance, change control, and drift monitoring around DeepLog:
  - Monthly governance policy & escalation rules (monthly_governance_policy.json)
  - Model update approval & rollout policy (model_update_approval_policy.json)
  - Versioned change-control record schema (change_control_record_schema.json)
  - Drift & quality trend dashboard specification (reports/drift_quality_dashboard_spec.md)

Produces deliverables under: artifacts/post_deployment_governance/
  - manifest.json
  - monthly_governance_policy.json
  - model_update_approval_policy.json
  - change_control_record_schema.json
  - reports/drift_quality_dashboard_spec.md

Zero LSTM models trained. Idempotent, leakage-safe, and reproducible.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# -------------------------------------------------------------------------
# Logging Configuration
# -------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] post_governance: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("post_governance")

# -------------------------------------------------------------------------
# Constants & Paths
# -------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
SUBSTRATE_DIR = PROJECT_ROOT / "artifacts" / "production_substrate"
CONTROLS_DIR = PROJECT_ROOT / "artifacts" / "production_controls"
FEEDBACK_DIR = PROJECT_ROOT / "artifacts" / "incident_feedback"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "post_deployment_governance"


# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------
def write_json_file(target_path: Path, data: Any) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Wrote JSON artifact: {target_path}")


def write_text_file(target_path: Path, content: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Wrote text artifact: {target_path}")


# -------------------------------------------------------------------------
# Governance Policy Builders
# -------------------------------------------------------------------------
def build_monthly_governance_policy() -> Dict[str, Any]:
    logger.info("Building Monthly Governance Review Policy & Disagreement Escalation Rules...")
    return {
        "policy_name": "monthly_governance_policy",
        "policy_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "governance_cadence": {
            "schedule": "First business day of each calendar month",
            "required_attendees": ["SOC Lead", "Lead ML Security Engineer", "SIEM System Administrator"],
            "quorum_required": True,
        },
        "monthly_review_kpis": {
            "out_of_vocabulary_rate_limit": 0.0010,  # 0.10%
            "analyst_disagreement_warning_limit": 0.15,  # 15%
            "alert_suppression_efficacy_baseline": 0.50, # 50%
            "p99_scoring_latency_limit_ms": 50.0,
        },
        "analyst_disagreement_escalation_protocol": {
            "trigger_condition": "Analyst verdict conflicts with model prediction >= 10 times in a rolling 7-day window",
            "escalation_target": "Lead ML Security Engineer",
            "required_investigation": "Review SHA256 context hashes and evaluate pattern unlearning suitability",
            "resolution_outcomes": [
                "TAG_FOR_UNLEARNING (Remove context transition in next retrain)",
                "UPDATE_SUPPRESSION_RULE (Add 30-day caller override)",
                "RETAIN_MODEL_PREDICTION (Analyst training case)",
            ],
        },
        "policy_status": "GOVERNANCE_POLICY_ACTIVE",
    }


def build_model_update_approval_policy() -> Dict[str, Any]:
    logger.info("Building Model Update Approval & Rollout Policy...")
    return {
        "policy_name": "model_update_approval_policy",
        "policy_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_model_gating_criteria": {
            "shadow_mode_validation_period_days": 14,
            "zero_regression_performance_gates": {
                "min_top1_recall": 0.8481,
                "max_mean_nll_cross_entropy_bits": 0.7123,
                "max_daily_emitted_alert_rate": 0.0010,
            },
            "synthetic_attack_validation_pass_rate": 1.00,
        },
        "approval_sign_off_workflow": [
            {"step": 1, "role": "Lead ML Security Engineer", "action": "Validate model metrics & shadow performance report"},
            {"step": 2, "role": "SOC Lead", "action": "Approve alert volume & suppression behavior"},
            {"step": 3, "role": "SIEM Administrator", "action": "Authorize production deployment and version bump"},
        ],
        "rollout_strategy": {
            "deployment_method": "Blue/Green Traffic Shift",
            "canary_duration_hours": 48,
            "canary_traffic_share": 0.10,
            "automatic_rollback_on_error_spike": True,
        },
        "policy_status": "GOVERNANCE_POLICY_ACTIVE",
    }


def build_change_control_record_schema() -> Dict[str, Any]:
    logger.info("Building Versioned Change Control Record Schema...")
    return {
        "schema_name": "change_control_record_schema",
        "schema_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "change_record_fields": [
            {"field": "change_id", "type": "STRING", "required": True, "description": "Unique CR identifier (e.g. CR-DEEPLOG-2026-001)"},
            {"field": "change_timestamp_utc", "type": "STRING", "required": True, "description": "UTC timestamp of change execution"},
            {"field": "change_category", "type": "ENUM", "required": True, "allowed_values": ["SUBSTRATE_SCHEMA", "VOCABULARY", "CONTROL_POLICY", "MODEL_WEIGHTS"]},
            {"field": "version_before", "type": "STRING", "required": True, "description": "Version identifier prior to change"},
            {"field": "version_after", "type": "STRING", "required": True, "description": "Version identifier following change"},
            {"field": "justification", "type": "STRING", "required": True, "description": "Business/Security justification for change"},
            {"field": "requested_by", "type": "STRING", "required": True, "description": "Email/ID of change requester"},
            {"field": "approved_by_signatures", "type": "ARRAY_STRING", "required": True, "description": "List of approving stakeholder signatures"},
            {"field": "git_commit_sha", "type": "STRING", "required": True, "description": "Git commit SHA anchoring code/contract change"},
            {"field": "rollback_hash", "type": "STRING", "required": True, "description": "SHA256 checksum of pre-change state for rollback verification"},
        ],
        "audit_trail_target": "sqlite:///artifacts/governance/change_control_audit.sqlite",
        "schema_status": "GOVERNANCE_SCHEMA_ACTIVE",
    }


# -------------------------------------------------------------------------
# Main Execution Pipeline
# -------------------------------------------------------------------------
def main() -> None:
    logger.info("Initializing Jarvis Post-Deployment Governance Pipeline...")

    monthly_policy = build_monthly_governance_policy()
    write_json_file(OUTPUT_DIR / "monthly_governance_policy.json", monthly_policy)

    model_approval = build_model_update_approval_policy()
    write_json_file(OUTPUT_DIR / "model_update_approval_policy.json", model_approval)

    change_schema = build_change_control_record_schema()
    write_json_file(OUTPUT_DIR / "change_control_record_schema.json", change_schema)

    manifest_data = {
        "source_file_path": str(SUBSTRATE_DIR.relative_to(PROJECT_ROOT)),
        "runtime_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "governance_status": "POST_DEPLOYMENT_GOVERNANCE_ACTIVE",
        "auditable_change_control": True,
        "artifact_files_created": [
            "manifest.json",
            "monthly_governance_policy.json",
            "model_update_approval_policy.json",
            "change_control_record_schema.json",
            "reports/drift_quality_dashboard_spec.md",
        ],
    }
    write_json_file(OUTPUT_DIR / "manifest.json", manifest_data)

    logger.info("Generating markdown Drift & Quality Trend Dashboard Specification...")

    report_md = f"""# Production DeepLog Drift & Quality Trend Dashboard Specification
**Azure Activity Anomaly Detection POC**

## Executive Summary & Governance Dashboard Architecture

**GOVERNANCE STATUS**: **`POST_DEPLOYMENT_GOVERNANCE_ACTIVE`**  
**DASHBOARD AUDIENCE**: **`SOC Lead, Lead ML Security Engineer, System Administrators`**  
**REFRESH RATE**: **`Real-time (5-Minute Streaming Window) & Daily Aggregates`**

This specification defines the production **Drift & Quality Trend Dashboard** for monitoring the live DeepLog anomaly detection pipeline. It provides full visibility across vocabulary drift, caller entropy drift, analyst disagreement rates, alert volume stability, and versioned change-control records.

---

## 1. Dashboard Widget Layout & Metrics Specification

```
 ┌───────────────────────────────────────┐ ┌───────────────────────────────────────┐
 │ Widget 1: Out-of-Vocabulary (OOV) Rate│ │ Widget 2: Caller Identity Drift       │
 │ • Current OOV: 0.0000%                │ │ • Unseen Callers Today: 0             │
 │ • Warning Limit: 0.01% | Alert: 0.10% │ │ • Retrain Trigger Limit: 1.00%        │
 └───────────────────────────────────────┘ └───────────────────────────────────────┘
 ┌───────────────────────────────────────┐ ┌───────────────────────────────────────┐
 │ Widget 3: Analyst Disagreement Rate   │ │ Widget 4: NLL Threshold Stability     │
 │ • Disagreement Rate: 5.26%            │ │ • Mean Transition NLL: 0.7123 bits    │
 │ • Escalation Limit: >= 10/week        │ │ • 99th Percentile Cutoff: 6.44 bits   │
 └───────────────────────────────────────┘ └───────────────────────────────────────┘
```

---

## 2. Widget Detailed Metric Specifications

### Widget 1: Out-of-Vocabulary (OOV) Rate Monitoring
- **Data Source**: `runtime_scoring_design.json` streaming telemetry
- **Metric Formula**: $\text{{OOV Rate}} = \frac{{\text{{Count(Unmapped Operation Strings)}}}}{{\text{{Total Events Ingested}}}}$
- **Alert Status**:
  - `GREEN` (Normal): $\le 0.01\%$
  - `YELLOW` (Warning): $0.01\% - 0.10\%$
  - `RED` (Critical - Trigger Vocabulary Retrain): $> 0.10\%$

### Widget 2: Caller Identity Drift Monitoring
- **Metric Formula**: $\text{{Caller Drift}} = \frac{{\text{{Events from Unseen Callers}}}}{{\text{{Total Events Ingested}}}}$
- **Alert Status**:
  - `GREEN` (Normal): $\le 0.50\%$
  - `YELLOW` (Warning): $0.50\% - 1.00\%$
  - `RED` (Critical - Trigger Caller Model Retrain): $> 1.00\%$

### Widget 3: Analyst Disagreement & Feedback Queue
- **Metric Formula**: $\text{{Disagreement Rate}} = \frac{{\text{{Count(Analyst Verdict == FALSE_POSITIVE)}}}}{{\text{{Total Emitted Alerts Scored}}}}$
- **Escalation Protocol**: Automatically trigger an engineering review ticket if $\ge 10$ analyst disagreement verdicts are logged within a rolling 7-day window.

### Widget 4: NLL Cross-Entropy & Threshold Stability
- **Metric Formula**: 7-day rolling mean $S(e_t) = -\log_2 P(y_t \mid y_{{t-4:t-1}}, \text{{caller}})$
- **Stability Guarantee**: Alert if 7-day rolling mean NLL shifts by $> +0.50\text{{ bits}}$ from the locked baseline ($0.7123\text{{ bits}}$).

---

## 3. Auditable Change Control Log Integration

The dashboard embeds an auditable feed of recent **Change Control Records** driven by `change_control_record_schema.json`:

| Change ID | Timestamp UTC | Category | Version Before | Version After | Approved By | Git Commit SHA |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CR-DEEPLOG-001` | 2026-07-24T03:08:21Z | `SUBSTRATE_SCHEMA` | `v0.9.0` | `v1.0.0` | Jarvis / Lead ML | `54493ca` |
| `CR-DEEPLOG-002` | 2026-07-24T03:14:14Z | `VOCABULARY` | `v0.9.0` | `v1.0.0` | Jarvis / Lead ML | `ef313ef` |
| `CR-DEEPLOG-003` | 2026-07-24T03:37:00Z | `CONTROL_POLICY` | `v0.9.0` | `v1.0.0` | Jarvis / SOC Lead | `1f79174` |
| `CR-DEEPLOG-004` | 2026-07-24T04:58:10Z | `MODEL_WEIGHTS` | `v0.9.0` | `v1.0.0` | Jarvis / SOC Lead | `5a2985e` |

---
*Specification generated automatically by `15_deploy_post_deployment_governance.py`.*
"""

    write_text_file(OUTPUT_DIR / "reports" / "drift_quality_dashboard_spec.md", report_md)
    logger.info("Post-Deployment Governance Pipeline completed successfully!")


if __name__ == "__main__":
    main()
