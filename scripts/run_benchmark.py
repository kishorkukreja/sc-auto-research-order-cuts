from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[1]

if load_dotenv:
    load_dotenv(ROOT / ".env")


def force_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def build_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONLEGACYWINDOWSSTDIO", "0")
    return env


def default_model_profile() -> str:
    provider = os.getenv("MODEL_PROVIDER", "openai").strip().lower()
    if provider == "openrouter":
        model_name = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2").strip()
        return f"openrouter/{model_name}"
    model_name = os.getenv("OPENAI_MODEL", "gpt-5.4").strip()
    reasoning = os.getenv("OPENAI_REASONING_EFFORT", "high").strip().lower()
    return f"openai/{model_name}/{reasoning}"


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
        help="Optional single task name passed to harbor via --task",
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
        default="",
        help="model_profile value written to results.tsv. If omitted, inferred from env vars.",
    )
    parser.add_argument(
        "--benchmark-split",
        default="dev",
        help="Benchmark split label written to results.tsv/results_detailed.tsv.",
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
        default="logs/runs/run.log",
        help="File to capture Harbor stdout/stderr",
    )
    parser.add_argument(
        "--progress-png",
        default="",
        help="PNG path for the auto-generated progress chart",
    )
    parser.add_argument(
        "--progress-svg",
        default="",
        help="SVG path for the auto-generated progress chart",
    )
    return parser.parse_args()


def default_progress_path(kind: str, benchmark_split: str, ext: str) -> str:
    return f"artifacts/plots/{kind}-{benchmark_split}.{ext}"


def run_command(command: list[str], *, stdout_path: Path | None = None) -> None:
    env = build_subprocess_env()
    if stdout_path is None:
        subprocess.run(command, cwd=ROOT, check=True, env=env)
        return

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        assert process.stdout is not None
        for line in process.stdout:
            try:
                print(line, end="")
            except UnicodeEncodeError:
                sys.stdout.buffer.write(line.encode("utf-8", errors="replace"))
                sys.stdout.buffer.flush()
            log_file.write(line)
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)


def harbor_result_exists(output_dir: str, job_name: str) -> bool:
    return (ROOT / output_dir / job_name / "result.json").exists()


def main() -> None:
    force_utf8_stdio()
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
        harbor_cmd.extend(["--task", args.task_name])
    if args.limit is not None:
        harbor_cmd.extend(["-l", str(args.limit)])

    print("Running Harbor:")
    print(" ".join(shlex.quote(part) for part in harbor_cmd))
    try:
        run_command(harbor_cmd, stdout_path=ROOT / args.log_file)
    except subprocess.CalledProcessError:
        if harbor_result_exists(args.output_dir, args.job_name):
            print(
                f"Harbor exited non-zero for {args.job_name}, but result.json exists; continuing to log partial results."
            )
        else:
            raise

    log_cmd = [
        sys.executable,
        "scripts/log_results.py",
        "--job-dir",
        str(Path(args.output_dir) / args.job_name),
        "--pass-threshold",
        str(args.pass_threshold),
        "--model-profile",
        args.model_profile or default_model_profile(),
        "--benchmark-split",
        args.benchmark_split,
        "--status",
        args.status,
        "--description",
        args.description,
        "--progress-png",
        args.progress_png or default_progress_path("progress", args.benchmark_split, "png"),
        "--progress-svg",
        args.progress_svg or default_progress_path("progress", args.benchmark_split, "svg"),
    ]
    run_command(log_cmd)


if __name__ == "__main__":
    main()
