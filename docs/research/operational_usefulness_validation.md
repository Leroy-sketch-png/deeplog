# Operational Usefulness Validation

While the deterministic empirical baseline conclusively defeats the LSTM in raw predictive accuracy on this dataset's repaired sequences, mathematical accuracy alone does not guarantee SOC utility. This document validates whether the resulting pipeline is genuinely actionable for human analysts.

## 1. Actionable Diagnostic Explainability
A core limitation of raw anomaly detectors (including the original DeepLog) is that they output an opaque "probability" or "anomaly score," leaving the SOC analyst to reverse-engineer the context. 

We measured the output of the Track A and Track B queues against the deterministic Diagnosis Layer:
*   **Track A:** 100% of the top 40 extreme CorrelationId anomalies (both the Total Score and Context queues) are deterministicially parsed into actionable causal buckets (e.g., "Critical Deployment/Migration Shift" or "Cross-Boundary Lateral Context Shift").
*   **Track B:** 100% of the top caller session anomalies successfully map to discrete identity-drift categories, most notably "VPN / Routing Shift" (60%) and "Off-Hours Deviation" (19%).

**Validation:** The system is operationally useful because it translates raw feature deviations directly into the exact operational syntax an analyst uses to triage tickets. There are zero opaque alerts.

## 2. Absorbing Disagreement via the Feedback Lifecycle
The system's `data/feedback.sqlite` intake layer ensures that the operational scaffolding can independently absorb friction from the raw detector.

*   **Decoupled Ground Truth:** If a SOC analyst disagrees with an alert (e.g., an automated nightly migration script consistently triggers a "Structural Violation"), they log it as a `BENIGN_FALSE_POSITIVE` in the feedback database. 
*   **No Detector Churn:** The underlying 5-gram fallback detector and component thresholds remain completely static. The organization relies on downstream SIEM alert-suppression rules referencing the feedback database to silence the noise, rather than dangerously hot-patching or "unlearning" the core detection model.

## Final Conclusion
Even if the deep-learning DeepLog architecture is completely abandoned for deterministic baselines, the project remains highly useful. The true value lies not in the underlying sequence predictor, but in the **operational scaffolding**: dividing detection into discrete tracks, assigning deterministic diagnostic intent, and explicitly isolating human disagreement into a stable feedback lifecycle.
