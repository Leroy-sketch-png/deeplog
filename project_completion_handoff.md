# DeepLog Project Completion Handoff

## Executive Summary
This project aimed to build a robust, explainable anomaly detection engine on top of 1.15 million raw Azure Log Analytics events. Through a rigorous audit, baseline evaluation, and modeling phase, we established a mathematically verified framework that prioritizes actionable SOC intelligence over opaque complexity. This document serves as the canonical handoff for stakeholders and future maintainers.

---

## 1. Data Verification & Chronology
**Data Integrity:** The ingestion pipeline surfaced latent chronology violations inherent to Azure Log Analytics exports (26,153 temporal violations per 100k rows in raw physical storage). 
**Remediation:** We completely decoupled the evaluation engine from physical storage order by materializing a strict, tie-broken chronological memory sort (`timestamp_epoch ASC, rowid ASC`) prior to sequence generation. The dataset is mathematically verified to represent true operational time.

## 2. Canonical Partitioning (The 70/15/15 Split)
**Zero Leakage:** The data was partitioned sequentially (70% Train, 15% Validation, 15% Test) based on exact timestamp span thresholds.
**Stability:** Re-sorting the dataset explicitly confirmed exactly 792,262 training events and 182,210 test events, maintaining zero cross-contamination and zero row drift between splits. This strict chronological separation guarantees the engine only evaluates unseen test events against strict historical priors.

## 3. The Champion Baseline: `caller_conditioned_ngram_5`
**Selection:** After evaluating multiple statistical models (frequency, rarity, Markov variants), the `caller_conditioned_ngram_5` model was locked as the champion.
**Why it Won:** It provides exact sequence matching conditioned specifically to individual callers. It avoids blending metrics into a single opaque number, instead tracking explicit, hard-capped component scores (e.g., structural violation, sequence rarity, timing deviation). It establishes an undeniable baseline floor for anomaly detection.

## 4. Rejection of LSTM Architecture
**Decision:** The LSTM gating mechanism was explicitly rejected.
**Rationale:** The LSTM failed to definitively improve useful operational metrics (alert burden efficiency, contextual reasoning) beyond the established baseline floor. While LSTMs often optimize for Top-1 accuracy in generalized sequences, they destroy deterministic explainability and vastly increase runtime/memory overhead. The decision was evidence-led: complexity without proportional SOC utility is a regression.

## 5. The Explainable Anomaly Packet
**Deliverable:** `analyst_review_packet.md`
**Contents:** The packet isolates the top 20 mathematically scored anomalies across two separate evaluation tracks:
- **Track A (CorrelationId Lifecycle):** Detects structural workflow violations and extreme backend latency during single backend operations.
- **Track B (Caller Session Drift):** Detects identity-centric behavioral drift, net-new operations, and activity spikes over 30-minute windows.
- **Tie-Breaks:** Because component scores are strictly capped (max 5.0), ties are deterministically resolved via a **Timestamp Recency** rule.

## 6. SOC Integration & Usage
**Triage:** Each anomaly in the packet is paired with a dynamic context clause (e.g., highlighting exactly which operation broke the sequence) and a single, human-readable action sentence directing the analyst on what to verify first.
**Feedback Loop:** The packet outlines an intake process for False Positives. If an alert is mathematically anomalous but operationally benign, analysts flag it in the triage system. This acts as ground-truth data for future suppression logic, keeping the SOC alert budget protected.

## 7. Criteria for Reopening Research
This phase is closed. Future model research should **only** be reopened if:
1. A genuinely new data representation (e.g., graph structures) or a fundamentally new modeling unit is proposed.
2. The proposed model can provably exceed the `caller_conditioned_ngram_5` baseline floor on *actionable SOC metrics* (alert burden, false positive rate, explanation quality), rather than purely optimizing Top-1 sequence prediction accuracy.
