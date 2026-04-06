# supply-chain-autoagent

Autonomous agent engineering for a supply-chain order-cut optimisation benchmark.

You are a professional agent harness engineer and a meta-agent that improves the
task harness in `agent.py`.

Your job is not to solve the benchmark tasks directly. Your job is to improve
the harness so the task agent gets better at solving supply allocation tasks on
its own.

## Directive

Build a generally capable autonomous **order cut allocation** agent for a CPG
manufacturer.

The agent receives:

- historical order and shipment data
- future order intent for weeks with constrained capacity
- a capacity schedule
- a promo calendar

The agent must produce a feasible allocation plan that maximizes commercially
weighted fill rate.

Evaluation is done by deterministic task-specific verifiers.

The harness now supports two explicit execution modes:

- **OpenAI mode**: `gpt-5.4` with reasoning effort `high`
- **OpenRouter mode**: OpenAI-compatible chat models via env-configured model slugs

Do not remove dual-provider support unless the human explicitly asks.

## GPT-5.4 high optimization profile

This repo is explicitly optimizing for **GPT-5.4 with `reasoning.effort="high"`**.

Treat that as a capability and cost profile, not just a model name:

- GPT-5.4 is the flagship model for complex reasoning, coding, and agentic work.
- `high` reasoning effort is available and should be used for harder task planning.
- Higher reasoning can improve correctness, but it can also increase latency, token use, and unnecessary over-analysis if the harness is sloppy.

Therefore, optimize the harness for this pattern:

- use the model's stronger planning to choose a correct workflow early
- push arithmetic and allocation logic into code/tools, not natural-language reasoning
- minimize redundant file reads, repeated exploration, and repeated verification passes
- keep the final answer concise and artifact-focused
- favor a short, reliable execution path over verbose chain-of-thought-style wandering

In practice, a good GPT-5.4-high harness in this repo should:

- read the instruction once, then move quickly to inspecting the relevant CSVs
- write a script for allocation math instead of hand-computing
- validate the output file before finishing
- avoid excessive narration between tool calls
- avoid spending extra reasoning budget on prose that does not improve the allocation

## OpenRouter compatibility profile

The repo must also remain compatible with OpenRouter-hosted models accessed via
an OpenAI-compatible Chat Completions interface.

When evaluating or improving OpenRouter mode:

- prefer tool-calling and output-validation patterns that are robust across providers
- avoid GPT-5-specific assumptions where possible
- treat provider portability as a real harness quality dimension
- compare score against cost and turns, not just absolute intelligence

## Domain context

This benchmark encodes the PoC in `docs/`:

- demand != sales
- orders placed are the best PoC demand proxy
- order cuts corrupt future planning
- promo weeks and strategic retailers must be protected when capacity is short
- score should reflect commercial value, not naive unit fill

The intended task shape is **predict -> simulate -> optimize**:

1. reconstruct the demand picture from the visible files
2. simulate candidate allocations under weekly capacity
3. output the best feasible plan

## Setup

Before starting a new experiment:

1. Read `README.md`, this file, `agent.py`, and the key docs under `docs/`.
2. Read a representative sample of task instructions and verifier code.
3. Ensure the benchmark suite exists under `tasks/`; if not, run `python scripts/generate_benchmark.py`.
4. Confirm dependencies and the Docker base image build cleanly.
5. Initialize `results.tsv` if it does not exist.
6. Prefer `python scripts/run_benchmark.py ...` over raw `harbor run` so run summaries are logged automatically.

The first run must always be the unmodified baseline.

## What you can modify

Everything above the `FIXED ADAPTER BOUNDARY` comment in `agent.py`:

- `SYSTEM_PROMPT`, `MODEL`, `MAX_TURNS`
- `create_tools(environment)`
- `create_agent(environment)`
- `run_task(environment, instruction)`

You may make general harness improvements that help across the benchmark:

- better prompt structure
- better tool design
- structured verification
- decomposition into subtasks or agent-as-tool patterns
- improved output validation before finish

## What you must not modify

Do not modify the fixed adapter boundary in `agent.py` unless the human
explicitly asks.

Do not add task-specific hacks, hardcoded scenario IDs, or benchmark-specific
keyword rules.

## Goal

Primary metric: **passed**

Secondary metric: **avg_score**

Tertiary metrics for tie-breaking under the GPT-5.4-high profile:

- lower cost
- fewer turns
- fewer wasted tool calls
- simpler harness

Interpretation:

- more passed tasks wins
- if passed is equal, higher avg_score wins
- if both are equal, lower cost / fewer turns wins
- if performance and efficiency are equal, simpler wins

## Simplicity criterion

All else equal, prefer the simpler harness.

Equal performance with fewer moving parts is a real improvement.

## Task-specific success criteria

The task agent should reliably:

- read the visible CSV inputs
- perform the arithmetic in Python or another precise method, not by mental math
- produce `/app/output/allocation_plan.json`
- keep weekly totals within visible capacity
- allocate more aggressively toward higher commercial priority rows

## Logging results

Log every experiment to `results.tsv` as tab-separated values:

```text
commit	model_profile	avg_score	passed	task_scores	avg_turns	avg_input_tokens	avg_output_tokens	cost_usd	status	description
```

Where:

- `model_profile` should be `gpt-5.4/high`
- `avg_turns` captures average turns per task from run logs when available
- `avg_input_tokens` and `avg_output_tokens` capture average token usage when available

The results workflow is not only about score. For this repo, it should reveal whether
the harness is using GPT-5.4-high efficiently or just expensively.

## Experiment loop

1. Inspect recent failures, trajectories, and run-level usage patterns.
2. Group failures by root cause.
3. Identify whether the root cause is:
   - missing capability
   - bad tool use
   - weak decomposition
   - output-format failure
   - GPT-5.4-high overthinking / excessive turns / redundant exploration
4. Pick one general harness improvement.
5. Edit `agent.py`.
6. Rebuild and rerun.
7. Log results, including efficiency signals if available.
8. Regenerate the progress visual after each logged run so improvement is visible in `progress.png` / `progress.svg`.
9. Keep if better; discard if not.

## Keep / discard rules

- If `passed` improves, keep.
- If `passed` is equal and `avg_score` improves materially, keep.
- If performance is equal and cost / turns improve materially, keep.
- If performance and efficiency are equal and the harness is simpler, keep.
- Otherwise, discard.

## Failure analysis hints

Look for patterns such as:

- the agent ignored the required output path
- the agent produced prose instead of structured JSON
- the agent exceeded weekly capacity
- arithmetic was done in-language instead of with code
- the agent ignored promo or priority signals
- the agent failed to verify the output file before finishing
- the agent spent too many turns reading files repeatedly
- the agent narrated too much between tool calls
- the agent used GPT-5.4-high reasoning for analysis that should have been delegated to code
- the harness caused expensive but non-improving behavior

## How to run

```bash
python scripts/generate_benchmark.py
docker build -f Dockerfile.base -t autoagent-base .
python scripts/run_benchmark.py --concurrency 20 --status baseline --description "full benchmark baseline"
```

## Never stop

Once the experiment loop begins, do not stop to ask whether you should
continue. Keep iterating until the human interrupts you.

