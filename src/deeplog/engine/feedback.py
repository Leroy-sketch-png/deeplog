import sqlite3
import datetime
from pathlib import Path

_DEFAULT_DB = Path(__file__).resolve().parent.parent.parent.parent / "data" / "feedback.sqlite"


def _get_db(db_path: Path = None) -> Path:
    return db_path if db_path else _DEFAULT_DB


def init_db(db_path: Path = None) -> None:
    path = _get_db(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp         TEXT    NOT NULL,
            alert_id          TEXT    NOT NULL,
            track             TEXT    NOT NULL,
            decision          TEXT    NOT NULL,
            reason            TEXT    NOT NULL,
            analyst_id        TEXT    NOT NULL,
            reviewer_count    INTEGER DEFAULT 1,
            reviewer_ids      TEXT    NOT NULL,
            confidence        TEXT,
            fn_source         TEXT,
            reviewed_at       TEXT    NOT NULL,
            disagreement_flag INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def submit_feedback(
    alert_id: str,
    track: str,
    decision: str,
    reason: str,
    analyst_id: str = "SOC_ANALYST",
    db_path: Path = None,
    confidence: str = None,
    fn_source: str = None,
) -> None:
    """
    Log a SOC analyst verdict into the feedback database.

    Parameters
    ----------
    alert_id    : CorrelationId (Track A) or Caller identifier (Track B).
    track       : "A" or "B".
    decision    : One of BENIGN_FALSE_POSITIVE | CONFIRMED_ANOMALY | UNREVIEWED.
    reason      : One-sentence justification.
    analyst_id  : Optional analyst identifier string.
    db_path     : Override for the feedback SQLite path (default: data/feedback.sqlite).
    confidence  : CERTAIN | PROBABLE | UNCERTAIN
    fn_source   : External source identifier if this is an externally-discovered false negative.
    """
    valid_decisions = {"BENIGN_FALSE_POSITIVE", "CONFIRMED_ANOMALY", "UNREVIEWED"}
    if decision not in valid_decisions:
        raise ValueError(f"Invalid decision '{decision}'. Must be one of {valid_decisions}")

    valid_tracks = {"A", "B"}
    if track not in valid_tracks:
        raise ValueError(f"Invalid track '{track}'. Must be 'A' or 'B'")

    if confidence and confidence not in {"CERTAIN", "PROBABLE", "UNCERTAIN"}:
        raise ValueError(f"Invalid confidence '{confidence}'. Must be CERTAIN, PROBABLE, or UNCERTAIN")

    path = _get_db(db_path)
    init_db(path)

    conn = sqlite3.connect(str(path))
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO feedback (timestamp, alert_id, track, decision, reason, analyst_id, reviewer_count, reviewer_ids, confidence, fn_source, reviewed_at, disagreement_flag) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ts, alert_id, track, decision, reason, analyst_id, 1, analyst_id, confidence, fn_source, ts, 0),
    )
    conn.commit()
    conn.close()

    print(f"Feedback logged — Alert: '{alert_id}' [Track {track}]: {decision} (Confidence: {confidence})")
