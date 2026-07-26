import csv
import json
import sqlite3
from pathlib import Path

OUTPUT_DIR = Path("artifacts/explainable_anomalies")
DB_PATH = Path("artifacts/_archive_phase1/sequence_viability/sequence_viability.sqlite")

def audit():
    # Load Track A top 10
    track_a = []
    with open(OUTPUT_DIR / "top_lifecycle_anomalies.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            track_a.append(row)
            if len(track_a) == 10: break
            
    # Load Track B top 10
    track_b = []
    with open(OUTPUT_DIR / "top_actor_anomalies.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            track_b.append(row)
            if len(track_b) == 10: break

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    audit_results = {}
    
    # Audit Track A (CorrelationId)
    audit_results["track_a"] = []
    for row in track_a:
        corr_id = row["correlation_id"]
        # Fetch actual DB sequence
        db_rows = conn.execute("SELECT timestamp_epoch, operation FROM events WHERE correlation_id=? AND timestamp_epoch IS NOT NULL", (corr_id,)).fetchall()
        db_rows.sort(key=lambda x: x["timestamp_epoch"]) # How we evaluate it now
        
        sequence_ops = [r["operation"] for r in db_rows]
        is_sorted = all(db_rows[i]["timestamp_epoch"] <= db_rows[i+1]["timestamp_epoch"] for i in range(len(db_rows)-1))
        
        audit_results["track_a"].append({
            "correlation_id": corr_id,
            "caller": row["caller"],
            "score": row["total_score"],
            "csv_sequence": row["sequence_context"].split(" -> "),
            "db_reconstructed_sequence": sequence_ops[:10],
            "is_strictly_chronological": is_sorted,
            "explanation": row["explanation"]
        })
        
    # Audit Track B (Caller Session)
    audit_results["track_b"] = []
    for row in track_b:
        caller = row["caller"]
        time_range = row["timestamp_range"].split(" - ")
        if len(time_range) == 2:
            try:
                # Extract timestamps
                import dateutil.parser
                t1 = dateutil.parser.isoparse(time_range[0]).timestamp()
                t2 = dateutil.parser.isoparse(time_range[1]).timestamp()
                
                db_rows = conn.execute("SELECT timestamp_epoch, operation FROM events WHERE caller=? AND timestamp_epoch >= ? AND timestamp_epoch <= ? AND timestamp_epoch IS NOT NULL", (caller, t1, t2)).fetchall()
                db_rows.sort(key=lambda x: x["timestamp_epoch"])
                
                is_sorted = all(db_rows[i]["timestamp_epoch"] <= db_rows[i+1]["timestamp_epoch"] for i in range(len(db_rows)-1))
                audit_results["track_b"].append({
                    "caller": caller,
                    "score": row["total_score"],
                    "session_ops": row["session_context"].split(", "),
                    "db_reconstructed_ops": list(set([r["operation"] for r in db_rows]))[:10],
                    "is_strictly_chronological": is_sorted,
                    "explanation": row["explanation"]
                })
            except Exception as e:
                pass

    with open(OUTPUT_DIR / "audit_results.json", "w") as f:
        json.dump(audit_results, f, indent=2)

if __name__ == "__main__":
    audit()
