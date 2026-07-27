import csv
from pathlib import Path
from deeplog.engine.diagnostics import diagnose_track_a, diagnose_track_b


def generate_packet(
    track_a_csv: Path,
    track_b_csv: Path,
    output_path: Path,
) -> None:
    """
    Generate a human-readable diagnosed SOC review packet.

    Parameters
    ----------
    track_a_csv : Path
        Path to the top_lifecycle_anomalies.csv produced by anomaly_generator.
    track_b_csv : Path
        Path to the top_actor_anomalies.csv produced by anomaly_generator.
    output_path : Path
        Destination path for the markdown packet.
    """
    with open(track_a_csv, "r", encoding="utf-8") as f:
        track_a_rows = list(csv.DictReader(f))

    track_a_top_20 = sorted(
        track_a_rows,
        key=lambda x: (float(x["total_score"]), x["timestamp_range"]),
        reverse=True,
    )[:20]

    context_rows = [
        r for r in track_a_rows
        if float(r["context_inconsistency"]) > 0 and r not in track_a_top_20
    ]
    track_a_context_20 = sorted(
        context_rows,
        key=lambda x: (float(x["context_inconsistency"]), float(x["total_score"])),
        reverse=True,
    )[:20]

    with open(track_b_csv, "r", encoding="utf-8") as f:
        track_b_rows = list(csv.DictReader(f))[:20]

    md = []
    md.append("# Diagnosed Analyst Review Packet")
    md.append(
        "\nThis packet maps raw anomaly scores into deterministic operational causal categories "
        "for SOC triage. Two independent review queues are provided for Track A."
    )

    md.append("\n---\n")
    md.append("## Track A — Queue 1: Top 20 by Total Score")
    md.append(
        "Structural workflow violations or extreme timing deviations within a single backend operation lifecycle."
    )
    for i, row in enumerate(track_a_top_20, 1):
        category, cause = diagnose_track_a(row)
        md.append(f"\n### A1-{i}. `{row['correlation_id']}`")
        md.append(f"**Window:** {row['timestamp_range']}")
        md.append(f"**Category:** {category}")
        md.append(f"**Cause:** {cause}")
        md.append(
            f"**Scores:** Total `{row['total_score']}` | "
            f"Struct `{row['structural_violation']}` | Rarity `{row['sequence_rarity']}` | "
            f"Duration `{row['duration_deviation']}` | Length `{row['length_deviation']}` | "
            f"Context `{row['context_inconsistency']}`"
        )

    if track_a_context_20:
        md.append("\n---\n")
        md.append("## Track A — Queue 2: Top 20 by Context Inconsistency")
        md.append(
            "CorrelationIds that traversed distinct resource groups or subscriptions — "
            "a distinct cross-boundary anomaly axis, evaluated independently of sequence structure."
        )
        for i, row in enumerate(track_a_context_20, 1):
            category, cause = diagnose_track_a(row)
            md.append(f"\n### A2-{i}. `{row['correlation_id']}`")
            md.append(f"**Window:** {row['timestamp_range']}")
            md.append(f"**Category:** {category}")
            md.append(f"**Cause:** {cause}")
            md.append(
                f"**Scores:** Total `{row['total_score']}` | "
                f"Struct `{row['structural_violation']}` | Rarity `{row['sequence_rarity']}` | "
                f"Duration `{row['duration_deviation']}` | Length `{row['length_deviation']}` | "
                f"Context `{row['context_inconsistency']}`"
            )

    md.append("\n---\n")
    md.append("## Track B — Caller 30-Minute Session Drift")
    md.append(
        "Identity-centric behavioral drift: net-new access patterns or volume spikes over a 30-minute window."
    )
    for i, row in enumerate(track_b_rows, 1):
        category, cause = diagnose_track_b(row)
        md.append(f"\n### B-{i}. `{row['caller']}`")
        md.append(f"**Window:** {row['timestamp_range']}")
        md.append(f"**Category:** {category}")
        md.append(f"**Cause:** {cause}")
        md.append(
            f"**Scores:** Total `{row['total_score']}` | "
            f"New Ops `{row['new_op']}` | New IP `{row['new_ip']}` | "
            f"New RG `{row['new_rg']}` | Act Spike `{row['activity_dev']}` | "
            f"Hour Dev `{row['hour_dev']}`"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(md), encoding="utf-8")
