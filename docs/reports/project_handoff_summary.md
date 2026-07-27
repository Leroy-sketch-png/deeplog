# DeepLog Project Handoff Summary

## Executive Summary
This project operationalizes the theoretical core of DeepLog into a production-ready anomaly detection pipeline. The detector family itself (empirical baseline vs. DeepLog-style LSTM) is fully interchangeable depending on the dataset benchmark. The **durable contribution** of this project is the operational scaffolding: dual-track detection (Track A: CorrelationId Lifecycle, Track B: Caller Session Drift), a deterministic Diagnosis Layer for direct SOC triage, and a decoupled analyst feedback lifecycle.

## Definitive Findings & Project Status
The project achieves three distinct milestones, each with a different status:

1.  **Operational Usefulness (PROVEN):** The system's durable contribution is its operational scaffolding. Whether powered by an LSTM or a deterministic 5-gram baseline, the raw detector simply outputs statistical anomalies. The project is operationally useful because it deterministicially parses these opaque scores into concrete, actionable causal buckets (e.g., VPN/Routing Shifts) via the Diagnosis Layer.
2.  **Security Validity (UNPROVEN):** The system reliably identifies extreme operational anomalies and workflow deviations. However, it remains entirely unproven whether these statistical deviations correlate with true, malicious security incidents in a live production environment.
3.  **Future Learning-Loop Readiness (PREPARED):** The infrastructure for closed-loop learning is established via the decoupled `data/feedback.sqlite` intake. However, any future implementation of automated model unlearning is currently suspended. It must only be reopened if justified by significant statistical accumulation of analyst-reviewed data.

## Track A: The Necessity of Two Review Queues
Track A (CorrelationId Lifecycle Violations) requires two distinct analyst review queues because of **score saturation**:
*   The primary components (structural violation, sequence rarity, duration, and length) rapidly saturate to a maximum score of `1.0` for the absolute most extreme <1% of records.
*   Because the total score ranks these saturated records at the top (e.g., a perfect 4.0), they inadvertently bury **Context Inconsistency** anomalies (e.g., lateral movement across subscriptions or resource groups). 
*   By splitting Track A into a **Top 20 Total Score** queue and a **Top 20 Context Score** queue, analysts can review severe structural breaks without missing critical contextual boundary crossings.

## Track B: Usable As-Is
Track B (Caller Session Drift) is immediately usable for SOC triage without modification. The 30-minute caller sessions yield well-distributed, non-saturating component scores (e.g., `activity_dev`, `new_ip`, `hour_dev`). The accompanying Diagnosis Layer accurately and reliably maps these scores into discrete operational buckets (such as VPN/Routing Shifts or Off-Hours Deviations).

## The Feedback Lifecycle and Next Steps
The project now includes a localized feedback ingestion mechanism (`data/feedback.sqlite` via the `submit-feedback` CLI). **Feedback is stored strictly separately from the detector.** The immediate next step is for human analysts to review the `diagnosed_review_packet.md` and log ground-truth verdicts (`CONFIRMED_ANOMALY` or `BENIGN_FALSE_POSITIVE`).

## Conditions for Future Unlearning or Model Research
Model research (including dynamically unlearning via LSTMs or online baseline updates) must only be reopened if justified by actual review data from the feedback lifecycle:
1.  The deterministic heuristics or current LSTM implementation produce an unmanageable false-positive rate that simple downstream alert-suppression rules cannot fix.
2.  Analysts discover true-positive security events that the current feature engineering fundamentally failed to capture, but which a deep learning architecture could theoretically detect.
