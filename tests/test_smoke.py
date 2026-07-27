"""
Smoke test: generates a minimal synthetic Azure Activity Log CSV
and runs the full analyze pipeline end-to-end to verify nothing crashes.
"""

import csv
import time
import tempfile
from pathlib import Path
import sys

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from deeplog.engine.anomaly_generator import load_events, train_and_score

# ---------------------------------------------------------------------------
# Minimal synthetic log — 300 events across 3 callers, 2 corr IDs each
# ---------------------------------------------------------------------------
OPERATIONS = [
    "MICROSOFT.COMPUTE/VIRTUALMACHINES/WRITE",
    "MICROSOFT.COMPUTE/VIRTUALMACHINES/DELETE",
    "MICROSOFT.RESOURCES/TAGS/WRITE",
    "MICROSOFT.SQL/SERVERS/DATABASES/WRITE",
    "MICROSOFT.NETWORK/NETWORKSECURITYGROUPS/WRITE",
]

def _generate_csv(path: Path, n: int = 300) -> None:
    base = time.time() - 3600 * 24 * 10   # 10 days ago
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "timestamp_epoch", "operation", "provider", "caller",
            "caller_ip", "subscription", "resource_group", "resource_type", "correlation_id"
        ])
        for i in range(n):
            caller  = f"user-{i % 3}@example.com"
            corr    = f"corr-{i % 6}"
            op      = OPERATIONS[i % len(OPERATIONS)]
            t       = base + i * 120   # 2-minute intervals
            w.writerow([
                t, op, "MICROSOFT.COMPUTE", caller,
                "1.2.3.4", "sub-001", "rg-prod", "VIRTUALMACHINES", corr,
            ])


def test_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "test_logs.csv"
        out_dir  = Path(tmp) / "out"
        _generate_csv(csv_path)

        # Should validate and return without crashing
        train_and_score(csv_path, out_dir, dry_run=True)
        assert not (out_dir / "top_lifecycle_anomalies.csv").exists(), \
            "dry-run should not produce output files"
    print("PASS: test_dry_run")


def test_full_pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "test_logs.csv"
        out_dir  = Path(tmp) / "out"
        _generate_csv(csv_path)

        train_and_score(csv_path, out_dir)

        assert (out_dir / "top_lifecycle_anomalies.csv").exists(), \
            "Track A CSV not produced"
        assert (out_dir / "top_actor_anomalies.csv").exists(), \
            "Track B CSV not produced"
        assert (out_dir / "manifest.json").exists(), \
            "manifest.json not produced"
    print("PASS: test_full_pipeline")


def test_missing_column_raises():
    with tempfile.TemporaryDirectory() as tmp:
        bad_csv = Path(tmp) / "bad.csv"
        with bad_csv.open("w") as f:
            f.write("timestamp_epoch,caller\n")
            f.write("1000,user@example.com\n")
        out_dir = Path(tmp) / "out"
        try:
            train_and_score(bad_csv, out_dir)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "schema not recognized" in str(e).lower() or "missing required columns" in str(e).lower()
    print("PASS: test_missing_column_raises")


if __name__ == "__main__":
    test_dry_run()
    test_full_pipeline()
    test_missing_column_raises()
    print("\nAll smoke tests passed.")
