# Supply Chain AutoAgent

AutoAgent-style autonomous harness engineering for the order-cut optimisation PoC described in `docs/`.

This repo adapts the structure of `kevinrgu/autoagent` to a supply-chain benchmark:

- human edits `program.md`
- meta-agent edits `agent.py`
- Harbor runs task containers under `tasks/`
- each task verifier writes a score to `/logs/verifier/reward.txt`

## Current benchmark

Use case: **Seasonal Peak Allocation / Order Cut Optimisation**

Goal: allocate constrained weekly supply across SKUs and retailers to maximize a commercially weighted fill-rate score, while respecting weekly capacity.

## Repo layout

```text
agent.py
program.md
Dockerfile.base
docs/
scripts/
  generate_benchmark.py
  heuristic_solver.py
tasks/
  order-cut-allocation-01/
  ...
```

## Quick start

Create a local `.env` from `.env.example` and choose either OpenAI mode or OpenRouter mode before real benchmark runs.

```bash
# 0. Configure environment
cp .env.example .env
# then edit .env and set OPENAI_API_KEY

# 1. Install deps
uv sync

# 2. Generate the synthetic benchmark suite
python scripts/generate_benchmark.py

# 3. Build the base image
docker build -f Dockerfile.base -t autoagent-base .

# 4. Run one task and auto-log the summary to results.tsv
python scripts/run_benchmark.py --task-name "supply-chain/order-cut-allocation-01" --limit 1 --concurrency 1 --status baseline --description "single-task smoke test"

# 5. Run the full suite and auto-log turns/tokens/cost to results.tsv
python scripts/run_benchmark.py --concurrency 20 --status baseline --description "full benchmark baseline"
```

`scripts/run_benchmark.py` wraps `harbor run`, captures the run log, parses task
scores plus ATIF trajectory metrics from `jobs/`, and appends one aggregate row
to `results.tsv`.

It also regenerates:

- `progress.png`
- `progress.svg`

after each logged run, so you have a blog/LinkedIn-friendly visual showing how
score evolves over time.


## Model provider modes

This harness now supports **both OpenAI and OpenRouter**.

### Option A - OpenAI

Use the default GPT-5.4 setup:

```env
MODEL_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.4
OPENAI_REASONING_EFFORT=high
```

### Option B - OpenRouter

Use any OpenRouter model slug supported by the OpenAI-compatible chat endpoint:

```env
MODEL_PROVIDER=openrouter
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=minimax/minimax-m2
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=https://github.com/kishorkukreja/sc-auto-research-order-cuts
OPENROUTER_APP_NAME=sc-auto-research-order-cuts
```

Examples you can test by changing `OPENROUTER_MODEL`:

- `minimax/minimax-m2`
- `minimax/minimax-m2.7`
- `z-ai/glm-5`
- `xiaomi/mimo-v2-pro`
- `google/gemma-4-31b-it`
- `nvidia/nemotron-3-super-120b-a12b:free`

The run logger will automatically record the provider/model profile into `results.tsv`, so you can compare cost and score across providers.

## Suggested comparison workflow

Run the same benchmark twice with different env settings:

```bash
# OpenAI baseline
python scripts/run_benchmark.py --concurrency 20 --status baseline --description "openai baseline"

# OpenRouter comparison
python scripts/run_benchmark.py --concurrency 20 --status run --description "openrouter minimax m2"
```

That will let you compare:

- score
- pass rate
- average turns
- token usage
- progress chart

## Output contract for the task agent

For each task, the agent must write:

`/app/output/allocation_plan.json`

Expected shape:

```json
[
  {"week": 13, "sku": "SKU_01", "retailer": "RET_A", "recommended_qty": 120}
]
```

The verifier is robust to missing rows and CSV fallback, but best practice is to emit every visible `(week, sku, retailer)` row exactly once.

## Local smoke test without Harbor

```bash
python scripts/generate_benchmark.py
python scripts/heuristic_solver.py tasks/order-cut-allocation-01/environment/files/future_orders.csv tasks/order-cut-allocation-01/environment/files/capacity_schedule.csv output/allocation_plan.json
```

Then run the verifier locally by pointing it at the generated file:

```bash
ALLOC_OUTPUT_PATH=output/allocation_plan.json \
HOLDOUT_PATH=tasks/order-cut-allocation-01/tests/holdout_actuals.csv \
REWARD_PATH=output/reward.txt \
python tasks/order-cut-allocation-01/tests/test.py
```

## Reference repos

- AutoAgent: https://github.com/kevinrgu/autoagent
- Harbor: https://github.com/laude-institute/harbor

