from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANALYSIS_DIR = ROOT / "analysis"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the next harness-improvement proposal from a run analysis."
    )
    parser.add_argument(
        "--analysis-json",
        type=Path,
        help="Path to run_analysis.json. Defaults to the newest analysis under analysis/.",
    )
    parser.add_argument(
        "--analysis-dir",
        type=Path,
        default=DEFAULT_ANALYSIS_DIR,
        help="Parent analysis directory used to infer the latest analysis JSON.",
    )
    parser.add_argument(
        "--proposal-id",
        default="",
        help="Optional explicit proposal_id to write into proposal.json",
    )
    return parser.parse_args()


def latest_analysis_json(analysis_dir: Path) -> Path:
    candidates = sorted(analysis_dir.glob("*/run_analysis.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No run_analysis.json files found under {analysis_dir}")
    return candidates[-1]


def load_analysis(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def choose_proposal(analysis: dict[str, Any], explicit_proposal_id: str = "") -> dict[str, Any]:
    focus = analysis.get("proposal_focus")
    avg_turns = analysis.get("avg_turns") or 0
    avg_input_tokens = analysis.get("avg_input_tokens") or 0
    worst_trials = analysis.get("worst_trials") or []
    worst_names = [trial["task_name"].split("/")[-1] for trial in worst_trials[:3]]
    passed_text = str(analysis.get("passed") or "0/0")
    try:
        passed_num = int(passed_text.split("/", 1)[0])
        passed_den = int(passed_text.split("/", 1)[1])
    except Exception:
        passed_num = 0
        passed_den = 0

    if (
        focus == "prompt_and_validation_tightening"
        and passed_den > 0
        and passed_num < passed_den
        and avg_turns <= 6
        and avg_input_tokens <= 20_000
    ):
        focus = "better_allocation_heuristic"

    if focus == "structured_optimizer_tooling":
        return {
            "proposal_id": explicit_proposal_id or "structured-optimizer",
            "title": "Replace the shell-only workflow with a built-in structured optimizer path",
            "hypothesis": (
                "A dedicated Python allocation tool plus a tighter prompt will cut repeated file reads, "
                "reduce turns, and improve consistency on constrained weeks."
            ),
            "why_now": [
                f"Average turns are {avg_turns}, which is too high for a stable benchmark harness.",
                f"Average input tokens are {avg_input_tokens}, indicating repeated raw-file ingestion.",
                f"Worst tasks currently include {', '.join(worst_names) or 'the benchmark tail'}, which suggests inconsistency on harder scenarios.",
            ],
            "changes": [
                "Add a purpose-built Python tool that loads future_orders.csv and capacity_schedule.csv once and computes a deterministic allocation plan.",
                "Add a validation tool that checks row count, JSON schema, and weekly capacity before finish.",
                "Rewrite the system prompt so the model reads the instruction once, calls the optimizer quickly, and avoids long shell-based exploration.",
                "Reduce MAX_TURNS from a high exploratory ceiling to a tighter operational ceiling.",
            ],
            "expected_impact": [
                "Lower prompt/token footprint",
                "Fewer redundant file reads",
                "Higher tail performance on the worst tasks",
                "Cleaner, more repeatable task trajectories",
            ],
            "acceptance_rule": [
                "Keep if full-benchmark avg_score improves over the current best full run.",
                "Prefer improvements that also reduce avg_turns or avg_input_tokens.",
            ],
            "risk": "The first structured heuristic may improve efficiency more than score; the heuristic should remain simple and general.",
        }

    if focus == "better_allocation_heuristic":
        return {
            "proposal_id": explicit_proposal_id or "better-allocation-heuristic",
            "title": "Strengthen the allocation heuristic for constrained promo/value trade-offs",
            "hypothesis": "A more explicit weighted allocation rule should improve tail performance on harder scenarios.",
            "why_now": [
                "The benchmark tail remains weak even though runs complete successfully.",
                "The current harness relies on ad hoc shell scripts instead of a reusable scoring-oriented heuristic.",
            ],
            "changes": [
                "Create a reusable planning function that allocates by weighted value density and promo/priority protection.",
                "Use history only for lightweight context, not raw transcript expansion.",
                "Validate the plan before writing the final output.",
            ],
            "expected_impact": ["Higher worst-task scores", "Less variance across runs"],
            "acceptance_rule": [
                "Keep if avg_score or passed improves without a large efficiency regression."
            ],
            "risk": "A heuristic that is too narrow could overfit the current synthetic tasks.",
        }

    return {
        "proposal_id": explicit_proposal_id or "prompt-and-validation-tightening",
        "title": "Tighten prompt flow and validation",
        "hypothesis": "A smaller prompt and explicit finish criteria will reduce waste and stabilize runs.",
        "why_now": ["No dominant structural issue detected; improve execution discipline first."],
        "changes": [
            "Shorten the system prompt.",
            "Make validation mandatory before finish.",
            "Reduce MAX_TURNS modestly.",
        ],
        "expected_impact": ["Lower cost", "Slightly better consistency"],
        "acceptance_rule": ["Keep only if score does not regress."],
        "risk": "Limited upside versus a larger tooling improvement.",
    }


def write_outputs(analysis_json: Path, proposal: dict[str, Any]) -> tuple[Path, Path]:
    out_dir = analysis_json.parent
    json_path = out_dir / "proposal.json"
    md_path = out_dir / "proposal.md"
    json_path.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(proposal), encoding="utf-8")
    return json_path, md_path


def render_markdown(proposal: dict[str, Any]) -> str:
    lines = [
        f"# Proposal: {proposal['title']}",
        "",
        f"**ID:** `{proposal['proposal_id']}`",
        "",
        "## Hypothesis",
        proposal["hypothesis"],
        "",
        "## Why now",
    ]
    lines.extend([f"- {item}" for item in proposal.get("why_now", [])])
    lines.extend(["", "## Planned changes"])
    lines.extend([f"- {item}" for item in proposal.get("changes", [])])
    lines.extend(["", "## Expected impact"])
    lines.extend([f"- {item}" for item in proposal.get("expected_impact", [])])
    lines.extend(["", "## Acceptance rule"])
    lines.extend([f"- {item}" for item in proposal.get("acceptance_rule", [])])
    lines.extend(["", "## Risk", proposal.get("risk", "")])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    analysis_json = args.analysis_json or latest_analysis_json(args.analysis_dir)
    analysis = load_analysis(analysis_json)
    proposal = choose_proposal(analysis, explicit_proposal_id=args.proposal_id)
    json_path, md_path = write_outputs(analysis_json, proposal)
    print(f"Wrote proposal:\n- {json_path}\n- {md_path}")


if __name__ == "__main__":
    main()
