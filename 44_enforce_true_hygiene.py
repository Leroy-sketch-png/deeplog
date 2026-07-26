#!/usr/bin/env python3
"""
44_enforce_true_hygiene.py

Enforces strict, aggressive repository hygiene:
1. Archives all obsolete Phase 1 artifact directories (from scripts 01-36).
2. Archives all obsolete Phase 1 scripts.
3. Preserves ONLY the canonical Phase 2 deliverable directories.
4. Generates a clean `tree.txt` of the workspace.
"""

import os
import shutil
import subprocess
from pathlib import Path

# -------------------------------------------------------------------------
# Constants & Paths
# -------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
ARCHIVE_ARTIFACTS_DIR = ARTIFACTS_DIR / "_archive_phase1"
ARCHIVE_SCRIPTS_DIR = PROJECT_ROOT / "archive_scripts"

# The strictly approved canonical directories from Phase 2
CANONICAL_ARTIFACTS = {
    "dataset_grounding",
    "reconciliation",
    "split_verification",
    "reproducible_baseline",
    "lstm_readiness",
    "baseline_synthesis",
    "repository_hygiene",
    "_archive_phase1" # keep the archive itself
}

def move_obsolete_artifacts():
    print("Archiving obsolete artifact directories...")
    ARCHIVE_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Iterate over all items in artifacts/
    for item in ARTIFACTS_DIR.iterdir():
        if item.is_dir() and item.name not in CANONICAL_ARTIFACTS:
            dest = ARCHIVE_ARTIFACTS_DIR / item.name
            print(f"  -> Archiving directory: {item.name}")
            shutil.move(str(item), str(dest))
        elif item.is_file():
            # Archive loose files in artifacts too (like loose csv/json)
            dest = ARCHIVE_ARTIFACTS_DIR / item.name
            print(f"  -> Archiving loose file: {item.name}")
            shutil.move(str(item), str(dest))

def move_obsolete_scripts():
    print("\nArchiving obsolete Phase 1 scripts (01 to 36)...")
    ARCHIVE_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    
    for item in PROJECT_ROOT.glob("*.py"):
        name = item.name
        # Match pattern "01_" to "36_"
        if len(name) >= 3 and name[:2].isdigit():
            prefix = int(name[:2])
            if 1 <= prefix <= 36:
                dest = ARCHIVE_SCRIPTS_DIR / name
                print(f"  -> Archiving script: {name}")
                shutil.move(str(item), str(dest))

def generate_tree_txt():
    print("\nRegenerating tree.txt for user context...")
    target_path = PROJECT_ROOT / "tree.txt"
    try:
        # Use cmd tree command to generate the standard Windows tree format
        result = subprocess.run(["cmd.exe", "/c", "tree", "/F", "/A"], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(result.stdout)
        print("  -> Successfully regenerated tree.txt")
    except Exception as e:
        print(f"  -> Failed to generate tree.txt: {e}")

def main():
    print("Initializing True Aggressive Repository Hygiene...\n")
    
    move_obsolete_artifacts()
    move_obsolete_scripts()
    generate_tree_txt()
    
    print("\nTrue Repository Hygiene completed successfully!")

if __name__ == "__main__":
    main()
