from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_PATH = ROOT / "results.tsv"
DEFAULT_JOBS_DIR = ROOT / "jobs"
DEFAULT_PASS_THRESHOLD = 0.80
DEFAULT_MODEL_PROFILE = ""
DEFAULT_PROGRESS_PNG = ROOT / "progress.png"
DEFAULT_PROGRESS_SVG = ROOT / "progress.svg"


@dataclass
class TrialSummary:
    name: str
    score: float
    turns: float | None
    input_tokens: float | None
    output_tokens: float | None
    cost_usd: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append aggregate Harbor run metrics into results.tsv."
    )
    parser.add_argument("--job-dir", type=Path, help="Specific Harbor job directory.")
    parser.add_argument(
        "--jobs-dir",
        type=Path,
        default=DEFAULT_JOBS_DIR,
        help="Directory containing Harbor jobs. Used when --job-dir is omitted.",
    )
    parser.add_argument(
        "--results-path",
        type=Path,
        default=DEFAULT_RESULTS_PATH,
        help="Path to results.tsv",
    )
    parser.add_argument(
        "--pass-threshold",
        type=float,
        default=DEFAULT_PASS_THRESHOLD,
        help="Score threshold for a task to count as passed.",
    )
    parser.add_argument(
        "--model-profile",
        default=DEFAULT_MODEL_PROFILE,
        help="Model profile label written into results.tsv",
    )
    parser.add_argument(
        "--status",
        default="run",
        help="Status value to write into results.tsv (for example: baseline, keep, discard, run, crash).",
    )
    parser.add_argument(
        "--description",
        default="automatic benchmark run",
        help="Short description written into results.tsv",
    )
    parser.add_argument(
        "--progress-png",
        type=Path,
        default=DEFAULT_PROGRESS_PNG,
        help="Output PNG chart path",
    )
    parser.add_argument(
        "--progress-svg",
        type=Path,
        default=DEFAULT_PROGRESS_SVG,
        help="Output SVG chart path",
    )
    return parser.parse_args()


def default_model_profile() -> str:
    provider = os.getenv("MODEL_PROVIDER", "openai").strip().lower()
    if provider == "openrouter":
        model_name = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2").strip()
        return f"openrouter/{model_name}"
    model_name = os.getenv("OPENAI_MODEL", "gpt-5.4").strip()
    reasoning = os.getenv("OPENAI_REASONING_EFFORT", "high").strip().lower()
    return f"openai/{model_name}/{reasoning}"


def latest_job_dir(jobs_dir: Path) -> Path:
    candidates = [
        path
        for path in jobs_dir.iterdir()
        if path.is_dir() and (path / "config.json").exists()
    ]
    if not candidates:
        raise FileNotFoundError(f"No Harbor job directories found under {jobs_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def parse_reward(trial_dir: Path) -> float:
    reward_txt = trial_dir / "verifier" / "reward.txt"
    reward_json = trial_dir / "verifier" / "reward.json"

    if reward_txt.exists():
        text = reward_txt.read_text(encoding="utf-8-sig").strip()
        return float(text)

    if reward_json.exists():
        payload = json.loads(reward_json.read_text(encoding="utf-8-sig"))
        if "reward" in payload:
            return float(payload["reward"])
        numeric_values = [float(v) for v in payload.values() if isinstance(v, (int, float))]
        if numeric_values:
            return float(numeric_values[0])

    raise FileNotFoundError(f"No reward file found for {trial_dir}")


def parse_trajectory_metrics(trial_dir: Path) -> dict[str, float | None]:
    trajectory_path = trial_dir / "agent" / "trajectory.json"
    if not trajectory_path.exists():
        return {
            "turns": None,
            "input_tokens": None,
            "output_tokens": None,
            "cost_usd": None,
        }

    payload = json.loads(trajectory_path.read_text(encoding="utf-8-sig"))
    final_metrics: dict[str, Any] = payload.get("final_metrics") or {}
    extra: dict[str, Any] = final_metrics.get("extra") or {}

    return {
        "turns": _as_float(extra.get("num_turns")),
        "input_tokens": _as_float(final_metrics.get("total_prompt_tokens")),
        "output_tokens": _as_float(final_metrics.get("total_completion_tokens")),
        "cost_usd": _as_float(final_metrics.get("total_cost_usd")),
    }


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_trials(job_dir: Path) -> list[TrialSummary]:
    trials: list[TrialSummary] = []
    for child in sorted(job_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name in {"agent", "verifier", "artifacts"}:
            continue
        if not ((child / "verifier").exists() or (child / "agent").exists()):
            continue

        try:
            score = parse_reward(child)
        except Exception:
            continue

        metrics = parse_trajectory_metrics(child)
        trials.append(
            TrialSummary(
                name=child.name,
                score=score,
                turns=metrics["turns"],
                input_tokens=metrics["input_tokens"],
                output_tokens=metrics["output_tokens"],
                cost_usd=metrics["cost_usd"],
            )
        )

    if not trials:
        raise RuntimeError(f"No parseable trials found in {job_dir}")
    return trials


def average(values: list[float | None]) -> str:
    actual = [v for v in values if v is not None]
    if not actual:
        return ""
    return f"{sum(actual) / len(actual):.2f}"


def total(values: list[float | None]) -> str:
    actual = [v for v in values if v is not None]
    if not actual:
        return ""
    return f"{sum(actual):.6f}"


def git_commit_short(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip() or "nogit"
    except Exception:
        return "nogit"


def sanitize_tsv(value: str) -> str:
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def ensure_results_header(path: Path) -> None:
    header = (
        "commit\tmodel_profile\tavg_score\tpassed\ttask_scores\tavg_turns\t"
        "avg_input_tokens\tavg_output_tokens\tcost_usd\tstatus\tdescription"
    )
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        path.write_text(header + "\n", encoding="utf-8")


def append_result_row(
    results_path: Path,
    root: Path,
    model_profile: str,
    pass_threshold: float,
    status: str,
    description: str,
    trials: list[TrialSummary],
) -> str:
    ensure_results_header(results_path)

    avg_score = sum(t.score for t in trials) / len(trials)
    passed_count = sum(1 for t in trials if t.score >= pass_threshold)
    task_scores = ";".join(f"{t.name}={t.score:.4f}" for t in trials)

    row = [
        git_commit_short(root),
        model_profile,
        f"{avg_score:.6f}",
        f"{passed_count}/{len(trials)}",
        task_scores,
        average([t.turns for t in trials]),
        average([t.input_tokens for t in trials]),
        average([t.output_tokens for t in trials]),
        total([t.cost_usd for t in trials]),
        sanitize_tsv(status),
        sanitize_tsv(description),
    ]
    line = "\t".join(sanitize_tsv(v) for v in row)

    with results_path.open("a", encoding="utf-8", newline="") as f:
        f.write(line + "\n")
    return line


def main() -> None:
    args = parse_args()
    job_dir = args.job_dir or latest_job_dir(args.jobs_dir)
    trials = summarize_trials(job_dir)
    line = append_result_row(
        results_path=args.results_path,
        root=ROOT,
        model_profile=args.model_profile or default_model_profile(),
        pass_threshold=args.pass_threshold,
        status=args.status,
        description=f"{args.description} | job={job_dir.name}",
        trials=trials,
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_progress_chart.py"),
            "--results-path",
            str(args.results_path),
            "--png-path",
            str(args.progress_png),
            "--svg-path",
            str(args.progress_svg),
        ],
        cwd=ROOT,
        check=True,
    )
    print(f"Logged results row:\n{line}")


if __name__ == "__main__":
    main()
