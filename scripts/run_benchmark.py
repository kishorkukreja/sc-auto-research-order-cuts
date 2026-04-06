from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Harbor benchmark and automatically append aggregate metrics to results.tsv."
    )
    parser.add_argument(
        "--task-path",
        default="tasks",
        help="Dataset/task path passed to harbor via -p",
    )
    parser.add_argument(
        "--task-name",
        help="Optional single task name passed to harbor via --task-name",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=20,
        help="Harbor -n concurrency",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional Harbor -l limit",
    )
    parser.add_argument(
        "--output-dir",
        default="jobs",
        help="Harbor output directory",
    )
    parser.add_argument(
        "--job-name",
        default="latest",
        help="Harbor job name",
    )
    parser.add_argument(
        "--agent-import-path",
        default="agent:AutoAgent",
        help="Harbor --agent-import-path value",
    )
    parser.add_argument(
        "--generate-benchmark",
        action="store_true",
        help="Regenerate synthetic tasks before running Harbor.",
    )
    parser.add_argument(
        "--pass-threshold",
        type=float,
        default=0.80,
        help="Threshold used when logging passed tasks to results.tsv",
    )
    parser.add_argument(
        "--model-profile",
        default="gpt-5.4/high",
        help="model_profile value written to results.tsv",
    )
    parser.add_argument(
        "--status",
        default="run",
        help="status value written to results.tsv",
    )
    parser.add_argument(
        "--description",
        default="automatic benchmark run",
        help="description written to results.tsv",
    )
    parser.add_argument(
        "--log-file",
        default="run.log",
        help="File to capture Harbor stdout/stderr",
    )
    parser.add_argument(
        "--progress-png",
        default="progress.png",
        help="PNG path for the auto-generated progress chart",
    )
    parser.add_argument(
        "--progress-svg",
        default="progress.svg",
        help="SVG path for the auto-generated progress chart",
    )
    return parser.parse_args()


def run_command(command: list[str], *, stdout_path: Path | None = None) -> None:
    if stdout_path is None:
        subprocess.run(command, cwd=ROOT, check=True)
        return

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log_file.write(line)
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)


def main() -> None:
    args = parse_args()

    if args.generate_benchmark:
        run_command([sys.executable, "scripts/generate_benchmark.py"])

    harbor_cmd = [
        "uv",
        "run",
        "harbor",
        "run",
        "-p",
        args.task_path,
        "-n",
        str(args.concurrency),
        "--agent-import-path",
        args.agent_import_path,
        "-o",
        args.output_dir,
        "--job-name",
        args.job_name,
    ]
    if args.task_name:
        harbor_cmd.extend(["--task-name", args.task_name])
    if args.limit is not None:
        harbor_cmd.extend(["-l", str(args.limit)])

    print("Running Harbor:")
    print(" ".join(shlex.quote(part) for part in harbor_cmd))
    run_command(harbor_cmd, stdout_path=ROOT / args.log_file)

    log_cmd = [
        sys.executable,
        "scripts/log_results.py",
        "--jobs-dir",
        args.output_dir,
        "--pass-threshold",
        str(args.pass_threshold),
        "--model-profile",
        args.model_profile,
        "--status",
        args.status,
        "--description",
        args.description,
        "--progress-png",
        args.progress_png,
        "--progress-svg",
        args.progress_svg,
    ]
    run_command(log_cmd)


if __name__ == "__main__":
    main()
