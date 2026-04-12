from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "agent.py"
PROGRAM_PATH = ROOT / "program.md"
RESULTS_PATH = ROOT / "results.tsv"
ANALYSIS_DIR = ROOT / "analysis"
EXPERIMENTS_DIR = ROOT / "experiments"
INCUMBENT_AGENT_PATH = EXPERIMENTS_DIR / "incumbent" / "agent.py"
FIXED_BOUNDARY = "# ============================================================================\n# FIXED ADAPTER BOUNDARY: do not modify unless the human explicitly asks.\n"
EDITABLE_START_TOKEN = "# EDITABLE HARNESS"

if load_dotenv:
    load_dotenv(ROOT / ".env")


@dataclass
class ResultRow:
    raw: dict[str, str]

    @property
    def benchmark_scope(self) -> str:
        return self.raw.get("benchmark_scope", "")

    @property
    def avg_score(self) -> float:
        return float(self.raw.get("avg_score", "0") or 0)

    @property
    def passed_num(self) -> int:
        passed = self.raw.get("passed", "0/0")
        try:
            return int(passed.split("/", 1)[0])
        except Exception:
            return 0

    @property
    def passed_den(self) -> int:
        passed = self.raw.get("passed", "0/0")
        try:
            return int(passed.split("/", 1)[1])
        except Exception:
            return 0

    @property
    def avg_turns(self) -> float | None:
        text = self.raw.get("avg_turns", "").strip()
        return float(text) if text else None

    @property
    def avg_input_tokens(self) -> float | None:
        text = self.raw.get("avg_input_tokens", "").strip()
        return float(text) if text else None

    @property
    def status(self) -> str:
        return self.raw.get("status", "")

    @property
    def description(self) -> str:
        return self.raw.get("description", "")

    @property
    def job_name(self) -> str | None:
        match = re.search(r"\bjob=([^\s|]+)", self.description)
        return match.group(1) if match else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a candidate patch to agent.py from proposal.json, run the benchmark, compare to best prior run, and keep/discard automatically."
    )
    parser.add_argument("--proposal-json", type=Path, required=True, help="Path to proposal.json")
    parser.add_argument("--analysis-json", type=Path, help="Optional run_analysis.json path. Defaults to proposal sibling.")
    parser.add_argument("--results-path", type=Path, default=RESULTS_PATH)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--task-path", default="tasks")
    parser.add_argument("--job-name", default="")
    parser.add_argument("--output-dir", type=Path, default=EXPERIMENTS_DIR)
    parser.add_argument("--status", default="candidate")
    parser.add_argument("--description", default="auto candidate iteration")
    parser.add_argument("--benchmark-split", default="dev")
    parser.add_argument("--patch-only", action="store_true", help="Generate and apply the candidate patch but do not benchmark it.")
    parser.add_argument("--keep-on-tie", action="store_true", help="Keep a candidate when primary/secondary metrics tie and efficiency improves.")
    parser.add_argument("--initialize-incumbent-from-current", action="store_true", help="Initialize experiments/incumbent/agent.py from the current working agent before iterating.")
    parser.add_argument("--docker-timeout-sec", type=int, default=60, help="Timeout for Docker preflight checks.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_results(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
        return reader.fieldnames or [], rows


def write_results(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def current_best_full_run(rows: list[dict[str, str]], benchmark_split: str) -> ResultRow | None:
    candidates = [
        ResultRow(row)
        for row in rows
        if row.get("benchmark_scope") == "full"
        and row.get("benchmark_split", "dev") == benchmark_split
        and row.get("status") != "discard"
    ]
    if not candidates:
        return None
    best = candidates[0]
    for row in candidates[1:]:
        if compare_rows(row, best) > 0:
            best = row
    return best


def compare_rows(candidate: ResultRow, incumbent: ResultRow) -> int:
    if candidate.passed_num != incumbent.passed_num:
        return 1 if candidate.passed_num > incumbent.passed_num else -1
    if abs(candidate.avg_score - incumbent.avg_score) > 1e-9:
        return 1 if candidate.avg_score > incumbent.avg_score else -1
    cand_turns = candidate.avg_turns
    inc_turns = incumbent.avg_turns
    if cand_turns is not None and inc_turns is not None and abs(cand_turns - inc_turns) > 1e-9:
        return 1 if cand_turns < inc_turns else -1
    cand_tokens = candidate.avg_input_tokens
    inc_tokens = incumbent.avg_input_tokens
    if cand_tokens is not None and inc_tokens is not None and abs(cand_tokens - inc_tokens) > 1e-9:
        return 1 if cand_tokens < inc_tokens else -1
    return 0


def get_patch_model_provider() -> str:
    provider = os.getenv("AUTO_PATCH_PROVIDER", "").strip().lower()
    if provider:
        return provider
    return os.getenv("MODEL_PROVIDER", "openrouter").strip().lower()


def get_patch_model_name(provider: str) -> str:
    if provider == "openai":
        return os.getenv("AUTO_PATCH_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.4"))
    return os.getenv("AUTO_PATCH_MODEL", os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.7"))


def create_client(provider: str) -> OpenAI:
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for AUTO_PATCH_PROVIDER=openai")
        return OpenAI(api_key=api_key)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required for AUTO_PATCH_PROVIDER=openrouter")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    site_url = os.getenv("OPENROUTER_SITE_URL", "https://github.com/kishorkukreja/sc-auto-research-order-cuts")
    app_name = os.getenv("OPENROUTER_APP_NAME", "sc-auto-research-order-cuts")
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        default_headers={"HTTP-Referer": site_url, "X-Title": app_name},
    )


def split_agent_file(text: str) -> tuple[str, str, str]:
    if EDITABLE_START_TOKEN not in text:
        raise RuntimeError("Could not find EDITABLE HARNESS marker in agent.py")
    if FIXED_BOUNDARY not in text:
        raise RuntimeError("Could not find FIXED ADAPTER BOUNDARY in agent.py")
    fixed_prefix, editable_and_suffix = text.split(EDITABLE_START_TOKEN, 1)
    editable_body, fixed_suffix = editable_and_suffix.split(FIXED_BOUNDARY, 1)
    return fixed_prefix + EDITABLE_START_TOKEN, editable_body, FIXED_BOUNDARY + fixed_suffix


def build_patch_prompt(current_editable: str, proposal: dict[str, Any], analysis: dict[str, Any] | None) -> str:
    analysis_summary = json.dumps(analysis or {}, indent=2)
    proposal_summary = json.dumps(proposal, indent=2)
    return f"""
You are editing only the editable harness section of a Harbor agent in agent.py.

Task:
- Improve the harness according to proposal.json.
- Edit ONLY the code between the `# EDITABLE HARNESS` marker and the `FIXED ADAPTER BOUNDARY` marker.
- Do NOT modify imports, module-level compatibility setup, provider adapter wiring, or anything after the fixed boundary.
- Preserve dual-provider support (OpenAI + OpenRouter).
- Do not remove the Harbor adapter compatibility assumptions established in the current file.
- Prefer built-in Python/function tools over repeated shell exploration.
- Make one concrete, general improvement that is meaningfully different from the current harness.
- Bias strongly toward improving `build_allocation_plan()` rather than just rewriting prompt wording.
- Prefer changing the weekly allocation algorithm over changing imports, provider logic, or transcript formatting.
- Keep the code concise, robust, and syntactically valid.
- Return ONLY the full replacement editable section as plain Python, with no markdown fences.

Allowed mutation targets:
- SYSTEM_PROMPT
- MAX_TURNS
- summarize_inputs
- build_allocation_plan
- validate_allocation_plan

Preferred allocation strategy families to search:
1. weighted_density_greedy
2. weighted_proportional
3. two_stage_promo_protect_then_fill
4. shortage_regime_switch (moderate shortage vs severe shortage)
5. retailer_floor_then_density_fill

Important strategy guidance:
- Always respect weekly capacity.
- Always emit every visible row exactly once.
- Use revenue_weight, priority_multiplier, promo_flag, and orders_placed.
- You may add a small retailer-floor allocation before the main fill if that helps pass count.
- You may switch strategy based on shortage ratio within a week.
- Prefer heuristics that improve passed tasks, not only average score.
- Do not add imports or top-level dependency changes.

Proposal JSON:
{proposal_summary}

Latest analysis JSON:
{analysis_summary}

Current editable section of agent.py:
{current_editable}
""".strip()


def clean_model_output(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_+-]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned.strip())
    if FIXED_BOUNDARY in cleaned:
        cleaned = cleaned.split(FIXED_BOUNDARY, 1)[0]
    return cleaned.rstrip() + "\n"


def validate_candidate_editable(candidate_editable: str) -> tuple[bool, str]:
    try:
        tree = ast.parse(candidate_editable)
    except SyntaxError as exc:
        return False, f"syntax_error:{exc}"

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False, "top_level_import_not_allowed"
    return True, "ok"


def generate_candidate_prefix(current_editable: str, proposal: dict[str, Any], analysis: dict[str, Any] | None) -> tuple[str, dict[str, str]]:
    provider = get_patch_model_provider()
    model = get_patch_model_name(provider)
    client = create_client(provider)
    prompt = build_patch_prompt(current_editable, proposal, analysis)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert Python harness engineer. Return only code."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content or ""
    cleaned = clean_model_output(content)
    metadata = {"provider": provider, "model": model}
    return cleaned, metadata


def py_compile(path: Path) -> None:
    subprocess.run([sys.executable, "-m", "py_compile", str(path)], cwd=ROOT, check=True)


def docker_preflight(timeout_sec: int) -> None:
    subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )


def remove_job_dir(job_name: str) -> None:
    job_dir = ROOT / "jobs" / job_name
    if job_dir.exists():
        shutil.rmtree(job_dir)


def run_benchmark(job_name: str, description: str, concurrency: int, status: str, benchmark_split: str, task_path: str) -> None:
    remove_job_dir(job_name)
    cmd = [
        sys.executable,
        "scripts/run_benchmark.py",
        "--task-path",
        task_path,
        "--concurrency",
        str(concurrency),
        "--job-name",
        job_name,
        "--benchmark-split",
        benchmark_split,
        "--status",
        status,
        "--description",
        description,
        "--log-file",
        f"run-{job_name}.log",
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def ensure_logged_row(job_name: str, status: str, description: str, benchmark_split: str) -> None:
    job_dir = ROOT / "jobs" / job_name
    if not job_dir.exists():
        raise FileNotFoundError(f"Job directory does not exist: {job_dir}")
    subprocess.run(
        [
            sys.executable,
            "scripts/log_results.py",
            "--job-dir",
            str(job_dir),
            "--results-path",
            str(RESULTS_PATH),
            "--results-detailed-path",
            str(ROOT / "results_detailed.tsv"),
            "--benchmark-split",
            benchmark_split,
            "--status",
            status,
            "--description",
            description,
        ],
        cwd=ROOT,
        check=True,
    )


def find_row_by_job(rows: list[dict[str, str]], job_name: str) -> tuple[int, dict[str, str]]:
    for idx in range(len(rows) - 1, -1, -1):
        row = rows[idx]
        description = row.get("description", "")
        if f"job={job_name}" in description:
            return idx, row
    raise RuntimeError(f"Could not find results row for job {job_name}")


def update_row_status(results_path: Path, job_name: str, new_status: str, extra_note: str = "") -> None:
    fieldnames, rows = load_results(results_path)
    idx, row = find_row_by_job(rows, job_name)
    row["status"] = new_status
    if extra_note:
        description = row.get("description", "")
        if extra_note not in description:
            row["description"] = f"{description} | {extra_note}".strip()
    rows[idx] = row
    write_results(results_path, fieldnames, rows)


def append_crash_row(results_path: Path, job_name: str, description: str, benchmark_split: str, extra_note: str = "") -> None:
    header = (
        "commit\tmodel_profile\tbenchmark_split\tbenchmark_scope\tavg_score\tpassed\ttask_scores\tavg_turns\t"
        "avg_input_tokens\tavg_output_tokens\tcost_usd\tstatus\tdescription"
    )
    if not results_path.exists() or not results_path.read_text(encoding="utf-8-sig").strip():
        results_path.write_text(header + "\n", encoding="utf-8")

    commit = "nogit"
    try:
        commit = (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            ).stdout.strip()
            or "nogit"
        )
    except Exception:
        pass

    provider = os.getenv("MODEL_PROVIDER", "openrouter").strip().lower()
    if provider == "openrouter":
        model_profile = f"openrouter/{os.getenv('OPENROUTER_MODEL', 'minimax/minimax-m2.7').strip()}"
    else:
        model_profile = f"openai/{os.getenv('OPENAI_MODEL', 'gpt-5.4').strip()}/{os.getenv('OPENAI_REASONING_EFFORT', 'high').strip().lower()}"

    desc = f"{description} | job={job_name}"
    if extra_note:
        desc = f"{desc} | {extra_note}"
    row = [
        commit,
        model_profile,
        benchmark_split,
        "full",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "crash",
        desc,
    ]
    with results_path.open("a", encoding="utf-8", newline="") as f:
        f.write("\t".join(row) + "\n")


def render_decision(candidate: ResultRow, incumbent: ResultRow | None, keep: bool) -> dict[str, Any]:
    payload = {
        "candidate": candidate.raw,
        "incumbent": incumbent.raw if incumbent else None,
        "decision": "keep" if keep else "discard",
        "compare_result": compare_rows(candidate, incumbent) if incumbent else 1,
    }
    return payload


def main() -> None:
    args = parse_args()
    proposal = load_json(args.proposal_json)
    analysis_json = args.analysis_json or args.proposal_json.with_name("run_analysis.json")
    analysis = load_json(analysis_json) if analysis_json.exists() else None

    fieldnames, rows = load_results(args.results_path)
    incumbent = current_best_full_run(rows, args.benchmark_split)

    live_agent = AGENT_PATH.read_text(encoding="utf-8")
    if args.initialize_incumbent_from_current or not INCUMBENT_AGENT_PATH.exists():
        INCUMBENT_AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        INCUMBENT_AGENT_PATH.write_text(live_agent, encoding="utf-8")
    incumbent_agent_text = INCUMBENT_AGENT_PATH.read_text(encoding="utf-8")
    fixed_prefix, current_editable, suffix = split_agent_file(incumbent_agent_text)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_name = args.job_name or f"auto-{proposal.get('proposal_id', 'candidate')}-{timestamp}"
    exp_dir = args.output_dir / job_name
    exp_dir.mkdir(parents=True, exist_ok=True)

    backup_agent = exp_dir / "agent.before.py"
    backup_agent.write_text(live_agent, encoding="utf-8")
    (exp_dir / "agent.incumbent.py").write_text(incumbent_agent_text, encoding="utf-8")
    (exp_dir / "proposal.json").write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    if analysis:
        (exp_dir / "run_analysis.json").write_text(json.dumps(analysis, indent=2), encoding="utf-8")

    candidate_prefix, patch_meta = generate_candidate_prefix(current_editable, proposal, analysis)
    (exp_dir / "candidate_prefix.py").write_text(candidate_prefix, encoding="utf-8")
    (exp_dir / "patch_meta.json").write_text(json.dumps(patch_meta, indent=2), encoding="utf-8")

    is_valid, validation_reason = validate_candidate_editable(candidate_prefix)
    if not is_valid:
        decision = {
            "decision": "discard",
            "reason": validation_reason,
            "proposal": proposal,
            "patch_meta": patch_meta,
        }
        (exp_dir / "decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
        print(f"Decision: DISCARD ({job_name}) because candidate failed validation: {validation_reason}")
        return

    if candidate_prefix.strip() == current_editable.strip():
        decision = {
            "decision": "discard",
            "reason": "no_change",
            "proposal": proposal,
            "patch_meta": patch_meta,
        }
        (exp_dir / "decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
        print(f"Decision: DISCARD ({job_name}) because generated candidate matched incumbent.")
        return

    new_agent = fixed_prefix + candidate_prefix + suffix
    AGENT_PATH.write_text(new_agent, encoding="utf-8")

    try:
        py_compile(AGENT_PATH)
    except Exception as exc:
        shutil.copyfile(INCUMBENT_AGENT_PATH, AGENT_PATH)
        append_crash_row(
            args.results_path,
            job_name,
            args.description,
            args.benchmark_split,
            extra_note=f"compile_error={type(exc).__name__}",
        )
        (exp_dir / "decision.json").write_text(
            json.dumps(
                {
                    "decision": "discard",
                    "reason": "compile_error",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Decision: DISCARD ({job_name}) due to compile error; restored incumbent agent.py")
        return

    if args.patch_only:
        print(f"Patched {AGENT_PATH} using {patch_meta['provider']}/{patch_meta['model']} and stopped before benchmark.")
        return

    description = f"{args.description} | proposal={proposal.get('proposal_id', 'unknown')}"
    try:
        docker_preflight(timeout_sec=args.docker_timeout_sec)
        run_benchmark(
            job_name=job_name,
            description=description,
            concurrency=args.concurrency,
            status=args.status,
            benchmark_split=args.benchmark_split,
            task_path=args.task_path,
        )
    except Exception as exc:
        shutil.copyfile(INCUMBENT_AGENT_PATH, AGENT_PATH)
        append_crash_row(
            args.results_path,
            job_name,
            description,
            args.benchmark_split,
            extra_note=f"error={type(exc).__name__}",
        )
        (exp_dir / "decision.json").write_text(
            json.dumps(
                {
                    "decision": "crash",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        raise

    fieldnames, rows = load_results(args.results_path)
    try:
        _, cand_row_raw = find_row_by_job(rows, job_name)
    except RuntimeError:
        ensure_logged_row(
            job_name=job_name,
            status=args.status,
            description=description,
            benchmark_split=args.benchmark_split,
        )
        fieldnames, rows = load_results(args.results_path)
        _, cand_row_raw = find_row_by_job(rows, job_name)
    candidate = ResultRow(cand_row_raw)

    keep = True if incumbent is None else compare_rows(candidate, incumbent) > 0 or (
        args.keep_on_tie and compare_rows(candidate, incumbent) == 0
    )
    decision = render_decision(candidate, incumbent, keep)
    (exp_dir / "decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")

    if keep:
        update_row_status(args.results_path, job_name, "keep", extra_note=f"incumbent={incumbent.job_name if incumbent else 'none'}")
        INCUMBENT_AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(AGENT_PATH, INCUMBENT_AGENT_PATH)
        shutil.copyfile(AGENT_PATH, exp_dir / "agent.keep.py")
        print(f"Decision: KEEP ({job_name})")
    else:
        shutil.copyfile(AGENT_PATH, exp_dir / "agent.discarded_candidate.py")
        shutil.copyfile(INCUMBENT_AGENT_PATH, AGENT_PATH)
        update_row_status(args.results_path, job_name, "discard", extra_note=f"incumbent={incumbent.job_name if incumbent else 'none'}")
        print(f"Decision: DISCARD ({job_name}) and restored incumbent agent.py")


if __name__ == "__main__":
    main()
