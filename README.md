# DeepLog: Behavioral Analytics & Anomaly Engine

## Overview
This repository contains a production-ready Behavioral Analytics Engine for Azure Log Analytics data. It is engineered to prioritize **actionable SOC intelligence**, **deterministic explainability**, and **strict chronological partitioning**.

While this project originated as an evaluation of the academic PyTorch DeepLog (LSTM) implementation (Du et al., 2017), rigorous benchmarking demonstrated that complex deep learning approaches destroyed explainability and massively increased compute overhead without proportionally improving actionable SOC metrics. 

As a result, the LSTM architecture was **explicitly rejected**. The canonical engine in this repository relies on a robust `caller_conditioned_ngram_5` baseline model that provides strict, human-readable structural and temporal anomaly alerts across two tracks:
- **Track A:** CorrelationId Lifecycle Violations
- **Track B:** Caller 30-minute Session Drift

---

## Project Structure

This repository strictly adheres to modern Python packaging standards to prevent anti-patterns and script sprawl.

```
DeepLog/
├── src/deeplog/               # Core engine module
│   ├── cli.py                 # Command Line Interface
│   └── engine/
│       └── anomaly_generator.py # The canonical caller_conditioned_ngram_5 model
├── data/raw/                  # Raw ingestion CSVs (ignored in Git)
├── docs/reports/              # Final deliverable artifacts & packets
├── archive_scripts/           # Historical R&D scripts (Phases 1-3) preserved for context
└── setup.py                   # Standard package configuration
```

---

## Documentation & Deliverables
The project has reached Phase 3 closure. Review the following canonical documents in the `docs/reports/` directory:

- **[Project Completion Handoff](docs/reports/project_completion_handoff.md)**: The executive summary of data verification, the 70/15/15 chronological split, and the architectural decisions.
- **[SOC Analyst Review Packet](docs/reports/analyst_review_packet.md)**: The top 20 verified explainable anomalies with dynamic context clauses and triage actions.
- **[Chronology & Hygiene Verification](docs/reports/final_chronology_and_hygiene_check.md)**: Proof of zero partition drift and temporal storage remediation.

---

## Execution (CLI)

The repository provides a clean command-line interface. To run the verified baseline model over the partitioned SQLite database:

```bash
# Install the package locally
pip install -e .

# Run the anomaly generator engine
python -m deeplog generate-anomalies
```

*Note: The script expects the finalized SQLite database located at `artifacts/_archive_phase1/sequence_viability/sequence_viability.sqlite`.*

---

## References & Academic Origins
This repository was forked from the IEEE S&P [DeepCASE](https://vm-thijs.ewi.utwente.nl/static/homepage/papers/deepcase.pdf) project and originally implemented [DeepLog (CCS'17)](https://doi.org/10.1145/3133956.3134015). If citing the underlying parser/hashing utilities, please credit Thijs van Ede and the original authors.
