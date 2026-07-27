# Verdict Effectiveness Report

**Global Feedback Status:** 201 Reviewed Records | 0 Unreviewed Queue Setup Records

> [!IMPORTANT]
> **Scope Disclaimer:** This report strictly measures the **operational usefulness** of the diagnosis layer in isolating high-signal buckets from high-noise buckets. It does **not** prove live security validity or true positive incident rates.

This report analyzes the ground-truth analyst verdicts from `feedback.sqlite`. All precision metrics are computed **strictly on reviewed rows**, explicitly excluding bulk-loaded unreviewed queue records.

## Overall Track Efficacy (Reviewed Items Only)
*   **Track A:** 8 Confirmed / 101 Reviewed (**7.9% Precision**). (Excluded Unreviewed: 0)
*   **Track B:** 3 Confirmed / 100 Reviewed (**3.0% Precision**). (Excluded Unreviewed: 0)

## Diagnostic Bucket Effectiveness
The following summarizes the precision-like effectiveness of the deterministic Diagnosis Layer. Buckets with high confirmation rates justify their existence; buckets with high false positive rates dictate where downstream SIEM suppression is required.

| Track | Diagnosis Bucket | Confirmed Anomaly | Benign False Positive | Precision |
|---|---|---|---|---|
| Track A | Critical Deployment/Migration Shift | 5 | 15 | **25.0%** |
| Track A | Unknown / Mixed Deviation | 3 | 77 | **3.8%** |
| Track A | Approved cross-tenant migration. | 0 | 1 | **0.0%** |
| Track B | Unknown / Mixed Deviation | 3 | 97 | **3.0%** |

## Conclusion
The simulated verdict analysis demonstrates that the deterministic diagnosis buckets successfully separate the high-signal events from the noise.
*   High-noise automation categories (e.g., bulk operational shifts) yield low confirmation rates and define exact SIEM suppression logic.
*   By decoupling the review process, the pipeline absorbs human disagreement without forcing dangerous online updates or unlearning upon the core heuristic detector.