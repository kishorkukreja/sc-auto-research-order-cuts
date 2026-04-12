from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the unattended outer loop: analyze -> propose -> auto-iterate for N iterations."
    )
    parser.add_argument("--iterations", type=int, default=5, help="Number of outer-loop iterations.")
    parser.add_argument("--concurrency", type=int, default=1, help="Benchmark concurrency passed to auto_iterate.py.")
    parser.add_argument("--task-path", default="tasks", help="Task directory to use for benchmark runs.")
    parser.add_argument("--benchmark-split", default="dev", help="Benchmark split label used for analysis/logging.")
    parser.add_argument("--analysis-dir", type=Path, default=ROOT / "analysis")
    parser.add_argument("--results-path", type=Path, default=ROOT / "results.tsv")
    parser.add_argument("--jobs-dir", type=Path, default=ROOT / "jobs")
    parser.add_argument("--initialize-incumbent-from-current", action="store_true")
    parser.add_argument("--stop-on-crash", action="store_true", default=True)
    parser.add_argument("--continue-on-discard", action="store_true", default=True)
    parser.add_argument("--proposal-prefix", default="outer-loop")
    parser.add_argument("--description-prefix", default="outer loop auto iteration")
    parser.add_argument("--patch-only", action="store_true", help="Generate and apply candidate patches without running the benchmark.")
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def latest_analysis_json(analysis_dir: Path) -> Path:
    candidates = sorted(analysis_dir.glob("*/run_analysis.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No run_analysis.json files found under {analysis_dir}")
    return candidates[-1]


def main() -> None:
    args = parse_args()
    for iteration in range(1, args.iterations + 1):
        print(f"\n=== OUTER LOOP ITERATION {iteration}/{args.iterations} ===")
        run(
            [
                sys.executable,
                "scripts/analyze_run.py",
                "--jobs-dir",
                str(args.jobs_dir),
                "--results-path",
                str(args.results_path),
                "--benchmark-split",
                args.benchmark_split,
                "--output-dir",
                str(args.analysis_dir),
            ]
        )

        analysis_json = latest_analysis_json(args.analysis_dir)
        proposal_id = f"{args.proposal_prefix}-iter-{iteration:02d}"
        run(
            [
                sys.executable,
                "scripts/propose_harness_change.py",
                "--analysis-json",
                str(analysis_json),
                "--proposal-id",
                proposal_id,
            ]
        )
        proposal_json = analysis_json.with_name("proposal.json")

        job_name = f"{proposal_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        auto_cmd = [
            sys.executable,
            "scripts/auto_iterate.py",
            "--proposal-json",
            str(proposal_json),
            "--analysis-json",
            str(analysis_json),
            "--concurrency",
            str(args.concurrency),
            "--benchmark-split",
            args.benchmark_split,
            "--task-path",
            args.task_path,
            "--job-name",
            job_name,
            "--description",
            f"{args.description_prefix} {iteration}",
        ]
        if iteration == 1 and args.initialize_incumbent_from_current:
            auto_cmd.append("--initialize-incumbent-from-current")
        if args.patch_only:
            auto_cmd.append("--patch-only")

        try:
            run(auto_cmd)
        except subprocess.CalledProcessError:
            print(f"Iteration {iteration} crashed.")
            if args.stop_on_crash:
                raise
        if not args.patch_only:
            run([sys.executable, "scripts/generate_progress_chart.py"])

    print("\nOuter loop completed.")


if __name__ == "__main__":
    main()
