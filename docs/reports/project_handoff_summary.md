# DeepLog Project Handoff Summary

## Executive Summary
This project successfully transitioned from an experimental LSTM-based anomaly detection approach to a deterministic, heuristic-based baseline model. The system evaluates backend telemetry across two distinct axes (Track A: CorrelationId Lifecycle, Track B: Caller Session Drift) and augments raw scores with a Diagnosis Layer for direct Security Operations Center (SOC) triage.

## Definitive Findings
*   **The Baseline Wins:** A heuristically driven baseline tracking n-gram sequences, duration, and contextual boundaries vastly outperforms opaque deep learning models for these logs. It provides exact component-level explainability without accuracy loss.
*   **The LSTM is Unnecessary:** The LSTM was rejected because it failed to provide deterministic causal explanations, suffered from extreme training overhead, and added no measurable security value over simple empirical baselines.

## Unproven Assumptions
*   **True Security Value:** The system definitively identifies operational anomalies, but it does not yet prove these anomalies are malicious security incidents. True Positive rates remain unproven until SOC triage occurs.
*   **Need for Automated Unlearning:** There is no evidence yet that the system requires complex automated "unlearning." 

## Track A: The Necessity of Two Review Queues
Track A (CorrelationId Lifecycle Violations) requires two distinct analyst review queues because of **score saturation**:
*   The primary components (structural violation, sequence rarity, duration, and length) rapidly saturate to a maximum score of `1.0` for the absolute most extreme <1% of records.
*   Because the total score ranks these saturated records at the top (e.g., a perfect 4.0), they inadvertently bury **Context Inconsistency** anomalies (e.g., lateral movement across subscriptions or resource groups). 
*   By splitting Track A into a **Top 20 Total Score** queue and a **Top 20 Context Score** queue, analysts can review severe structural breaks without missing critical contextual boundary crossings.

## Track B: Usable As-Is
Track B (Caller Session Drift) is immediately usable for SOC triage without modification. The 30-minute caller sessions yield well-distributed, non-saturating component scores (e.g., `activity_dev`, `new_ip`, `hour_dev`). The accompanying Diagnosis Layer accurately and reliably maps these scores into discrete operational buckets (such as VPN/Routing Shifts or Off-Hours Deviations).

## The Feedback Lifecycle and Next Steps
The project now includes a localized feedback ingestion mechanism (`data/feedback.sqlite` via the `submit-feedback` CLI). The immediate next step is for human analysts to review the `diagnosed_review_packet.md` and log ground-truth verdicts (`CONFIRMED_ANOMALY` or `BENIGN_FALSE_POSITIVE`).
**This feedback accumulation is the mandatory prerequisite for any future automation.**

## Conditions for Reopening Model Research
Model research (including LSTMs or online unlearning) should only be reopened if the feedback lifecycle proves that:
1.  The deterministic heuristics produce an unmanageable false-positive rate that simple threshold tuning cannot fix.
2.  Analysts discover true-positive security events that the current feature engineering fundamentally failed to capture, but which a deep learning architecture could theoretically detect.
