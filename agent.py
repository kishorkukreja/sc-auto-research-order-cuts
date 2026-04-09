"""Single-file Harbor agent harness: --agent-import-path agent:AutoAgent."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from agents import (
    Agent,
    ModelSettings,
    Runner,
    function_tool,
    set_default_openai_client,
    set_tracing_disabled,
)
from agents.items import (
    ItemHelpers,
    MessageOutputItem,
    ReasoningItem,
    ToolCallItem,
    ToolCallOutputItem,
)
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from agents.tool import FunctionTool
from agents.usage import Usage
from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from openai import AsyncOpenAI
from openai.types.shared import Reasoning

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

if load_dotenv:
    load_dotenv()


# ============================================================================
# EDITABLE HARNESS — prompt, tools, agent construction
# ============================================================================

SYSTEM_PROMPT = """
You are a supply-chain allocation agent.

Your input message already contains the full task instruction. Do not waste turns
re-reading large raw CSV files unless a built-in tool fails.

Default workflow:
1. Call summarize_inputs once.
2. Call build_allocation_plan once, using the default score-aligned strategy.
3. Call validate_allocation_plan.
4. If validation is clean, finish with a very short summary.
5. Use run_shell only as a fallback.

Important rules:
- Never rely on mental math for allocations.
- Prefer the structured optimizer and validator tools over ad hoc shell exploration.
- Optimize for the weighted fill-rate objective under weekly capacity.
- Keep the plan feasible and include every visible (week, sku, retailer) row exactly once.
- Finish with a concise summary of what you wrote.
""".strip()

MODEL = "gpt-5.4"
MAX_TURNS = 10


def get_provider() -> str:
    return os.getenv("MODEL_PROVIDER", "openai").strip().lower()


def get_model_name() -> str:
    provider = get_provider()
    if provider == "openrouter":
        return os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2").strip()
    return os.getenv("OPENAI_MODEL", MODEL).strip()


def get_model_profile() -> str:
    provider = get_provider()
    model_name = get_model_name()
    if provider == "openrouter":
        return f"openrouter/{model_name}"
    reasoning = os.getenv("OPENAI_REASONING_EFFORT", "high").strip().lower()
    return f"openai/{model_name}/{reasoning}"


def create_model_settings() -> ModelSettings:
    provider = get_provider()
    if provider == "openrouter":
        return ModelSettings()

    reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "high").strip().lower()
    return ModelSettings(reasoning=Reasoning(effort=reasoning_effort))


def create_model() -> str | OpenAIChatCompletionsModel:
    provider = get_provider()
    model_name = get_model_name()

    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "MODEL_PROVIDER=openrouter requires OPENROUTER_API_KEY to be set."
            )

        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        site_url = os.getenv(
            "OPENROUTER_SITE_URL",
            "https://github.com/kishorkukreja/sc-auto-research-order-cuts",
        )
        app_name = os.getenv(
            "OPENROUTER_APP_NAME",
            "sc-auto-research-order-cuts",
        )
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "HTTP-Referer": site_url,
                "X-Title": app_name,
            },
        )
        set_default_openai_client(client, use_for_tracing=False)
        set_tracing_disabled(True)
        return OpenAIChatCompletionsModel(model=model_name, openai_client=client)

    set_tracing_disabled(False)
    return model_name


def create_tools(environment: BaseEnvironment) -> list[FunctionTool]:
    """Create tools for the agent. Add new tools here."""

    async def _exec(command: str, timeout_sec: int = 120) -> str:
        try:
            result = await environment.exec(command=command, timeout_sec=timeout_sec)
            out = ""
            if result.stdout:
                out += result.stdout
            if result.stderr:
                out += (
                    f"\nSTDERR:\n{result.stderr}"
                    if out
                    else f"STDERR:\n{result.stderr}"
                )
            return out or "(no output)"
        except Exception as exc:
            return f"ERROR: {exc}"

    async def _exec_python(script: str, timeout_sec: int = 120) -> str:
        command = (
            "cat <<'PY' > /tmp/autoagent_tool.py\n"
            + script
            + "\nPY\npython3 /tmp/autoagent_tool.py"
        )
        return await _exec(command, timeout_sec=timeout_sec)

    @function_tool
    async def run_shell(command: str) -> str:
        """Run a shell command in the task environment. Returns stdout and stderr."""
        return await _exec(command, timeout_sec=60)

    @function_tool
    async def summarize_inputs() -> str:
        """Return a compact summary of the visible task files and the recommended allocation strategy."""
        script = r"""
import json
from pathlib import Path
import pandas as pd

base = Path("/task/environment/files")
future = pd.read_csv(base / "future_orders.csv")
capacity_path = base / "capacity_schedule.csv"
capacity = pd.read_csv(capacity_path) if capacity_path.exists() else None
train_path = base / "train_history.csv"
train = pd.read_csv(train_path) if train_path.exists() else None
scenario_path = base / "scenario_notes.json"
scenario = {}
if scenario_path.exists():
    try:
        scenario = json.loads(scenario_path.read_text())
    except Exception:
        scenario = {}

future = future.copy()
future["priority_weight"] = future["revenue_weight"].fillna(0) * future["priority_multiplier"].fillna(1)
future["score_per_case"] = future["priority_weight"] / future["orders_placed"].clip(lower=1)
future["score_per_case"] = future["score_per_case"] * future["promo_flag"].map(lambda x: 1.05 if int(x) else 1.0)

capacity_map = {}
if capacity is not None and {"week", "capacity_cases"} <= set(capacity.columns):
    capacity_map = {int(row.week): int(row.capacity_cases) for row in capacity.itertuples(index=False)}
else:
    capacity_map = {int(week): int(group["capacity_cases"].iloc[0]) for week, group in future.groupby("week")}

week_rows = []
for week, group in future.groupby("week", sort=True):
    total_orders = int(group["orders_placed"].sum())
    cap = int(capacity_map[int(week)])
    week_rows.append({
        "week": int(week),
        "capacity_cases": cap,
        "total_orders": total_orders,
        "capacity_gap": cap - total_orders,
    })

top_rows = []
for row in future.sort_values(
    ["score_per_case", "priority_weight", "promo_flag", "orders_placed"],
    ascending=[False, False, False, True],
).head(8).itertuples(index=False):
    top_rows.append({
        "week": int(row.week),
        "sku": row.sku,
        "retailer": row.retailer,
        "orders_placed": int(row.orders_placed),
        "promo_flag": int(row.promo_flag),
        "priority_weight": round(float(row.priority_weight), 6),
        "score_per_case": round(float(row.score_per_case), 6),
    })

recent_fill = None
if train is not None and {"orders_placed", "shipments"} <= set(train.columns):
    denom = train["orders_placed"].replace({0: pd.NA})
    ratio = (train["shipments"] / denom).dropna()
    if not ratio.empty:
        recent_fill = round(float(ratio.tail(min(96, len(ratio))).mean()), 4)

payload = {
    "scenario_name": scenario.get("scenario_name") or scenario.get("name"),
    "weeks": week_rows,
    "recent_historical_fill_rate": recent_fill,
    "recommended_strategy": "score_aligned_greedy",
    "strategy_note": "Prioritize rows by (revenue_weight * priority_multiplier) / orders_placed, then fill within weekly capacity.",
    "top_priority_rows": top_rows,
}
print(json.dumps(payload, indent=2))
"""
        return await _exec_python(script)

    @function_tool
    async def build_allocation_plan(strategy: str = "score_aligned_greedy") -> str:
        """Build /app/output/allocation_plan.json using a score-aligned weekly capacity heuristic."""
        script = f"""
import json
from pathlib import Path
import pandas as pd

base = Path("/task/environment/files")
future = pd.read_csv(base / "future_orders.csv").copy()
capacity_path = base / "capacity_schedule.csv"
capacity = pd.read_csv(capacity_path) if capacity_path.exists() else None

future["_row_id"] = range(len(future))
future["priority_weight"] = future["revenue_weight"].fillna(0) * future["priority_multiplier"].fillna(1)
future["score_per_case"] = future["priority_weight"] / future["orders_placed"].clip(lower=1)
future["score_per_case"] = future["score_per_case"] * future["promo_flag"].map(lambda x: 1.05 if int(x) else 1.0)

if capacity is not None and {{"week", "capacity_cases"}} <= set(capacity.columns):
    capacity_map = {{int(row.week): int(row.capacity_cases) for row in capacity.itertuples(index=False)}}
else:
    capacity_map = {{int(week): int(group["capacity_cases"].iloc[0]) for week, group in future.groupby("week")}}

allocations = []
week_summary = []

for week, group in future.groupby("week", sort=True):
    group = group.copy()
    week_int = int(week)
    capacity_cases = int(capacity_map[week_int])
    total_orders = int(group["orders_placed"].sum())

    if total_orders <= capacity_cases:
        group["recommended_qty"] = group["orders_placed"].astype(int)
    else:
        if "{strategy}" == "weighted_proportional":
            weights = (group["priority_weight"] * group["orders_placed"]).astype(float)
            if float(weights.sum()) <= 0:
                weights = group["orders_placed"].astype(float)
            target = capacity_cases * weights / float(weights.sum())
            base_alloc = target.clip(upper=group["orders_placed"]).fillna(0).astype(int)
            remaining = capacity_cases - int(base_alloc.sum())
            group["recommended_qty"] = base_alloc
            if remaining > 0:
                remainder = (target - base_alloc).fillna(0)
                order = group.assign(_remainder=remainder).sort_values(
                    ["_remainder", "priority_weight", "promo_flag", "orders_placed"],
                    ascending=[False, False, False, True],
                )
                for idx in order.index:
                    if remaining <= 0:
                        break
                    spare = int(group.at[idx, "orders_placed"] - group.at[idx, "recommended_qty"])
                    if spare <= 0:
                        continue
                    give = min(spare, remaining)
                    group.at[idx, "recommended_qty"] += give
                    remaining -= give
        else:
            group = group.sort_values(
                ["score_per_case", "priority_weight", "promo_flag", "orders_placed"],
                ascending=[False, False, False, True],
            )
            remaining = capacity_cases
            recs = []
            for row in group.itertuples(index=False):
                qty = min(int(row.orders_placed), remaining)
                recs.append(qty)
                remaining -= qty
            group["recommended_qty"] = recs

    week_summary.append({{
        "week": week_int,
        "capacity_cases": capacity_cases,
        "total_orders": total_orders,
        "allocated_cases": int(group["recommended_qty"].sum()),
    }})
    allocations.append(group)

plan_df = pd.concat(allocations, ignore_index=True).sort_values("_row_id")
plan = [
    {{
        "week": int(row.week),
        "sku": row.sku,
        "retailer": row.retailer,
        "recommended_qty": int(row.recommended_qty),
    }}
    for row in plan_df.itertuples(index=False)
]

out_path = Path("/app/output/allocation_plan.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(plan, indent=2))

summary = {{
    "strategy": "{strategy}",
    "rows_written": len(plan),
    "output_path": str(out_path),
    "week_summary": week_summary,
}}
print(json.dumps(summary, indent=2))
"""
        return await _exec_python(script)

    @function_tool
    async def validate_allocation_plan() -> str:
        """Validate /app/output/allocation_plan.json against visible rows and weekly capacity."""
        script = r"""
import json
from pathlib import Path
import pandas as pd

base = Path("/task/environment/files")
future = pd.read_csv(base / "future_orders.csv").copy()
capacity_path = base / "capacity_schedule.csv"
capacity = pd.read_csv(capacity_path) if capacity_path.exists() else None

payload = {
    "valid": False,
    "errors": [],
    "weekly_totals": {},
    "row_count": 0,
}

plan_path = Path("/app/output/allocation_plan.json")
if not plan_path.exists():
    payload["errors"].append("allocation_plan.json does not exist")
    print(json.dumps(payload, indent=2))
    raise SystemExit(0)

try:
    plan = json.loads(plan_path.read_text())
except Exception as exc:
    payload["errors"].append(f"invalid JSON: {exc}")
    print(json.dumps(payload, indent=2))
    raise SystemExit(0)

if not isinstance(plan, list):
    payload["errors"].append("output is not a JSON array")
    print(json.dumps(payload, indent=2))
    raise SystemExit(0)

plan_df = pd.DataFrame(plan)
payload["row_count"] = int(len(plan_df))
required_cols = {"week", "sku", "retailer", "recommended_qty"}
missing_cols = sorted(required_cols - set(plan_df.columns))
if missing_cols:
    payload["errors"].append(f"missing columns: {missing_cols}")
    print(json.dumps(payload, indent=2))
    raise SystemExit(0)

expected = future[["week", "sku", "retailer"]].copy()
expected["_key"] = expected.astype(str).agg("|".join, axis=1)
plan_df["_key"] = plan_df[["week", "sku", "retailer"]].astype(str).agg("|".join, axis=1)

missing_rows = sorted(set(expected["_key"]) - set(plan_df["_key"]))
extra_rows = sorted(set(plan_df["_key"]) - set(expected["_key"]))
duplicate_count = int(plan_df["_key"].duplicated().sum())
negative_count = int((pd.to_numeric(plan_df["recommended_qty"], errors="coerce").fillna(-1) < 0).sum())

if missing_rows:
    payload["errors"].append(f"missing rows: {len(missing_rows)}")
if extra_rows:
    payload["errors"].append(f"extra rows: {len(extra_rows)}")
if duplicate_count:
    payload["errors"].append(f"duplicate rows: {duplicate_count}")
if negative_count:
    payload["errors"].append(f"negative or invalid recommended_qty rows: {negative_count}")

if capacity is not None and {"week", "capacity_cases"} <= set(capacity.columns):
    capacity_map = {int(row.week): int(row.capacity_cases) for row in capacity.itertuples(index=False)}
else:
    capacity_map = {int(week): int(group["capacity_cases"].iloc[0]) for week, group in future.groupby("week")}

weekly = (
    plan_df.groupby("week", dropna=False)["recommended_qty"]
    .sum()
    .to_dict()
)
for week, total in weekly.items():
    week_int = int(week)
    total_int = int(total)
    limit = int(capacity_map.get(week_int, 0))
    payload["weekly_totals"][str(week_int)] = {
        "allocated_cases": total_int,
        "capacity_cases": limit,
        "within_capacity": total_int <= limit,
    }
    if total_int > limit:
        payload["errors"].append(f"week {week_int} exceeds capacity: {total_int} > {limit}")

payload["valid"] = not payload["errors"]
print(json.dumps(payload, indent=2))
"""
        return await _exec_python(script)

    return [summarize_inputs, build_allocation_plan, validate_allocation_plan, run_shell]


def create_agent(environment: BaseEnvironment) -> Agent:
    """Build the agent. Modify to add handoffs, sub-agents, or agent-as-tool."""
    tools = create_tools(environment)
    model_settings = create_model_settings()
    model = create_model()
    return Agent(
        name="supply-chain-autoagent",
        instructions=SYSTEM_PROMPT,
        tools=tools,
        model=model,
        model_settings=model_settings,
    )


async def run_task(
    environment: BaseEnvironment,
    instruction: str,
) -> tuple[object, int]:
    """Run the agent on a task and return (result, duration_ms)."""
    agent = create_agent(environment)
    t0 = time.time()
    result = await Runner.run(agent, input=instruction, max_turns=MAX_TURNS)
    duration_ms = int((time.time() - t0) * 1000)
    return result, duration_ms


# ============================================================================
# FIXED ADAPTER BOUNDARY: do not modify unless the human explicitly asks.
# Harbor integration and trajectory serialization live here.
# ============================================================================

def to_atif(result: object, model: str, duration_ms: int = 0) -> dict:
    """Convert OpenAI Agents SDK RunResult to an ATIF trajectory dict."""
    steps: list[dict] = []
    step_id = 0
    now = datetime.now(timezone.utc).isoformat()

    def _step(source: str, message: str, **extra: object) -> dict:
        nonlocal step_id
        step_id += 1
        step = {
            "step_id": step_id,
            "timestamp": now,
            "source": source,
            "message": message,
        }
        step.update({key: value for key, value in extra.items() if value is not None})
        return step

    pending_tool_call = None
    for item in result.new_items:
        if isinstance(item, MessageOutputItem):
            text = ItemHelpers.text_message_output(item)
            if text:
                steps.append(_step("agent", text, model_name=model))
        elif isinstance(item, ReasoningItem):
            summaries = getattr(item.raw_item, "summary", None)
            reasoning = (
                "\n".join(s.text for s in summaries if hasattr(s, "text"))
                if summaries
                else None
            )
            if reasoning:
                steps.append(
                    _step(
                        "agent",
                        "(thinking)",
                        reasoning_content=reasoning,
                        model_name=model,
                    )
                )
        elif isinstance(item, ToolCallItem):
            raw = item.raw_item
            if hasattr(raw, "name"):
                pending_tool_call = raw
        elif isinstance(item, ToolCallOutputItem) and pending_tool_call:
            arguments = (
                json.loads(pending_tool_call.arguments)
                if isinstance(pending_tool_call.arguments, str)
                else pending_tool_call.arguments
            )
            output_str = str(item.output) if item.output else ""
            steps.append(
                _step(
                    "agent",
                    f"Tool: {pending_tool_call.name}",
                    tool_calls=[
                        {
                            "tool_call_id": pending_tool_call.call_id,
                            "function_name": pending_tool_call.name,
                            "arguments": arguments,
                        }
                    ],
                    observation={
                        "results": [
                            {
                                "source_call_id": pending_tool_call.call_id,
                                "content": output_str,
                            }
                        ]
                    },
                )
            )
            pending_tool_call = None

    if pending_tool_call:
        arguments = (
            json.loads(pending_tool_call.arguments)
            if isinstance(pending_tool_call.arguments, str)
            else pending_tool_call.arguments
        )
        steps.append(
            _step(
                "agent",
                f"Tool: {pending_tool_call.name}",
                tool_calls=[
                    {
                        "tool_call_id": pending_tool_call.call_id,
                        "function_name": pending_tool_call.name,
                        "arguments": arguments,
                    }
                ],
            )
        )

    if not steps:
        steps.append(_step("user", "(empty)"))

    usage = Usage()
    for response in result.raw_responses:
        usage.add(response.usage)

    return {
        "schema_version": "ATIF-v1.6",
        "session_id": getattr(result, "last_response_id", None) or "unknown",
        "agent": {"name": "autoagent", "version": "0.1.0", "model_name": model},
        "steps": steps,
        "final_metrics": {
            "total_prompt_tokens": usage.input_tokens,
            "total_completion_tokens": usage.output_tokens,
            "total_cached_tokens": getattr(usage.input_tokens_details, "cached_tokens", 0) or 0,
            "total_cost_usd": None,
            "total_steps": len(steps),
            "extra": {"duration_ms": duration_ms, "num_turns": len(result.raw_responses)},
        },
    }


class AutoAgent(BaseAgent):
    """Harbor agent adapter. Runs the OpenAI agent host-side and proxies shell into the container."""

    SUPPORTS_ATIF = True

    def __init__(self, *args, extra_env: dict[str, str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._extra_env = dict(extra_env) if extra_env else {}

    @staticmethod
    def name() -> str:
        return "autoagent"

    def version(self) -> str | None:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        pass

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        await environment.exec(command="mkdir -p /task /app/output")
        instr_file = self.logs_dir / "instruction.md"
        instr_file.write_text(instruction)
        await environment.upload_file(source_path=instr_file, target_path="/task/instruction.md")

        result, duration_ms = await run_task(environment, instruction)

        resolved_model = get_model_profile()
        atif = to_atif(result, model=resolved_model, duration_ms=duration_ms)
        traj_path = self.logs_dir / "trajectory.json"
        traj_path.write_text(json.dumps(atif, indent=2))

        try:
            final_metrics = atif.get("final_metrics", {})
            context.n_input_tokens = final_metrics.get("total_prompt_tokens", 0)
            context.n_output_tokens = final_metrics.get("total_completion_tokens", 0)
            context.n_cache_tokens = final_metrics.get("total_cached_tokens", 0)
        except Exception:
            pass

        usage = Usage()
        for response in result.raw_responses:
            usage.add(response.usage)
        print(
            f"model_profile={resolved_model} turns={len(result.raw_responses)} duration_ms={duration_ms} "
            f"input={usage.input_tokens} output={usage.output_tokens}"
        )


__all__ = ["AutoAgent"]

