import sys
import argparse
from deeplog.engine.anomaly_generator import train_and_score

def main():
    parser = argparse.ArgumentParser(description="DeepLog Core CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    gen_parser = subparsers.add_parser("generate-anomalies", help="Generate explainable anomalies from the locked baseline")
    
    fb_parser = subparsers.add_parser("submit-feedback", help="Submit SOC analyst feedback for a specific anomaly")
    fb_parser.add_argument("--track", required=True, choices=["A", "B"], help="Anomaly track (A for Lifecycle, B for Session)")
    fb_parser.add_argument("--id", required=True, help="The CorrelationId (Track A) or Caller/Session timestamp (Track B)")
    fb_parser.add_argument("--decision", required=True, choices=["BENIGN_FALSE_POSITIVE", "CONFIRMED_ANOMALY", "UNREVIEWED"], help="The ground-truth analyst decision")
    fb_parser.add_argument("--reason", required=True, help="1-sentence reason for the decision")
    fb_parser.add_argument("--analyst", default="SOC_ANALYST", help="Analyst identifier")
    
    args = parser.parse_args()
    
    if args.command == "generate-anomalies":
        print("Starting anomaly generation engine...")
        train_and_score()
    elif args.command == "submit-feedback":
        from deeplog.engine.feedback import submit_feedback
        submit_feedback(args.id, args.track, args.decision, args.reason, args.analyst)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
