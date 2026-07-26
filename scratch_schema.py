import sqlite3
from pathlib import Path

db_path = Path('artifacts/_archive_phase1/sequence_viability/sequence_viability.sqlite')
if not db_path.exists():
    print(f"Database not found at {db_path}")
else:
    conn = sqlite3.connect(str(db_path))
    schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='events';").fetchone()[0]
    print(schema)
    conn.close()
