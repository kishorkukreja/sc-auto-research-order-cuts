# Technical Details — Order Cut Optimisation Autoagent PoC

> Derived from conversation on 2026-04-06.

## Stack

| Layer | Technology | Version / Notes |
|---|---|---|
| Task runner | Harbor | pip installable; runs Docker tasks in parallel |
| Agent framework | OpenAI Agents SDK | `openai-agents` package; supports tool use + multi-agent handoffs |
| Container runtime | Docker | Dockerfile.base provided by autoagent repo |
| Package manager | uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Language | Python | >= 3.12 required |
| Data manipulation | pandas, numpy, openpyxl | Listed in pyproject.toml |
| LLM (meta-agent) | Claude Sonnet 4.6 or GPT-5 | Same-family pairing recommended; default in repo is GPT-5 |
| LLM (task agent) | Same as meta-agent | Set via MODEL in agent.py SYSTEM_PROMPT config section |
| Source repo | github.com/kevinrgu/autoagent | MIT licence; fork this |
| Reference only | github.com/neosigmaai/auto-harness | tau-bench specific; not used in this PoC |

## Key Technical Decisions

### Decision: autoagent over auto-harness
- Decision: Use kevinrgu/autoagent as the base, not neosigmaai/auto-harness
- Rationale: auto-harness is coupled to tau-bench (retail/airline customer service domain). autoagent is domain-agnostic — any task with a Harbor-format verifier works
- Alternatives considered: auto-harness, building from scratch
- Trade-offs: autoagent is days old, minimal documentation; but the mechanism is well-defined and the loop is verifiably real

### Decision: Orders placed as true demand proxy (not sales)
- Decision: Use `orders_placed` as the uncensored demand signal; do not use `sales` or `shipments`
- Rationale: Sales are censored by cuts — if 1,000 units were ordered but only 600 shipped, sales shows 600 and permanently undercounts demand. Orders placed is the retailer's actual intent before cuts are applied
- Alternatives considered: Using sell-through data (unavailable at PoC stage), econometric demand reconstruction
- Trade-offs: Orders placed may include speculative ordering (retailer safety stock inflation); acceptable at PoC fidelity level

### Decision: Weighted fill rate as optimisation metric and agent score
- Decision: `score = sum(fill_rate[sku][retailer][wk] * revenue_weight[sku]) / sum(revenue_weight)`
- Rationale: Unweighted fill rate treats a low-revenue SKU equally to a high-revenue one; weighting by revenue aligns the agent's optimisation to commercial priorities
- Alternatives considered: Unit fill rate (unweighted), service level agreement pass/fail
- Trade-offs: Revenue weights must be defined in synthetic data; at PoC stage these are assumed/synthetic

### Decision: Synthetic dataset (no client data)
- Decision: Generate `seasonal_peak_sample.csv` synthetically for PoC
- Rationale: No client data available at 48-hour PoC stage; synthetic data allows full control over cut events, capacity constraints, and promo calendar
- Alternatives considered: M5 Walmart dataset (demand forecasting, not allocation-centric), client data under NDA
- Trade-offs: Synthetic data reduces credibility of raw numbers but does not affect the validity of the mechanism demonstration

## Code / Config Snippets

### Install and run
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/kevinrgu/autoagent
cd autoagent
uv sync

# Set environment variables
cat > .env << 'EOF'
OPENAI_API_KEY=...
# or ANTHROPIC_API_KEY=... if using Claude
EOF

# Build base Docker image
docker build -f Dockerfile.base -t autoagent-base .

# Run single task (spot-check)
uv run harbor run -p tasks/ --task-name "order-cut-allocation" \
  -l 1 -n 1 --agent-import-path agent:AutoAgent \
  -o jobs --job-name latest > run.log 2>&1

# Run full benchmark (overnight)
rm -rf jobs; mkdir -p jobs && \
  uv run harbor run -p tasks/ -n 100 \
  --agent-import-path agent:AutoAgent \
  -o jobs --job-name latest > run.log 2>&1
```

### Weighted fill rate verifier (test.py skeleton)
```python
import json, sys, pathlib
import pandas as pd
import numpy as np

# Paths
HOLDOUT_PATH = pathlib.Path("/task/environment/files/holdout_actuals.csv")
LOG_PATH = pathlib.Path("/logs/reward.txt")

def compute_score(agent_output: str) -> float:
    # Parse agent allocation table from stdout
    # Expected format: CSV or JSON with columns: sku, retailer, week, recommended_qty
    try:
        allocation = pd.read_json(agent_output)
    except Exception:
        return 0.0

    holdout = pd.read_csv(HOLDOUT_PATH)
    # holdout columns: sku, retailer, week, true_demand, available_supply, revenue_weight

    merged = allocation.merge(holdout, on=["sku", "retailer", "week"])
    merged["shipped"] = merged.apply(
        lambda r: min(r["recommended_qty"], r["available_supply"]), axis=1
    )
    merged["fill_rate"] = merged["shipped"] / merged["true_demand"].clip(lower=0.001)
    merged["weighted_fill"] = merged["fill_rate"] * merged["revenue_weight"]

    score = merged["weighted_fill"].sum() / merged["revenue_weight"].sum()
    return float(np.clip(score, 0.0, 1.0))

if __name__ == "__main__":
    agent_output = sys.stdin.read()
    score = compute_score(agent_output)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(str(score))
    print(f"Score: {score:.4f}")
```

### Demand reconstruction formula
```python
# True demand = orders placed (less censored than shipments)
# Fill rate = shipments / orders_placed
# Pent-up demand = orders_placed - shipments (partially carries forward)

df["true_demand"] = df["orders_placed"]
df["fill_rate"] = df["shipments"] / df["orders_placed"].clip(lower=0.001)
df["pent_up"] = df["orders_placed"] - df["shipments"]
```

### Synthetic dataset columns (seasonal_peak_sample.csv)
```
week          int   1-16
sku           str   SKU_01 to SKU_12
retailer      str   RET_A to RET_D
orders_placed int   retailer's intended order quantity
shipments     int   actual units shipped (orders_placed × fill_rate_applied)
fill_rate     float historical fill rate (1.0 = no cut; < 1.0 = cut occurred)
promo_flag    bool  1 if this SKU/retailer/week has a promotion
revenue_per_case float used to compute revenue_weight for verifier
capacity      int   total production capacity available for this week (shared across all SKUs/retailers)
```

## APIs & Schemas

### Harbor task format (tasks/order-cut-allocation/)
```
task.toml           # [task] name, timeout_seconds, metadata
instruction.md      # prompt delivered to task agent; references data in /task/environment/files/
tests/
  test.sh           # #!/bin/bash; python tests/test.py < /task/agent_output.txt
  test.py           # verifier; writes float to /logs/reward.txt
environment/
  Dockerfile        # FROM autoagent-base; COPY files/ /task/environment/files/
  files/
    train_data.csv        # 12 weeks of history visible to agent
    holdout_actuals.csv   # weeks 13-16 actuals; mounted but not in instruction
    capacity_schedule.csv # production capacity by week
    promo_calendar.csv    # promotional events by retailer × SKU × week
```

### results.tsv columns
```
iteration   int     iteration number (0 = baseline)
val_score   float   weighted fill rate score on validation set
passed      int     number of tasks meeting threshold
avg_score   float   mean score across all tasks
commit      str     git commit hash of agent.py at this iteration
timestamp   str     ISO datetime of run completion
notes       str     meta-agent's self-logged diagnosis
```

## Known Constraints

- autoagent repo is days old; no production reliability guarantees
- Benchmark scores claimed by creator (96.5% SpreadsheetBench) not yet verified on official leaderboards
- Task suite size directly affects overnight iteration count: more tasks = fewer iterations per 8 hours
- `test.py` must handle malformed agent output gracefully (return 0.0, not crash) or Harbor will error
- Docker required; adds friction if client environment doesn't run containers
- OpenAI Agents SDK required even if using Claude as the LLM (adapter layer handles this)
