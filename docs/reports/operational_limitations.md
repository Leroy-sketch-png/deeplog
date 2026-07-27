# Operational Limitations

As the system transitions from research to SOC integration, maintainers must be aware of the following structural and operational limitations:

## 1. Zero-Day Cold Start Bias
The baseline heuristic profiles operations based entirely on an initial historical training window. **If malicious activity or severe misconfigurations exist in the training window, the engine will model them as "normal."** The system assumes a clean baseline and has no inherent mechanism to identify pre-existing persistent threats.

## 2. Hardcoded Diagnosis Taxonomy
The Diagnosis Layer currently utilizes a deterministic, hardcoded taxonomy mapping component scores to specific operational buckets (e.g., "VPN / Routing Shift", "Critical Deployment/Migration Shift"). 
*   **Limitation:** It cannot dynamically discover new causal categories. If a novel attack vector emerges that falls outside the hardcoded if/else heuristic tree, it will be mapped into a generic bucket like "Unclassified Behavioral Drift."

## 3. Heuristic Threshold Saturation
In Track A (CorrelationId Lifecycle), component scores (e.g., `duration_deviation`, `length_deviation`) saturate heavily at a cap of `1.0` for the most extreme anomalies. 
*   **Limitation:** This prevents the engine from sorting extreme anomalies with high fidelity. A sequence that is 10x slower than average receives the same penalty as a sequence that is 100x slower. This saturation required the creation of a dedicated "Context Inconsistency" queue to ensure lateral movement wasn't buried by severe timing deviations.

## 4. No Live "Unlearning" or Adaptive Recalibration
The current deployment has no automation linking the analyst feedback lifecycle (`data/feedback.sqlite`) back into the model weights or heuristic thresholds. 
*   **Limitation:** If a noisy benign workflow repeatedly triggers an anomaly, human analysts must manually log the False Positive, but the engine will continue to flag it on the next run. Automated tuning has been explicitly blocked pending statistical accumulation of actual analyst feedback.

## 5. Security Validity vs. Operational Validity
The DeepLog engine is exceptionally proficient at detecting *operational* anomalies (e.g., failed deployments, broken scripts, misconfigured load balancers).
*   **Limitation:** It is not yet proven to be a high-fidelity *security* anomaly detector. A high score means the workflow changed drastically, not necessarily that the workflow is malicious. Analysts must treat the output as an operational drift indicator first, and a security indicator second.
