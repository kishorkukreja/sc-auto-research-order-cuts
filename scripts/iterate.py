from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Semi-automated outer-loop scaffold: analyze a run and propose the next harness change."
    )
    parser.add_argument("--job-dir", type=Path, help="Specific Harbor job directory to inspect.")
    parser.add_argument(
        "--jobs-dir",
        type=Path,
        default=ROOT / "jobs",
        help="Parent jobs directory used when --job-dir is omitted.",
    )
    parser.add_argument(
        "--results-path",
        type=Path,
        default=ROOT / "results.tsv",
        help="results.tsv used to infer the latest full run.",
    )
    parser.add_argument(
        "--analysis-dir",
        type=Path,
        default=ROOT / "analysis",
        help="Directory where iteration analysis/proposals will be written.",
    )
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    args = parse_args()
    analyze_cmd = [
        sys.executable,
        "scripts/analyze_run.py",
        "--jobs-dir",
        str(args.jobs_dir),
        "--results-path",
        str(args.results_path),
        "--output-dir",
        str(args.analysis_dir),
    ]
    if args.job_dir:
        analyze_cmd.extend(["--job-dir", str(args.job_dir)])
    run(analyze_cmd)

    propose_cmd = [
        sys.executable,
        "scripts/propose_harness_change.py",
        "--analysis-dir",
        str(args.analysis_dir),
    ]
    run(propose_cmd)

    print("Iteration scaffold complete. Inspect analysis/<job>/run_analysis.md and proposal.md before patching the harness.")


if __name__ == "__main__":
    main()
