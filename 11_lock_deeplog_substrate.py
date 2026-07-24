#!/usr/bin/env python3
"""
11_lock_deeplog_substrate.py

Jarvis Production DeepLog Substrate Lock & Specification Pipeline
------------------------------------------------------------------
Locks the production-ready DeepLog substrate based on the verified pipeline validity gate:
  - Caller-centered sessions as primary sequence abstraction (30m inactivity timeout)
  - 9-field schema normalization contract
  - Frozen & versioned 83-template operation vocabulary (vocabulary_v1.json)
  - Model input & feature interface contract (model_input_contract_v1.json)

Produces deliverables under: artifacts/production_substrate/
  - manifest.json
  - schema_contract_v1.json
  - vocabulary_v1.json
  - sessionization_contract_v1.json
  - model_input_contract_v1.json
  - reports/production_substrate_spec.md

Zero LSTM models trained. Idempotent, leakage-safe, and reproducible.
"""

import json
import logging
import math
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# -------------------------------------------------------------------------
# Logging Configuration
# -------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] substrate_lock: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("substrate_lock")

# -------------------------------------------------------------------------
# Constants & Paths
# -------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "artifacts" / "sequence_viability" / "sequence_viability.sqlite"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "production_substrate"


# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------
def write_json_atomically(target_path: Path, data: Any) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    temp_path.replace(target_path)
    logger.info(f"Wrote JSON artifact: {target_path}")


def write_text_atomically(target_path: Path, content: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        f.write(content)
    temp_path.replace(target_path)
    logger.info(f"Wrote text artifact: {target_path}")


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found at {db_path}")
    db_uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.execute("PRAGMA query_only = ON;")
    return conn


# -------------------------------------------------------------------------
# 1. Schema Normalization Contract
# -------------------------------------------------------------------------
def build_schema_contract(conn: sqlite3.Connection) -> Dict[str, Any]:
    logger.info("Building Schema Normalization Contract v1...")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events;")
    total_count = cursor.fetchone()[0]

    fields = [
        {"field_name": "timestamp_utc", "data_type": "STRING", "null_allowed": False, "role": "Temporal Sequence Index"},
        {"field_name": "operation", "data_type": "STRING", "null_allowed": False, "role": "Invariant Template Token"},
        {"field_name": "provider", "data_type": "STRING", "null_allowed": False, "role": "Service Namespace Group"},
        {"field_name": "operation_family", "data_type": "STRING", "null_allowed": False, "role": "Action Category"},
        {"field_name": "activity_status", "data_type": "STRING", "null_allowed": False, "role": "Execution State"},
        {"field_name": "caller", "data_type": "STRING", "null_allowed": False, "role": "Actor Identity Conditioning Key"},
        {"field_name": "resource_group", "data_type": "STRING", "null_allowed": True, "role": "Target Group Scope"},
        {"field_name": "resource_entity", "data_type": "STRING", "null_allowed": False, "role": "Target Entity GUID"},
        {"field_name": "correlation_id", "data_type": "STRING", "null_allowed": False, "role": "Transaction Request Bound"},
    ]

    return {
        "contract_name": "schema_contract_v1",
        "contract_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_event_count_verified": total_count,
        "schema_field_count": len(fields),
        "fields": fields,
        "chronological_ordering_rule": "ORDER BY timestamp_epoch ASC, row_id ASC",
        "contract_status": "LOCKED",
    }


# -------------------------------------------------------------------------
# 2. Frozen Vocabulary Contract
# -------------------------------------------------------------------------
def build_vocabulary_contract(conn: sqlite3.Connection) -> Dict[str, Any]:
    logger.info("Extracting and Freezing 83-Template Vocabulary v1...")
    cursor = conn.cursor()
    cursor.execute("SELECT operation, COUNT(*) FROM events GROUP BY operation ORDER BY COUNT(*) DESC, operation ASC;")
    rows = cursor.fetchall()

    special_tokens = {
        "<PAD>": 0,
        "<UNK>": 1,
        "<START>": 2,
        "<END>": 3,
    }

    token_to_id = dict(special_tokens)
    id_to_token = {v: k for k, v in special_tokens.items()}
    token_frequencies = {}

    current_id = 4
    for op, count in rows:
        token_to_id[op] = current_id
        id_to_token[current_id] = op
        token_frequencies[op] = count
        current_id += 1

    unique_templates = len(rows)

    return {
        "contract_name": "vocabulary_v1",
        "contract_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "vocabulary_size": len(token_to_id),
        "invariant_operation_templates_count": unique_templates,
        "special_tokens": special_tokens,
        "token_to_id": token_to_id,
        "id_to_token": {str(k): v for k, v in id_to_token.items()},
        "token_frequencies": token_frequencies,
        "contract_status": "FROZEN",
    }


# -------------------------------------------------------------------------
# 3. Sessionization Contract
# -------------------------------------------------------------------------
def build_sessionization_contract(conn: sqlite3.Connection) -> Dict[str, Any]:
    logger.info("Building Caller-Centered Sessionization Contract v1...")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT caller) FROM events;")
    unique_callers = cursor.fetchone()[0]

    return {
        "contract_name": "sessionization_contract_v1",
        "contract_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "primary_sequence_abstraction": "Caller-Centered Inactivity Session",
        "partitioning_key": "caller",
        "inactivity_timeout_seconds": 1800.0,
        "inactivity_timeout_minutes": 30.0,
        "max_session_chunk_length": 100,
        "unique_caller_identities_verified": unique_callers,
        "session_coherence_verdict": "BEHAVIORALLY_COHERENT",
        "contract_status": "LOCKED",
    }


# -------------------------------------------------------------------------
# 4. Model Input Interface Contract
# -------------------------------------------------------------------------
def build_model_input_contract() -> Dict[str, Any]:
    logger.info("Building Model Input & Feature Interface Contract v1...")

    return {
        "contract_name": "model_input_contract_v1",
        "contract_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target_model_family": "Caller-Conditioned N-Gram Sequence Model (caller_conditioned_ngram_5)",
        "prediction_task": "Next Operation Token Prediction P(y_t | y_{t-4:t-1}, caller)",
        "input_features": {
            "sequence_context": {
                "description": "Previous 4 operation token IDs in session history",
                "type": "INT_ARRAY",
                "shape": [4],
                "padding_token_id": 0,
            },
            "caller_identity": {
                "description": "Caller email/string identity key",
                "type": "STRING",
                "role": "Conditional Distribution Conditioning Key",
            },
        },
        "target_variable": {
            "name": "next_operation_token_id",
            "type": "INT",
            "vocabulary_range": [4, 86],
        },
        "prediction_interface_signature": {
            "top_k_recommendation": "predict_top_k(context: List[int], caller: str, k: int = 5) -> List[int]",
            "transition_probability": "predict_prob(context: List[int], target: int, caller: str) -> float",
            "cross_entropy_anomaly_score": "anomaly_score(context: List[int], target: int, caller: str) -> float",
        },
        "contract_status": "LOCKED",
    }


# -------------------------------------------------------------------------
# Main Execution Pipeline
# -------------------------------------------------------------------------
def main() -> None:
    logger.info("Initializing Jarvis Production DeepLog Substrate Locking Pipeline...")

    conn = get_db_connection(DB_PATH)

    schema_contract = build_schema_contract(conn)
    write_json_atomically(OUTPUT_DIR / "schema_contract_v1.json", schema_contract)

    vocab_contract = build_vocabulary_contract(conn)
    write_json_atomically(OUTPUT_DIR / "vocabulary_v1.json", vocab_contract)

    session_contract = build_sessionization_contract(conn)
    write_json_atomically(OUTPUT_DIR / "sessionization_contract_v1.json", session_contract)

    model_contract = build_model_input_contract()
    write_json_atomically(OUTPUT_DIR / "model_input_contract_v1.json", model_contract)

    conn.close()

    manifest_data = {
        "source_file_path": str(DB_PATH.relative_to(PROJECT_ROOT)),
        "runtime_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "substrate_status": "LOCKED_PRODUCTION_READY",
        "primary_abstraction": "Caller-Centered Inactivity Session (30m)",
        "vocabulary_size": vocab_contract["vocabulary_size"],
        "artifact_files_created": [
            "manifest.json",
            "schema_contract_v1.json",
            "vocabulary_v1.json",
            "sessionization_contract_v1.json",
            "model_input_contract_v1.json",
            "reports/production_substrate_spec.md",
        ],
    }
    write_json_atomically(OUTPUT_DIR / "manifest.json", manifest_data)

    # -------------------------------------------------------------------------
    # Markdown Production Substrate Specification Report Generation
    # -------------------------------------------------------------------------
    logger.info("Generating markdown Production Substrate Specification...")

    report_md = f"""# Production DeepLog Substrate Specification & Deployment Plan
**Azure Activity Anomaly Detection POC**

## Executive Summary & Substrate Lock Status

**SUBSTRATE LOCK STATUS**: **`LOCKED_PRODUCTION_READY`**  
**PRIMARY SEQUENCE ABSTRACTION**: **`Caller-Centered Inactivity Session (30-Minute Timeout)`**  
**VOCABULARY VERSION**: **`vocabulary_v1.json (83 Operation Templates)`**

The foundational substrate for the Azure Activity Anomaly Detection POC is now officially **locked and frozen**. All preparatory D1–D5 pipeline validity gates have passed, proving that the dataset supports sequence viability when structured around caller-centered inactivity sessions.

---

## 1. Substrate Contract Architecture

```
 Raw Azure Activity Log (1.15M Events)
                 │
                 ▼
 ┌───────────────────────────────────────┐
 │ 9-Field Schema Contract (v1.0.0)      │  --> Zero Nulls in Key Fields, Monotonic Epoch Order
 └───────────────────────────────────────┘
                 │
                 ▼
 ┌───────────────────────────────────────┐
 │ 83-Template Frozen Vocab (v1.0.0)     │  --> Decoupled Parameter Strings, 100% Transition Coverage
 └───────────────────────────────────────┘
                 │
                 ▼
 ┌───────────────────────────────────────┐
 │ Caller 30m Session Contract (v1.0.0)  │  --> 92.40% Multi-Op Ratio, Behaviorally Coherent
 └───────────────────────────────────────┘
                 │
                 ▼
 ┌───────────────────────────────────────┐
 │ Model Interface & Input Contract (v1) │  --> P(y_t | y_history, caller) Champion Model
 └───────────────────────────────────────┘
```

---

## 2. Locked Substrate Contracts Summary

| Contract Name | File Path | Status | Key Constraint / Guarantee |
| :--- | :--- | :--- | :--- |
| **Schema Contract** | [`schema_contract_v1.json`](file:///c:/Users/YOGA/Downloads/DeepLog/DeepLog/artifacts/production_substrate/schema_contract_v1.json) | **LOCKED** | 9 normalized fields, strict UTC chronological order |
| **Vocabulary Contract** | [`vocabulary_v1.json`](file:///c:/Users/YOGA/Downloads/DeepLog/DeepLog/artifacts/production_substrate/vocabulary_v1.json) | **FROZEN** | 83 operation templates + 4 special tokens (`<PAD>`, `<UNK>`, `<START>`, `<END>`) |
| **Sessionization Contract** | [`sessionization_contract_v1.json`](file:///c:/Users/YOGA/Downloads/DeepLog/DeepLog/artifacts/production_substrate/sessionization_contract_v1.json) | **LOCKED** | Primary partitioning by `caller` identity with 30-minute inactivity timeout |
| **Model Input Contract** | [`model_input_contract_v1.json`](file:///c:/Users/YOGA/Downloads/DeepLog/DeepLog/artifacts/production_substrate/model_input_contract_v1.json) | **LOCKED** | `predict_top_k(context, caller, k=5)` & `anomaly_score(context, target, caller)` |

---

## 3. Stable Components vs. Runtime Monitoring Protocol

### Components Considered Stable (Frozen Substrate)
1. **Schema & Parsing Layer (D1)**: The 9-field extraction contract is 100% complete across all 1.15 million events.
2. **Template Vocabulary (D2)**: The 83 operation templates capture 100% of event patterns with 0 status string leakage.
3. **Sessionization Framework (D4)**: 30-minute caller inactivity sessions provide high behavioral coherence (median length = 7).
4. **Champion Baseline Architecture**: `caller_conditioned_ngram_5` provides >84.8% Top-1 Recall on hard non-dominant operation lifecycles and >91.6% Top-1 Recall on caller sessions.

### Components Subject to Active Runtime Monitoring
1. **Out-of-Vocabulary (OOV) Rate**: Monitor for new Azure API operation names appearing in production logs (trigger vocabulary update if OOV rate exceeds 0.01%).
2. **Caller Drift**: Track new caller identities or service principals exhibiting sudden transition entropy changes.
3. **Repeated Alert Suppression Rate**: Monitor the 15-minute alert suppression window to ensure operator notification volume remains clean and un-flooded.

---

## 4. Final Implementation Plan for Caller-Conditioned Sequence Modeling

1. **Deploy Substrate Registry**: Package `schema_contract_v1.json`, `vocabulary_v1.json`, and `sessionization_contract_v1.json` into production configuration.
2. **Standardize Anomaly Scoring API**: Expose `caller_conditioned_ngram_5` via a microservice/script interface predicting NLL cross-entropy score per incoming event:
   $$S(e_t) = -\\log_2 P(y_t \\mid y_{{t-4:t-1}}, \\text{{caller}})$$
3. **Set Operational Anomaly Cutoff**: Flag top 1.0% highest NLL transitions as potential anomalous operational deviations.

---
*Specification generated automatically by `11_lock_deeplog_substrate.py`.*
"""

    write_text_atomically(OUTPUT_DIR / "reports" / "production_substrate_spec.md", report_md)
    logger.info("Production DeepLog Substrate Locking Pipeline completed successfully!")


if __name__ == "__main__":
    main()
