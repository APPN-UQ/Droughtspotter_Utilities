#!/usr/bin/env python3
"""
DroughtSpotter analysis pipeline.

Usage:
  python run_pipeline.py <zip_path> [--days N]

Expects experimentFile.csv in the same folder as the zip.
Outputs go into a datetime-stamped subfolder next to the zip, e.g.:
  <zip_folder>/outputs/2026-07-01_143210/
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

from weather_summary import plot_weather
from weight_summary import plot_weights


def main():
    parser = argparse.ArgumentParser(
        description="DroughtSpotter pipeline — weather + weight plots"
    )
    parser.add_argument("zip_path", help="TraitFinder zip export")
    parser.add_argument("--days", type=int, default=5,
                        help="Days of recent data to include in the filtered view (default: 5)")
    args = parser.parse_args()

    zip_path = Path(args.zip_path)
    exp_path = zip_path.parent / "experimentFile.csv"

    if not zip_path.exists():
        print(f"Error: zip file not found: {zip_path}")
        sys.exit(1)
    if not exp_path.exists():
        print(f"Warning: experimentFile.csv not found in {zip_path.parent} — "
              f"continuing without target weight lines.")
        exp_path = None

    t_start  = time.time()
    run_time = datetime.now()
    run_stamp = run_time.strftime("%Y-%m-%d_%H%M%S")
    out_dir  = zip_path.parent / "outputs" / run_stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    recent_dir = out_dir / "most_recent"
    full_dir   = out_dir / "entire_dataset"
    recent_dir.mkdir(parents=True, exist_ok=True)
    full_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("DroughtSpotter Pipeline")
    print(f"  Zip:        {zip_path.name}")
    print(f"  Experiment: {exp_path.name if exp_path else '(none — skipping target weights)'}")
    print(f"  Output:     {out_dir}")
    print(f"  Recent view: last {args.days} days")
    print("=" * 60)

    print(f"\n[1/4] Weather summary — most recent ({args.days} days)")
    plot_weather(zip_path, out_dir=recent_dir, show=False, days=args.days)

    print(f"\n[2/4] Weight summary — most recent ({args.days} days)")
    plot_weights(zip_path, exp_path, out_dir=recent_dir, show=False, days=args.days)

    print("\n[3/4] Weather summary — entire dataset")
    plot_weather(zip_path, out_dir=full_dir, show=False, days=None)

    print("\n[4/4] Weight summary — entire dataset")
    result = plot_weights(zip_path, exp_path, out_dir=full_dir, show=False, days=None)

    elapsed = time.time() - t_start

    meta = {
        "run_at":            run_time.isoformat(timespec="seconds"),
        "zip_file":          str(zip_path.resolve()),
        "experiment_file":   str(exp_path.resolve()) if exp_path else None,
        "recent_days":       args.days,
        "records_processed": int(len(result["data"])),
        "units":             int(result["data"]["unit"].nunique()),
        "duration_s":        round(elapsed, 1),
    }
    meta_file = out_dir / "pipeline_metadata.json"
    meta_file.write_text(json.dumps(meta, indent=2))

    print(f"\nDone in {elapsed:.0f} s")
    print(f"Metadata saved: {meta_file}")


if __name__ == "__main__":
    main()
