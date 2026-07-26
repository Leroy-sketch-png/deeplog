import sqlite3
from pathlib import Path
import json

db_path = Path("artifacts/_archive_phase1/sequence_viability/sequence_viability.sqlite")
conn = sqlite3.connect(str(db_path))

cursor = conn.execute("SELECT rowid, timestamp_epoch, operation FROM events WHERE timestamp_epoch IS NOT NULL LIMIT 100000")
prev_ts = -1
out_of_order = []

for row in cursor:
    rowid, ts, op = row
    if prev_ts != -1 and ts < prev_ts:
        out_of_order.append({"rowid": rowid, "timestamp_epoch": ts, "prev_timestamp_epoch": prev_ts, "operation": op})
    prev_ts = ts

print(f"Total out of order rows in first 100k: {len(out_of_order)}")

if out_of_order:
    print("Sample of 20 out-of-order rows:")
    for x in out_of_order[:20]:
        print(x)
        
with open("out_of_order_sample.json", "w") as f:
    json.dump(out_of_order[:20], f, indent=2)

conn.close()
