import sqlite3
from pathlib import Path
db_path = Path('artifacts/_archive_phase1/sequence_viability/sequence_viability.sqlite')
print("Creating index on timestamp_epoch...")
conn = sqlite3.connect(str(db_path))
conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON events(timestamp_epoch);")
conn.commit()
print("Index created.")
conn.close()
