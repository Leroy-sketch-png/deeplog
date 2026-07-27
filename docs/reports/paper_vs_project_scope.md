# Paper Scope vs. Project Scope

The original DeepLog and subsequent adaptive unlearning academic papers provide crucial theoretical foundations. However, transitioning from academic theory to a production-ready SOC tool requires defining strict operational boundaries.

## What the Academic Papers Prove
*   **The Theory of Sequence Normalcy:** Academic papers successfully prove that defining normalcy via sequential workflow prediction (e.g., using an LSTM to predict the next log key) is mathematically viable and capable of surfacing statistical anomalies.
*   **The Theory of Matrix Parameter Drift:** They prove that numerical performance matrices can represent multi-dimensional parameter variance.
*   **The Theory of Unlearning:** They prove that a deep learning model can be continuously updated (unlearned/retrained) online to absorb changing environments and user feedback.

## What Our Implementation Proves
*   **We Have Proven Explainability and Feedback Decoupling:** We proved that raw anomaly scores are operationally useless without deterministic translation. Our primary contribution is the operational scaffolding: parsing sequences into dual tracks (Track A / Track B) and explicitly mapping statistical deviations into deterministic, human-readable causal buckets (the Diagnosis Layer). Furthermore, we proved that analyst disagreement can be effectively captured via an isolated feedback lifecycle (`data/feedback.sqlite`) without dangerously hot-patching the underlying detector.
*   **Empirical Simplicity Competes with Deep Learning:** We empirically proved that for this specific dataset's repaired sequences, a deterministic 5-gram baseline achieves identical next-log-key accuracy (Top-1: ~79.8%) to a DeepLog LSTM, rendering the massive training overhead and opacity of deep learning unnecessary for sequence prediction.

## What Remains Unproven
*   **We Have Not Proven Live Security Efficacy:** Both the papers and our implementation prove that the system can find *operational* anomalies. Neither has yet proven that these statistical anomalies correlate strongly with true, malicious *security* incidents in a live production environment.
*   **We Have Not Proven Automated Unlearning is Safe or Necessary:** Because our baseline detector remains locked, we have not proven that automated, online unlearning is necessary or safe. Any future attempt to implement live model unlearning remains unproven and must only be justified by statistical analysis of the accumulated ground-truth analyst feedback.
