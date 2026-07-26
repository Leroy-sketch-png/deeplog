# Diagnosis Layer Specification

This document details the deterministic heuristic tree that maps raw mathematical anomaly scores into operational, causal categories. It provides the "missing third pillar" of DeepLog by strictly bounding explanations to calculated component features, rather than relying on assumed intent or new opaque models.

## Heuristic Mappings

### Track A (CorrelationId Lifecycle)
The diagnosis layer evaluates the `structural_violation`, `duration_deviation`, `length_deviation`, and `context_inconsistency` scores for a given CorrelationId anomaly.

1. **Lateral Boundary Crossing** (`context_inconsistency > 0`): The CorrelationId unexpectedly traversed distinct resource groups or providers during execution.
2. **Critical Deployment/Migration Shift** (`structural_violation == 1.0` AND `duration_deviation > 0.8`): Unseen sequence path combined with massive latency, likely indicating a failed backend deployment.
3. **New Microservice Routine** (`structural_violation == 1.0` AND `duration_deviation <= 0.8`): Strictly unseen workflow path, likely an unmodeled script or manual intervention.
4. **Latency / Retry Loop** (`structural_violation == 0.0` AND `duration_deviation > 0.8`): Standard workflow path, but extreme timing delay indicative of a backend retry loop or stalled process.
5. **Stalled Operation** (`length_deviation > 0.8`): Abnormal volume of events within the same CorrelationId cycle without a severe structural violation.

### Track B (Caller Session Drift)
The diagnosis layer evaluates `new_ip`, `new_op`, `new_rg`, `new_prov`, `activity_dev`, and `hour_dev` over a 30-minute caller window.

1. **Possible Credential/Token Compromise** (`new_ip == 1.0`, `new_op == 1.0`, `activity_dev > 0.5`): Identity used a brand new IP to execute unseen operations at an unusually high volume.
2. **VPN / Routing Shift** (`new_ip == 1.0`, `new_op == 0.0`, `new_prov == 0.0`): Identity executed standard business operations from a previously unseen IP space.
3. **Automation / Batch Script Change** (`new_op == 1.0`, `activity_dev > 0.8`, `new_ip == 0.0`): Massive volume spike of unseen operations from a known IP, indicating a cron job or automation change.
4. **RBAC Role Expansion** (`new_rg == 1.0` OR `new_prov == 1.0` AND `new_ip == 0.0`): Identity began operating in previously unseen resource groups or providers, suggesting a recent permissions grant.
5. **Off-Hours Deviation** (`hour_dev > 0.8`, `new_op == 1.0`): Identity executed unseen operations during a historically inactive hour.

These mappings guarantee deterministic explainability without introducing new inference boundaries.
