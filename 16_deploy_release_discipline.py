#!/usr/bin/env python3
"""
16_deploy_release_discipline.py

Jarvis Production DeepLog Release Discipline & Change Management Pipeline
-------------------------------------------------------------------------
Specifies production release discipline for future system updates:
  - Release checklist (release_checklist.json)
  - Sequential sign-off hierarchy (signoff_sequence.json)
  - Rollback authority policy (rollback_authority_policy.json)
  - Emergency change procedure (emergency_change_procedure.json)
  - Change communication templates (reports/change_communication_template.md)

Produces deliverables under: artifacts/release_discipline/
  - manifest.json
  - release_checklist.json
  - signoff_sequence.json
  - rollback_authority_policy.json
  - emergency_change_procedure.json
  - reports/change_communication_template.md

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
    format="%(asctime)s [%(levelname)s] release_discipline: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("release_discipline")

# -------------------------------------------------------------------------
# Constants & Paths
# -------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
SUBSTRATE_DIR = PROJECT_ROOT / "artifacts" / "production_substrate"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "release_discipline"


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
# Release Discipline Contract Builders
# -------------------------------------------------------------------------
def build_release_checklist() -> Dict[str, Any]:
    logger.info("Building Production Release Checklist Contract...")
    return {
        "checklist_name": "release_checklist",
        "checklist_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pre_release_verification_gates": [
            {"gate_id": "GATE_01", "name": "Substrate Schema Contract Alignment", "description": "Verify 9-field schema completeness & monotonic epoch ordering", "required": True},
            {"gate_id": "GATE_02", "name": "Vocabulary Frozen Compatibility", "description": "Verify 83-template operation mapping with 0.0% OOV on test set", "required": True},
            {"gate_id": "GATE_03", "name": "14-Day Shadow Mode Validation", "description": "Confirm zero-regression performance over 14-day bake-in period", "required": True},
            {"gate_id": "GATE_04", "name": "Synthetic Attack Regression Suite", "description": "Pass 100% of synthetic attack detection tests", "required": True},
            {"gate_id": "GATE_05", "name": "Git Commit SHA Anchoring", "description": "Verify change is anchored by clean git commit SHA in master", "required": True},
        ],
        "canary_rollout_gates": [
            {"canary_stage": "Stage 1 (10% Traffic)", "duration_hours": 48, "max_oov_rate": 0.0001, "max_alert_rate": 0.0010},
            {"canary_stage": "Stage 2 (100% Traffic)", "duration_hours": 168, "max_oov_rate": 0.0001, "max_alert_rate": 0.0010},
        ],
        "contract_status": "RELEASE_DISCIPLINE_ACTIVE",
    }


def build_signoff_sequence() -> Dict[str, Any]:
    logger.info("Building Sequential Sign-off Order Hierarchy...")
    return {
        "sequence_name": "signoff_sequence",
        "sequence_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "sequential_approval_hierarchy": [
            {
                "step_order": 1,
                "role_title": "Lead ML Security Engineer",
                "authority_scope": "Technical, Model Metric, & Cross-Entropy Validation",
                "signoff_required": True,
                "rejection_action": "Halt release, return to shadow mode",
            },
            {
                "step_order": 2,
                "role_title": "SOC Operations Lead",
                "authority_scope": "Alert Volume, Operator SLA, & Suppression Efficacy Approval",
                "signoff_required": True,
                "rejection_action": "Halt release, adjust threshold/suppression window",
            },
            {
                "step_order": 3,
                "role_title": "SIEM System Administrator",
                "authority_scope": "Infrastructure Throughput, Latency SLA (< 50ms), & Deployment Readiness",
                "signoff_required": True,
                "rejection_action": "Halt release, optimize worker throughput",
            },
            {
                "step_order": 4,
                "role_title": "Release Manager",
                "authority_scope": "Final Change Control Gate & Production Deployment Authorization",
                "signoff_required": True,
                "rejection_action": "Cancel Change Request (CR)",
            },
        ],
        "signoff_enforcement": "STRICT_SEQUENTIAL_ONLY",
        "contract_status": "RELEASE_DISCIPLINE_ACTIVE",
    }


def build_rollback_authority_policy() -> Dict[str, Any]:
    logger.info("Building Rollback Authority Policy...")
    return {
        "policy_name": "rollback_authority_policy",
        "policy_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "unilateral_rollback_authorities": [
            {"role": "On-Shift SOC Lead", "scope": "Immediate rollback during alert storms or high false-positive noise"},
            {"role": "Lead ML Security Engineer", "scope": "Immediate rollback upon detecting model drift or transition degradation"},
            {"role": "SIEM System Administrator", "scope": "Immediate rollback upon scoring latency SLA breach (> 50ms)"},
        ],
        "automated_rollback_triggers": [
            {"trigger_id": "AUTO_ROLLBACK_01", "condition": "Daily OOV Rate > 0.0050 (0.50%)", "action": "Revert to static baseline immediately"},
            {"trigger_id": "AUTO_ROLLBACK_02", "condition": "Daily Emitted Alert Rate > 0.0100 (1.00%)", "action": "Revert to static baseline immediately"},
            {"trigger_id": "AUTO_ROLLBACK_03", "condition": "P99 Event Scoring Latency > 50ms", "action": "Revert to marginal unconditioned model"},
        ],
        "rollback_execution_time_sla_minutes": 5,
        "contract_status": "RELEASE_DISCIPLINE_ACTIVE",
    }


def build_emergency_change_procedure() -> Dict[str, Any]:
    logger.info("Building Emergency Change Procedure Contract...")
    return {
        "procedure_name": "emergency_change_procedure",
        "procedure_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "emergency_break_glass_protocol": {
            "authorized_reasons": ["Active zero-day alert flood", "Critical pipeline worker crash", "Unscheduled cloud API schema change"],
            "required_joint_approval": ["On-Call SOC Lead", "On-Call Lead ML Engineer"],
            "max_deployment_time_minutes": 60,
            "post_facto_auditability": {
                "mandatory_cr_filing_hours": 2,
                "mandatory_retrospective_hours": 24,
                "audit_record_schema": "change_control_record_schema.json",
            },
        },
        "contract_status": "RELEASE_DISCIPLINE_ACTIVE",
    }


# -------------------------------------------------------------------------
# Main Execution Pipeline
# -------------------------------------------------------------------------
def main() -> None:
    logger.info("Initializing Jarvis Production DeepLog Release Discipline Pipeline...")

    release_chk = build_release_checklist()
    write_json_file(OUTPUT_DIR / "release_checklist.json", release_chk)

    signoff_seq = build_signoff_sequence()
    write_json_file(OUTPUT_DIR / "signoff_sequence.json", signoff_seq)

    rollback_auth = build_rollback_authority_policy()
    write_json_file(OUTPUT_DIR / "rollback_authority_policy.json", rollback_auth)

    emergency_proc = build_emergency_change_procedure()
    write_json_file(OUTPUT_DIR / "emergency_change_procedure.json", emergency_proc)

    manifest_data = {
        "source_file_path": str(SUBSTRATE_DIR.relative_to(PROJECT_ROOT)),
        "runtime_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "release_discipline_status": "RELEASE_DISCIPLINE_ACTIVE",
        "auditable_emergency_procedure": True,
        "artifact_files_created": [
            "manifest.json",
            "release_checklist.json",
            "signoff_sequence.json",
            "rollback_authority_policy.json",
            "emergency_change_procedure.json",
            "reports/change_communication_template.md",
        ],
    }
    write_json_file(OUTPUT_DIR / "manifest.json", manifest_data)

    logger.info("Generating markdown Change Communication Templates...")

    report_md = f"""# Production DeepLog Change Communication & Notification Templates
**Azure Activity Anomaly Detection POC**

## Executive Summary & Communication Standard

**COMMUNICATION STATUS**: **`RELEASE_DISCIPLINE_ACTIVE`**  
**RECIPIENT GROUPS**: **`SOC Operations, ML Engineering, System Administration, Executive IT Security`**

This document specifies the standardized change communication templates for approved and rejected updates to the DeepLog production anomaly detection pipeline.

---

## 1. Approved Change Deployment Notification Template

```markdown
# [APPROVED CHANGE DEPLOYMENT] Change Control Record: {{{{CHANGE_ID}}}}

**Target Component**: {{{{SUBSTRATE_SCHEMA | VOCABULARY | CONTROL_POLICY | MODEL_WEIGHTS}}}}
**Version Transition**: `{{{{VERSION_BEFORE}}}}` ────────► `{{{{VERSION_AFTER}}}}`
**Deployment Date/Time (UTC)**: {{{{YYYY-MM-DD THH:MM:SSZ}}}}
**Git Commit SHA**: `{{{{GIT_COMMIT_SHA}}}}`

### Executive Summary & Justification
{{{{BRIEF_JUSTIFICATION_TEXT}}}}

### Approval Sign-off Audit Trail
- [x] **Stage 1 (ML Security Engineer)**: Approved by {{{{APPROVER_ML}}}} at {{{{TIMESTAMP_ML}}}}
- [x] **Stage 2 (SOC Operations Lead)**: Approved by {{{{APPROVER_SOC}}}} at {{{{TIMESTAMP_SOC}}}}
- [x] **Stage 3 (SIEM Administrator)**: Approved by {{{{APPROVER_SIEM}}}} at {{{{TIMESTAMP_SIEM}}}}
- [x] **Stage 4 (Release Manager)**: Authorized by {{{{APPROVER_RM}}}} at {{{{TIMESTAMP_RM}}}}

### Deployment & Rollback Strategy
- **Rollout Method**: Blue/Green Canary Traffic Shift (10% Canary for 48 Hours)
- **Automatic Rollback Trigger**: OOV > 0.50% | Emitted Alert Rate > 1.00% | Latency > 50ms
- **Rollback Pre-Change Hash**: `{{{{ROLLBACK_HASH}}}}`
```

---

## 2. Rejected Change Notification Template

```markdown
# [REJECTED CHANGE REQUEST] Change Control Record: {{{{CHANGE_ID}}}}

**Target Component**: {{{{SUBSTRATE_SCHEMA | VOCABULARY | CONTROL_POLICY | MODEL_WEIGHTS}}}}
**Requested Version**: `{{{{VERSION_REQUESTED}}}}`
**Rejection Date/Time (UTC)**: {{{{YYYY-MM-DD THH:MM:SSZ}}}}

### Rejection Stage & Authority
- **Rejected At Stage**: {{{{STAGE_1_ML | STAGE_2_SOC | STAGE_3_SIEM | STAGE_4_RM}}}}
- **Rejecting Stakeholder**: {{{{REJECTOR_NAME_AND_ROLE}}}}

### Rejection Rationale & Disqualifying Criteria
{{{{DETAILED_REJECTION_REASON_TEXT}}}}

### Mandatory Remediation Steps Required Before Re-submission
1. {{{{REMEDIATION_STEP_1}}}}
2. {{{{REMEDIATION_STEP_2}}}}
3. Re-run 14-day shadow validation bake-in period.
```

---

## 3. Emergency Change (EC) Break-Glass Notification Template

```markdown
# [EMERGENCY CHANGE DEPLOYED] Incident Reference: {{{{INCIDENT_ID}}}}

**Change Control Record**: `{{{{CHANGE_ID}}}}` (Post-Facto)
**Execution Date/Time (UTC)**: {{{{YYYY-MM-DD THH:MM:SSZ}}}}
**Break-Glass Approvers**: {{{{SOC_LEAD_NAME}}}} (SOC) & {{{{ML_ENGINEER_NAME}}}} (ML)

### Emergency Rationale
{{{{EMERGENCY_REASON_TEXT}}}}

### Mandatory Post-Facto Audit Requirements
- [ ] File formal Change Control Record within **2 Hours** (SLA: {{{{DUE_TIME_2H}}}})
- [ ] Complete Post-Incident Retrospective Review within **24 Hours** (SLA: {{{{DUE_TIME_24H}}}})
```

---
*Template generated automatically by `16_deploy_release_discipline.py`.*
"""

    write_text_file(OUTPUT_DIR / "reports" / "change_communication_template.md", report_md)
    logger.info("Production DeepLog Release Discipline Pipeline completed successfully!")


if __name__ == "__main__":
    main()
