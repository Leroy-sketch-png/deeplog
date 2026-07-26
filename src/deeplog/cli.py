import sys
import argparse
from deeplog.engine.anomaly_generator import train_and_score

def main():
    parser = argparse.ArgumentParser(description="DeepLog Core CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    gen_parser = subparsers.add_parser("generate-anomalies", help="Generate explainable anomalies from the locked baseline")
    
    args = parser.parse_args()
    
    if args.command == "generate-anomalies":
        print("Starting anomaly generation engine...")
        train_and_score()
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
