import sqlite3

conn = sqlite3.connect('artifacts/_archive_phase1/sequence_viability/sequence_viability.sqlite')
print(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
conn.close()
