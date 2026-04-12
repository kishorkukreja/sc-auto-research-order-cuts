from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS_DIR = ROOT / "jobs"
DEFAULT_RESULTS_PATH = ROOT / "results.tsv"
DEFAULT_OUTPUT_DIR = ROOT / "analysis"


@dataclass
class TrialAnalysis:
    trial_name: str
    task_name: str
    score: float
    input_tokens: float | None
    output_tokens: float | None
    turns: float | None
    duration_sec: float | None
    tool_calls: int
    run_shell_calls: int
    file_read_commands: int
    csv_read_commands: int
    write_commands: int
    unique_files_read: list[str]
    commands_sample: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze a Harbor benchmark job and emit machine-readable failure/improvement signals."
    )
    parser.add_argument("--job-dir", type=Path, help="Specific Harbor job directory to analyze.")
    parser.add_argument(
        "--jobs-dir",
        type=Path,
        default=DEFAULT_JOBS_DIR,
        help="Directory containing Harbor job directories.",
    )
    parser.add_argument(
        "--results-path",
        type=Path,
        default=DEFAULT_RESULTS_PATH,
        help="results.tsv used to infer the latest full benchmark job when --job-dir is omitted.",
    )
    parser.add_argument(
        "--benchmark-split",
        default="dev",
        help="Benchmark split to analyze when inferring the latest job.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where JSON and markdown analysis will be written.",
    )
    return parser.parse_args()


def infer_latest_full_job(results_path: Path, jobs_dir: Path, benchmark_split: str) -> Path:
    if results_path.exists():
        lines = results_path.read_text(encoding="utf-8-sig").splitlines()
        if len(lines) >= 2:
            header = lines[0].split("\t")
            rows = [dict(zip(header, line.split("\t"))) for line in lines[1:] if line.strip()]
            full_rows = [
                row
                for row in rows
                if row.get("benchmark_scope", "full") == "full"
                and row.get("benchmark_split", "dev") == benchmark_split
                and row.get("avg_score", "").strip()
                and row.get("status", "").strip().lower() != "crash"
            ]
            for row in reversed(full_rows):
                description = row.get("description", "")
                match = re.search(r"\bjob=([^\s|]+)", description)
                if match:
                    candidate = jobs_dir / match.group(1)
                    if candidate.exists():
                        return candidate

    candidates = [
        path for path in jobs_dir.iterdir() if path.is_dir() and (path / "config.json").exists()
    ]
    if not candidates:
        raise FileNotFoundError(f"No Harbor jobs found under {jobs_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def duration_seconds(result_payload: dict[str, Any]) -> float | None:
    agent_exec = result_payload.get("agent_execution") or {}
    start = parse_iso(agent_exec.get("started_at"))
    end = parse_iso(agent_exec.get("finished_at"))
    if start and end:
        return max(0.0, (end - start).total_seconds())
    return None


def parse_trial_metrics(result_payload: dict[str, Any], trajectory_payload: dict[str, Any] | None) -> tuple[float | None, float | None, float | None]:
    agent_result = result_payload.get("agent_result") or {}
    input_tokens = _as_float(agent_result.get("n_input_tokens"))
    output_tokens = _as_float(agent_result.get("n_output_tokens"))
    turns = None

    if trajectory_payload:
        final_metrics = trajectory_payload.get("final_metrics") or {}
        extra = final_metrics.get("extra") or {}
        input_tokens = input_tokens or _as_float(final_metrics.get("total_prompt_tokens"))
        output_tokens = output_tokens or _as_float(final_metrics.get("total_completion_tokens"))
        turns = _as_float(extra.get("num_turns"))

    return input_tokens, output_tokens, turns


def parse_exception_turns(result_payload: dict[str, Any]) -> float | None:
    exception_info = result_payload.get("exception_info") or {}
    message = str(exception_info.get("exception_message", ""))
    if "Max turns (" in message:
        try:
            return float(message.split("Max turns (", 1)[1].split(")", 1)[0])
        except Exception:
            return None
    return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_commands(trajectory_payload: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for step in trajectory_payload.get("steps", []):
        for tool_call in step.get("tool_calls", []):
            if tool_call.get("function_name") != "run_shell":
                continue
            arguments = tool_call.get("arguments") or {}
            command = arguments.get("command")
            if isinstance(command, str):
                commands.append(command)
    return commands


def classify_commands(commands: list[str]) -> dict[str, Any]:
    read_patterns = [
        r"\bcat\b",
        r"\bhead\b",
        r"\btail\b",
        r"\bsed\b",
        r"\bawk\b",
        r"\bgrep\b",
        r"\bls\b",
        r"\bfind\b",
        r"read_csv",
    ]
    write_patterns = [
        r">",
        r"json\.dump",
        r"to_csv",
        r"to_json",
        r"write_text",
        r"allocation_plan\.json",
    ]
    file_ref_pattern = re.compile(r"/task/environment/files/[A-Za-z0-9_.-]+")

    file_reads = 0
    csv_reads = 0
    writes = 0
    file_counter: Counter[str] = Counter()

    for command in commands:
        lowered = command.lower()
        if any(re.search(pattern, lowered) for pattern in read_patterns):
            file_reads += 1
        if ".csv" in lowered or "read_csv" in lowered:
            csv_reads += 1
        if any(re.search(pattern, command) for pattern in write_patterns):
            writes += 1
        for match in file_ref_pattern.findall(command):
            file_counter[Path(match).name] += 1

    return {
        "file_read_commands": file_reads,
        "csv_read_commands": csv_reads,
        "write_commands": writes,
        "unique_files_read": sorted(file_counter.keys()),
        "repeated_file_reads": {name: count for name, count in file_counter.items() if count > 1},
    }


def analyze_trial(trial_dir: Path) -> TrialAnalysis | None:
    result_path = trial_dir / "result.json"
    reward_path = trial_dir / "verifier" / "reward.txt"
    trajectory_path = trial_dir / "agent" / "trajectory.json"
    if not result_path.exists():
        return None

    result_payload = load_json(result_path)
    trajectory_payload = load_json(trajectory_path) if trajectory_path.exists() else None
    if reward_path.exists():
        score = float(reward_path.read_text(encoding="utf-8-sig").strip())
    elif result_payload.get("exception_info"):
        score = 0.0
    else:
        return None
    input_tokens, output_tokens, turns = parse_trial_metrics(result_payload, trajectory_payload)
    turns = turns or parse_exception_turns(result_payload)
    commands = extract_commands(trajectory_payload or {})
    cmd_stats = classify_commands(commands)

    return TrialAnalysis(
        trial_name=trial_dir.name,
        task_name=str(result_payload.get("task_name", "")),
        score=score,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        turns=turns,
        duration_sec=duration_seconds(result_payload),
        tool_calls=len(commands),
        run_shell_calls=len(commands),
        file_read_commands=cmd_stats["file_read_commands"],
        csv_read_commands=cmd_stats["csv_read_commands"],
        write_commands=cmd_stats["write_commands"],
        unique_files_read=cmd_stats["unique_files_read"],
        commands_sample=commands[:5],
    )


def summarize_job(job_dir: Path) -> dict[str, Any]:
    trials: list[TrialAnalysis] = []
    for child in sorted(job_dir.iterdir()):
        if child.is_dir():
            analysis = analyze_trial(child)
            if analysis:
                trials.append(analysis)
    if not trials:
        raise RuntimeError(f"No trial artifacts found in {job_dir}")

    scores = [trial.score for trial in trials]
    turn_values = [trial.turns for trial in trials if trial.turns is not None]
    input_values = [trial.input_tokens for trial in trials if trial.input_tokens is not None]
    output_values = [trial.output_tokens for trial in trials if trial.output_tokens is not None]
    duration_values = [trial.duration_sec for trial in trials if trial.duration_sec is not None]
    read_counts = [trial.file_read_commands for trial in trials]
    csv_counts = [trial.csv_read_commands for trial in trials]

    task_buckets = defaultdict(list)
    for trial in trials:
        task_buckets[_short_task_name(trial.task_name)].append(trial.score)

    worst_trials = sorted(trials, key=lambda t: t.score)[:3]
    best_trials = sorted(trials, key=lambda t: t.score, reverse=True)[:3]
    avg_score = statistics.mean(scores)
    pass_count = sum(1 for score in scores if score >= 0.80)
    med_score = statistics.median(scores)

    heuristics: list[str] = []
    if input_values and statistics.mean(input_values) > 175_000:
        heuristics.append("high_input_tokens")
    if turn_values and statistics.mean(turn_values) > 8:
        heuristics.append("high_turn_count")
    if read_counts and statistics.mean(read_counts) > 4:
        heuristics.append("heavy_file_reading")
    if csv_counts and statistics.mean(csv_counts) > 2:
        heuristics.append("repeated_csv_access")
    if min(scores) < 0.72:
        heuristics.append("low_tail_performance")
    if (max(scores) - min(scores)) > 0.15:
        heuristics.append("high_run_variance")

    root_causes = infer_root_causes(heuristics)
    proposal_focus = choose_proposal_focus(heuristics)

    return {
        "job_name": job_dir.name,
        "job_dir": str(job_dir),
        "n_trials": len(trials),
        "avg_score": round(avg_score, 6),
        "median_score": round(med_score, 6),
        "best_score": round(max(scores), 6),
        "worst_score": round(min(scores), 6),
        "passed": f"{pass_count}/{len(trials)}",
        "avg_turns": round(statistics.mean(turn_values), 2) if turn_values else None,
        "avg_input_tokens": round(statistics.mean(input_values), 2) if input_values else None,
        "avg_output_tokens": round(statistics.mean(output_values), 2) if output_values else None,
        "avg_duration_sec": round(statistics.mean(duration_values), 2) if duration_values else None,
        "heuristics": heuristics,
        "root_causes": root_causes,
        "proposal_focus": proposal_focus,
        "worst_trials": [_trial_to_dict(trial) for trial in worst_trials],
        "best_trials": [_trial_to_dict(trial) for trial in best_trials],
        "score_by_task": {
            task: round(statistics.mean(values), 6) for task, values in sorted(task_buckets.items())
        },
        "notes": build_notes(heuristics, trials),
        "trials": [_trial_to_dict(trial) for trial in trials],
    }


def _short_task_name(task_name: str) -> str:
    return task_name.split("/")[-1] if "/" in task_name else task_name


def _trial_to_dict(trial: TrialAnalysis) -> dict[str, Any]:
    return {
        "trial_name": trial.trial_name,
        "task_name": trial.task_name,
        "score": round(trial.score, 6),
        "input_tokens": trial.input_tokens,
        "output_tokens": trial.output_tokens,
        "turns": trial.turns,
        "duration_sec": trial.duration_sec,
        "tool_calls": trial.tool_calls,
        "run_shell_calls": trial.run_shell_calls,
        "file_read_commands": trial.file_read_commands,
        "csv_read_commands": trial.csv_read_commands,
        "write_commands": trial.write_commands,
        "unique_files_read": trial.unique_files_read,
        "commands_sample": trial.commands_sample,
    }


def infer_root_causes(heuristics: list[str]) -> list[str]:
    root_causes: list[str] = []
    if "high_input_tokens" in heuristics or "heavy_file_reading" in heuristics:
        root_causes.append("The harness is spending too much budget rereading raw files instead of using structured preprocessing.")
    if "high_turn_count" in heuristics:
        root_causes.append("The agent is taking too many conversational turns before writing a plan.")
    if "low_tail_performance" in heuristics or "high_run_variance" in heuristics:
        root_causes.append("The current shell-only workflow is inconsistent on harder constrained scenarios.")
    if not root_causes:
        root_causes.append("No single dominant root cause detected; prioritize the largest efficiency bottleneck first.")
    return root_causes


def choose_proposal_focus(heuristics: list[str]) -> str:
    if {"high_input_tokens", "heavy_file_reading", "high_turn_count"} & set(heuristics):
        return "structured_optimizer_tooling"
    if "low_tail_performance" in heuristics:
        return "better_allocation_heuristic"
    return "prompt_and_validation_tightening"


def build_notes(heuristics: list[str], trials: list[TrialAnalysis]) -> list[str]:
    notes: list[str] = []
    if "high_input_tokens" in heuristics:
        notes.append("Average prompt footprint is high; the agent is likely ingesting more raw CSV content than necessary.")
    if "high_turn_count" in heuristics:
        notes.append("Average turns are above the desired range for a benchmark harness and suggest over-exploration.")
    if "heavy_file_reading" in heuristics:
        notes.append("Many tool calls are file reads rather than purpose-built computations.")
    low_trials = [trial for trial in trials if trial.score < 0.76]
    if low_trials:
        names = ", ".join(_short_task_name(trial.task_name) for trial in low_trials[:4])
        notes.append(f"Tail-risk tasks below 0.76 include: {names}.")
    return notes


def write_outputs(output_dir: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "run_analysis.json"
    md_path = output_dir / "run_analysis.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Run analysis: {payload['job_name']}",
        "",
        f"- avg_score: **{payload['avg_score']:.6f}**",
        f"- passed: **{payload['passed']}**",
        f"- avg_turns: **{payload.get('avg_turns')}**",
        f"- avg_input_tokens: **{payload.get('avg_input_tokens')}**",
        f"- avg_output_tokens: **{payload.get('avg_output_tokens')}**",
        f"- avg_duration_sec: **{payload.get('avg_duration_sec')}**",
        "",
        "## Heuristics triggered",
    ]
    heuristics = payload.get("heuristics") or []
    if heuristics:
        lines.extend([f"- {item}" for item in heuristics])
    else:
        lines.append("- none")

    lines.extend(["", "## Root causes"])
    lines.extend([f"- {item}" for item in payload.get("root_causes", [])])

    lines.extend(["", "## Worst tasks"])
    for trial in payload.get("worst_trials", []):
        lines.append(
            f"- `{_short_task_name(trial['task_name'])}` score={trial['score']:.4f}, turns={trial.get('turns')}, input_tokens={trial.get('input_tokens')}"
        )

    lines.extend(["", "## Notes"])
    lines.extend([f"- {item}" for item in payload.get("notes", [])])

    lines.extend(
        [
            "",
            "## Proposed focus",
            f"`{payload.get('proposal_focus')}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    job_dir = args.job_dir or infer_latest_full_job(args.results_path, args.jobs_dir, args.benchmark_split)
    payload = summarize_job(job_dir)
    output_dir = args.output_dir / job_dir.name
    json_path, md_path = write_outputs(output_dir, payload)
    print(f"Wrote analysis:\n- {json_path}\n- {md_path}")


if __name__ == "__main__":
    main()
