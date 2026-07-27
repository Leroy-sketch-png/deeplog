import sys
import argparse
from pathlib import Path

from deeplog.engine.anomaly_generator import train_and_score
from deeplog.engine.diagnose_packet import generate_packet
from deeplog.engine.feedback import submit_feedback, init_db


def main():
    parser = argparse.ArgumentParser(
        prog="deeplog",
        description=(
            "DeepLog Analytics Engine — Behavioral anomaly detection for Azure Activity Logs.\n\n"
            "Commands:\n"
            "  analyze         Detect anomalies in a log CSV and write SOC review packets.\n"
            "  submit-feedback Log an analyst verdict against a detected alert.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -------------------------------------------------------------------------
    # analyze
    # -------------------------------------------------------------------------
    ana = subparsers.add_parser(
        "analyze",
        help="Detect anomalies in a log CSV and write SOC review packets.",
    )
    ana.add_argument(
        "--input", "-i",
        required=True,
        metavar="PATH",
        help=(
            "Path to an Azure Activity Log CSV export. "
            "Must contain columns: timestamp_epoch, operation, provider, caller, "
            "caller_ip, subscription, resource_group, resource_type, correlation_id."
        ),
    )
    ana.add_argument(
        "--output-dir", "-o",
        default="./reports",
        metavar="DIR",
        help="Directory to write output artifacts (default: ./reports).",
    )
    ana.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate input schema and exit without scoring.",
    )

    # -------------------------------------------------------------------------
    # submit-feedback
    # -------------------------------------------------------------------------
    fb = subparsers.add_parser(
        "submit-feedback",
        help="Log an analyst verdict against a detected alert.",
    )
    fb.add_argument(
        "--track", "-t",
        required=True,
        choices=["A", "B"],
        help="Anomaly track. A = CorrelationId lifecycle, B = Caller session.",
    )
    fb.add_argument(
        "--id",
        required=True,
        dest="alert_id",
        metavar="ID",
        help="The CorrelationId (Track A) or Caller identifier (Track B).",
    )
    fb.add_argument(
        "--decision", "-d",
        required=True,
        choices=["BENIGN_FALSE_POSITIVE", "CONFIRMED_ANOMALY", "UNREVIEWED"],
        help="Ground-truth analyst verdict.",
    )
    fb.add_argument(
        "--reason", "-r",
        required=True,
        metavar="TEXT",
        help="One-sentence reason for the verdict.",
    )
    fb.add_argument(
        "--analyst",
        default="SOC_ANALYST",
        metavar="ID",
        help="Analyst identifier (default: SOC_ANALYST).",
    )
    fb.add_argument(
        "--db",
        default=None,
        metavar="PATH",
        help="Path to the feedback SQLite database (default: ./data/feedback.sqlite).",
    )
    fb.add_argument(
        "--confidence",
        default=None,
        choices=["CERTAIN", "PROBABLE", "UNCERTAIN"],
        help="Analyst confidence in the verdict.",
    )
    fb.add_argument(
        "--fn-source",
        default=None,
        metavar="SOURCE",
        help="External source identifier if this is an externally-discovered false negative.",
    )

    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Dispatch
    # -------------------------------------------------------------------------
    if args.command == "analyze":
        input_path  = Path(args.input).resolve()
        output_dir  = Path(args.output_dir).resolve()

        train_and_score(input_path, output_dir, dry_run=args.dry_run)

        if not args.dry_run:
            packet_path = output_dir / "diagnosed_review_packet.md"
            generate_packet(
                track_a_csv=output_dir / "top_lifecycle_anomalies.csv",
                track_b_csv=output_dir / "top_actor_anomalies.csv",
                output_path=packet_path,
            )
            print(f"\nSOC review packet written to: {packet_path}")

    elif args.command == "submit-feedback":
        db_path = Path(args.db).resolve() if args.db else None
        submit_feedback(
            alert_id=args.alert_id,
            track=args.track,
            decision=args.decision,
            reason=args.reason,
            analyst_id=args.analyst,
            db_path=db_path,
            confidence=args.confidence,
            fn_source=args.fn_source,
        )

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
