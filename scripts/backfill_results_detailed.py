from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_PATH = ROOT / "results.tsv"
DEFAULT_RESULTS_DETAILED_PATH = ROOT / "results_detailed.tsv"
DEFAULT_JOBS_DIR = ROOT / "jobs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill results_detailed.tsv from existing Harbor job directories referenced in results.tsv.")
    parser.add_argument("--results-path", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--results-detailed-path", type=Path, default=DEFAULT_RESULTS_DETAILED_PATH)
    parser.add_argument("--jobs-dir", type=Path, default=DEFAULT_JOBS_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.results_detailed_path.exists():
        args.results_detailed_path.unlink()

    with args.results_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    for row in rows:
        desc = row.get("description", "")
        match = re.search(r"\bjob=([^\s|]+)", desc)
        if not match:
            continue
        job_dir = args.jobs_dir / match.group(1)
        if not job_dir.exists():
            continue
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "log_results.py"),
                "--job-dir",
                str(job_dir),
                "--results-path",
                str(ROOT / "_backfill_ignore_results.tsv"),
                "--results-detailed-path",
                str(args.results_detailed_path),
                "--model-profile",
                row.get("model_profile", ""),
                "--status",
                row.get("status", "run"),
                "--description",
                desc.split("| job=")[0].strip(),
                "--skip-visuals",
            ],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    ignore_path = ROOT / "_backfill_ignore_results.tsv"
    if ignore_path.exists():
        ignore_path.unlink()
    print(f"Backfilled {args.results_detailed_path}")


if __name__ == "__main__":
    main()
