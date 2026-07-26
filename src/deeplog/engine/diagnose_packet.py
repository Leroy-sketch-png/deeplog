import csv
from pathlib import Path
from deeplog.engine.diagnostics import diagnose_track_a, diagnose_track_b

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "explainable_anomalies"

def generate_diagnosed_packet():
    with open(ARTIFACT_DIR / "top_lifecycle_anomalies.csv", "r", encoding="utf-8") as f:
        # Sort explicitly by score descending, then timestamp_range descending (recency)
        track_a_rows = list(csv.DictReader(f))
        track_a_rows.sort(key=lambda x: (float(x["total_score"]), x["timestamp_range"]), reverse=True)
        track_a_top_20 = track_a_rows[:20]
        
    with open(ARTIFACT_DIR / "top_actor_anomalies.csv", "r", encoding="utf-8") as f:
        track_b_rows = list(csv.DictReader(f))[:20]

    md = []
    md.append("# Diagnosed Analyst Review Packet")
    md.append("\nThis packet contains the top 20 most critical anomalies augmented by the **Diagnosis Layer**, which maps raw component scores into deterministic operational causal categories.")
    
    md.append("\n## Track A: CorrelationId Lifecycle Violations")
    md.append("These alerts indicate structural workflow violations or extreme timing deviations within a single backend operation lifecycle.")
    
    for i, row in enumerate(track_a_top_20, 1):
        category, cause = diagnose_track_a(row)
        md.append(f"\n### {i}. CorrelationId: `{row['correlation_id']}`")
        md.append(f"**Timestamp Window:** {row['timestamp_range']}")
        md.append(f"**Diagnosis Category:** **[{category}]**")
        md.append(f"**Causal Explanation:** {cause}")
        md.append(f"- **Scores:** Total: {row['total_score']} | Struct: {row['structural_violation']} | Rarity: {row['sequence_rarity']} | Dur: {row['duration_deviation']} | Len: {row['length_deviation']} | Ctx: {row['context_inconsistency']}")
        
    md.append("\n## Track B: Caller 30m Session Drift")
    md.append("These alerts indicate identity-centric behavioral drift, focusing on net-new access patterns or extreme volume spikes over a 30-minute window.")
    for i, row in enumerate(track_b_rows, 1):
        category, cause = diagnose_track_b(row)
        md.append(f"\n### {i}. Caller: `{row['caller']}`")
        md.append(f"**Session Window:** {row['timestamp_range']}")
        md.append(f"**Diagnosis Category:** **[{category}]**")
        md.append(f"**Causal Explanation:** {cause}")
        md.append(f"- **Scores:** Total: {row['total_score']} | New Ops: {row['new_op']} | IPs: {row['new_ip']} | RGs: {row['new_rg']} | ActSpike: {row['activity_dev']} | HrDev: {row['hour_dev']}")
        
    with open(PROJECT_ROOT / "docs" / "reports" / "diagnosed_review_packet.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))
        
    print("Successfully generated diagnosed_review_packet.md")

if __name__ == "__main__":
    generate_diagnosed_packet()
