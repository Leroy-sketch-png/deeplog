import sqlite3
import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FEEDBACK_DB_PATH = PROJECT_ROOT / "data" / "feedback.sqlite"

def init_db():
    FEEDBACK_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(FEEDBACK_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            alert_id TEXT NOT NULL,
            track TEXT NOT NULL,
            decision TEXT NOT NULL,
            reason TEXT NOT NULL,
            analyst_id TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def submit_feedback(alert_id: str, track: str, decision: str, reason: str, analyst_id: str = "SOC_ANALYST"):
    init_db()
    
    valid_decisions = {"BENIGN_FALSE_POSITIVE", "CONFIRMED_ANOMALY", "UNREVIEWED"}
    if decision not in valid_decisions:
        raise ValueError(f"Invalid decision '{decision}'. Must be one of {valid_decisions}")
        
    valid_tracks = {"A", "B"}
    if track not in valid_tracks:
        raise ValueError(f"Invalid track '{track}'. Must be 'A' or 'B'")
        
    conn = sqlite3.connect(str(FEEDBACK_DB_PATH))
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO feedback (timestamp, alert_id, track, decision, reason, analyst_id) VALUES (?, ?, ?, ?, ?, ?)",
        (ts, alert_id, track, decision, reason, analyst_id)
    )
    conn.commit()
    conn.close()
    
    print(f"Feedback successfully logged for alert '{alert_id}' [Track {track}]: {decision}")
