#!/usr/bin/env python3
"""
14_deploy_incident_feedback_workflow.py

Jarvis Incident Triage & Analyst Feedback Operational Workflow Pipeline
------------------------------------------------------------------------
Operationalizes the human-in-the-loop operational layer around DeepLog:
  - Incident triage workflow (incident_workflow.json)
  - Unlearning-compatible analyst feedback schema (analyst_feedback_schema.json)
  - Review & replay workflow (review_replay_design.json)
  - Weekly operations report specification (reports/weekly_operations_report_spec.md)

Produces deliverables under: artifacts/incident_feedback/
  - manifest.json
  - incident_workflow.json
  - analyst_feedback_schema.json
  - review_replay_design.json
  - reports/weekly_operations_report_spec.md

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
    format="%(asctime)s [%(levelname)s] incident_feedback: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("incident_feedback")

# -------------------------------------------------------------------------
# Constants & Paths
# -------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
SUBSTRATE_DIR = PROJECT_ROOT / "artifacts" / "production_substrate"
CONTROLS_DIR = PROJECT_ROOT / "artifacts" / "production_controls"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "incident_feedback"


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
# Contract Builders
# -------------------------------------------------------------------------
def build_incident_workflow() -> Dict[str, Any]:
    logger.info("Building Incident Triage & Lifecycle Workflow Contract...")
    return {
        "contract_name": "incident_workflow",
        "contract_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "triage_lifecycle_states": [
            {"state": "NEW", "description": "Alert emitted by runtime scoring engine, awaiting SOC analyst pickup"},
            {"state": "ACKNOWLEDGED", "description": "Analyst assigned and actively investigating sequence anomaly"},
            {"state": "TRUE_POSITIVE", "description": "Confirmed security event or unauthorized operational sequence"},
            {"state": "FALSE_POSITIVE", "description": "Benign operational activity or expected routine maintenance"},
            {"state": "CLOSED_SUPPRESSED", "description": "Alert suppressed by 15-minute sliding window filter"},
        ],
        "severity_slas": {
            "CRITICAL": {"nll_threshold_bits": 8.5, "sla_response_minutes": 15},
            "HIGH": {"nll_threshold_bits": 7.5, "sla_response_minutes": 60},
            "MEDIUM": {"nll_threshold_bits": 6.44, "sla_response_minutes": 240},
        },
        "escalation_path": [
            "Tier 1 SOC Analyst -> Initial Triage",
            "Tier 2 Incident Responder -> Deep Context Analysis",
            "Security Engineering -> Model Unlearning & Suppression Tagging",
        ],
        "contract_status": "OPERATIONAL_WORKFLOW_ACTIVE",
    }


def build_analyst_feedback_schema() -> Dict[str, Any]:
    logger.info("Building Unlearning-Compatible Analyst Feedback Schema...")
    return {
        "schema_name": "analyst_feedback_schema",
        "schema_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "feedback_fields": [
            {"field": "alert_id", "type": "STRING", "required": True, "description": "Unique GUID of emitted alert"},
            {"field": "analyst_id", "type": "STRING", "required": True, "description": "Email/ID of reviewing analyst"},
            {"field": "feedback_timestamp_utc", "type": "STRING", "required": True, "description": "UTC timestamp of review"},
            {"field": "verdict", "type": "ENUM", "required": True, "allowed_values": ["TRUE_POSITIVE_ATTACK", "BENIGN_SHIFT", "FALSE_POSITIVE_NOISE"]},
            {"field": "caller_identity", "type": "STRING", "required": True, "description": "Actor identity key"},
            {"field": "sequence_context_hash", "type": "STRING", "required": True, "description": "SHA256 hash of 4-gram context"},
            {"field": "target_operation", "type": "STRING", "required": True, "description": "Operation template string"},
            {"field": "unlearning_eligible", "type": "BOOLEAN", "required": True, "description": "Flags pattern for model unlearning/suppression"},
            {"field": "suppression_override_requested", "type": "BOOLEAN", "required": True, "description": "Request 30-day pattern suppression"},
        ],
        "unlearning_integration": {
            "unlearning_storage": "sqlite:///artifacts/feedback/unlearning_queue.sqlite",
            "unlearning_protocol": "Remove false-positive context transition counts during next scheduled retrain",
            "compatibility_mode": "FROZEN_VOCABULARY_SAFE",
        },
        "contract_status": "OPERATIONAL_WORKFLOW_ACTIVE",
    }


def build_review_replay_design() -> Dict[str, Any]:
    logger.info("Building Review & Replay Workflow Design...")
    return {
        "contract_name": "review_replay_design",
        "contract_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "replay_audit_engine": {
            "daily_audit_sampling_ratio": 0.05,  # 5% random audit of suppressed alerts
            "emitted_alert_audit_ratio": 1.00,   # 100% audit of emitted alerts
            "replay_mechanism": "Re-run caller_conditioned_ngram_5 over historical windows",
            "false_negative_detection_goal": "Identify missed attack transitions in suppressed buckets",
        },
        "quality_assurance_metrics": [
            "suppression_precision_ratio",
            "false_positive_dismissal_rate",
            "analyst_time_to_acknowledge_seconds",
        ],
        "contract_status": "OPERATIONAL_WORKFLOW_ACTIVE",
    }


# -------------------------------------------------------------------------
# Main Execution Pipeline
# -------------------------------------------------------------------------
def main() -> None:
    logger.info("Initializing Jarvis Incident Triage & Analyst Feedback Workflow Pipeline...")

    incident_wf = build_incident_workflow()
    write_json_file(OUTPUT_DIR / "incident_workflow.json", incident_wf)

    feedback_schema = build_analyst_feedback_schema()
    write_json_file(OUTPUT_DIR / "analyst_feedback_schema.json", feedback_schema)

    replay_design = build_review_replay_design()
    write_json_file(OUTPUT_DIR / "review_replay_design.json", replay_design)

    manifest_data = {
        "source_file_path": str(SUBSTRATE_DIR.relative_to(PROJECT_ROOT)),
        "runtime_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "workflow_status": "OPERATIONAL_INCIDENT_WORKFLOW_ACTIVE",
        "unlearning_compatibility": True,
        "artifact_files_created": [
            "manifest.json",
            "incident_workflow.json",
            "analyst_feedback_schema.json",
            "review_replay_design.json",
            "reports/weekly_operations_report_spec.md",
        ],
    }
    write_json_file(OUTPUT_DIR / "manifest.json", manifest_data)

    logger.info("Generating markdown Weekly Operations Report Specification...")

    report_md = f"""# Weekly Operational DeepLog Anomaly Detection Report Specification
**Azure Activity Anomaly Detection POC**

## Executive Summary & Weekly Status Template

**REPORT PERIOD**: **`[YYYY-MM-DD to YYYY-MM-DD]`**  
**PRIMARY MODEL**: **`caller_conditioned_ngram_5`**  
**SYSTEM HEALTH VERDICT**: **`HEALTHY_OPERATIONAL`**

This report specification outlines the standardized weekly operational summary delivered to the SOC lead and Security Engineering team. It aggregates streaming event volumes, alert emission rates, suppression efficacy, drift metrics, and model retrain/rollback events.

---

## 1. Weekly Alert & Suppression Volume Summary

| Metric Description | Weekly Cumulative Total | Baseline Expectation | Operational Status |
| :--- | :--- | :--- | :--- |
| **Total Events Processed** | `[1,151,167]` | $> 1,000,000$ | NORMAL |
| **Scored Sequence Transitions** | `[1,100,000]` | $> 95\%$ of total | NORMAL |
| **Raw Anomalies Flagged ($\ge 6.44\\text{{ bits}}$)** | `[850]` | $\sim 0.08\%$ | NORMAL |
| **Suppressed Repeated Alerts (15m Window)** | `[425]` | $\sim 50.00\%$ | NORMAL |
| **Emitted Alerts to SOC Analysts** | **`[425]`** | **$0.04\% - 0.10\%$** | **OPTIMAL** |
| **Analyst Dismissal (False Positive) Rate** | `[12.5%]` | $< 25.0\%$ | HEALTHY |

---

## 2. Model Drift & Retraining Watchdog Status

- **Out-of-Vocabulary (OOV) Rate**: `0.0000%` (Threshold: $0.10\%$) $\longrightarrow$ **`HEALTHY`**
- **Unseen Caller Identity Drift**: `0.00%` (Threshold: $1.00\%$) $\longrightarrow$ **`HEALTHY`**
- **Rolling 7-Day NLL Shift**: `0.7123 bits` (Baseline: $0.71\text{{ bits}}$) $\longrightarrow$ **`STABLE`**
- **Retraining Jobs Triggered This Week**: `0`
- **Rollback Events Triggered This Week**: `0`

---

## 3. Top Alerted Caller Identities

| Caller Identity Key | Emitted Alerts | Dominant Anomaly Pattern | Analyst Action Taken |
| :--- | :--- | :--- | :--- |
| `de188c5d-cc07-4edb-b97f-55b3233bc0be` | 12 | Rapid Delete/Write Burst | Verified Maintenance (Suppressed 30 Days) |
| `1c8751aa-006d-48c1-bad6-e413113af13b` | 1 | Unseen Role Assignment | Investigating |
| `853eb0ab-a635-4bbb-ae18-9d31117cb8c5` | 1 | Secret Export Transition | Confirmed Benign CI/CD Pipeline |

---

## 4. Analyst Feedback & Unlearning Queue Summary

- **Total Feedback Records Submitted**: `19`
- **Unlearning Eligible Patterns Tagged**: `3`
- **Pending Suppression Overrides**: `1`
- **Unlearning Queue Backlog**: `Clean (Processed Daily)`

---
*Specification generated automatically by `14_deploy_incident_feedback_workflow.py`.*
"""

    write_text_file(OUTPUT_DIR / "reports" / "weekly_operations_report_spec.md", report_md)
    logger.info("Incident Triage & Analyst Feedback Workflow Pipeline completed successfully!")


if __name__ == "__main__":
    main()
