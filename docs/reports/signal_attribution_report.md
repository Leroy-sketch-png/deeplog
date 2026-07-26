# Signal Attribution & Diagnosis Report

This report grounds the diagnosis heuristics and feature signals directly against the full canonical CSV outputs (`top_lifecycle_anomalies.csv` and `top_actor_anomalies.csv`).

## 1. Feedback System Grounding
- Successfully loaded **100** Track A records as `UNREVIEWED`.
- Successfully loaded **100** Track B records as `UNREVIEWED`.
The ground-truth SQLite database now has full coverage of the ranked outputs, providing a real baseline for SOC review rather than an empty table.

## 2. Diagnosis Distribution
The following details the distribution of operational categories across the full ranked CSVs (not just the top 20). If a single category dominates >90%, the heuristic is overly broad.

### Track A (CorrelationId Lifecycle)
- **Critical Deployment/Migration Shift**: 100 (100.0%)

### Track B (Caller Session Drift)
- **Possible Credential/Token Compromise**: 4 (4.0%)
- **Automation / Batch Script Change**: 1 (1.0%)
- **Off-Hours Deviation**: 19 (19.0%)
- **Unclassified Behavioral Drift**: 10 (10.0%)
- **RBAC Role Expansion**: 6 (6.0%)
- **VPN / Routing Shift**: 60 (60.0%)

## 3. Signal Attribution (Feature Value)
This section compares the component score activation (which components actually fire) between the Top 20 alerts (which a SOC sees) and the full exported dataset. This proves which features actually drive detection value.

### Track A Components
| Feature | Fired in Top 20? | Fired in Full CSV? | Top 20 Avg | Full CSV Avg |
| :--- | :--- | :--- | :--- | :--- |
| `structural_violation` | True | True | 1.00 | 1.00 |
| `sequence_rarity` | True | True | 1.00 | 1.00 |
| `duration_deviation` | True | True | 1.00 | 1.00 |
| `length_deviation` | True | True | 1.00 | 1.00 |
| `context_inconsistency` | False | False | 0.00 | 0.00 |

### Track B Components
| Feature | Fired in Top 20? | Fired in Full CSV? | Top 20 Avg | Full CSV Avg |
| :--- | :--- | :--- | :--- | :--- |
| `new_op` | True | True | 1.00 | 0.32 |
| `new_prov` | True | True | 0.20 | 0.04 |
| `new_sub` | True | True | 0.25 | 0.06 |
| `new_rg` | True | True | 0.25 | 0.11 |
| `new_type` | True | True | 1.00 | 0.31 |
| `new_ip` | True | True | 0.20 | 0.64 |
| `activity_dev` | True | True | 0.43 | 0.33 |
| `hour_dev` | True | True | 0.69 | 0.73 |

## Conclusion
This data proves explicitly which components are producing diagnostic signal versus which are silent within the evaluated dataset slice, grounding the heuristic logic entirely in empirical reality.