# Autoagent Supply Chain PoC — Archive

**Exported:** 2026-04-06
**Scope:** Full conversation — from initial repo discovery through problem framing, use case selection, and detailed design of Order Cut optimisation PoC

---

## 1. Origin

Kish identified two freshly released GitHub repos:
- `neosigmaai/auto-harness` — tau-bench-based autonomous agent optimisation harness
- `kevinrgu/autoagent` — general-purpose autonomous harness engineering (ThirdLayer / YC W25)

Goal: build a repo of their own for automated optimisation of a supply chain use case, demonstrating measurable improvement to a client within 2 days.

Starting question: how does the loop work, what problem should we pick, where does data come from?

---

## 2. Context & Constraints

**Client context:**
- Coefficient Advisory client demo — supply chain / CPG domain
- Audience likely: S&OP leads, supply planning managers at PepsiCo / L'Oréal / Unilever tier
- 2-day hard deadline to show working PoC

**Technical constraints:**
- Must use autoagent framework (kevinrgu fork — more general, Docker-sandboxed, domain-agnostic)
- Eval/verifier must produce a numeric score 0.0–1.0 written to `/logs/reward.txt`
- Data must be either public or synthetic — no client data at PoC stage
- Stack: Python, Docker, Harbor task runner, OpenAI Agents SDK

**Key assumptions stated:**
- Demand ≠ Sales — sales data is censored by order cuts; true demand must be reconstructed
- Shipment-to-demand ratio is the correct service level anchor, not fill rate against sales
- Pent-up demand compounds: a cut during a peak or launch doesn't just lose the sale, it corrupts the demand signal for future planning cycles

---

## 3. Evolution

**Turn 1 — Repo understanding**
Both repos decoded. auto-harness is tau-bench specific (retail/airline). autoagent is the right base — domain-agnostic, tasks defined via `instruction.md` + `test.py`, meta-agent edits `agent.py`, human only writes `program.md`. Three-file architecture confirmed.

**Turn 2 — Problem shortlist**
Three options were presented:
1. Demand forecast refinement (M5 Walmart dataset) — WAPE metric, cleanest setup
2. Supply exception classification — synthetic data, LLM-as-judge
3. Order quantity recommendation — demand + inventory + lead time → replenishment qty

**Turn 3 — Problem reframe (Kish)**
Kish rejected generic replenishment framing. Reframed to:
- **Order cuts specifically** — more commercially relevant, directly tied to inventory and production quantities
- Must account for pent-up demand
- Must use shipment-to-demand ratios, not demand vs sales
- Must be a predict → simulate → optimize loop, not just a forecasting task
- Requested 2 grounded use cases

**Turn 4 — Full use case design**
Two use cases produced:

**UC1: Seasonal Peak Allocation (Ice Cream / Beverages)**
- Production capacity constrained, multiple retailer customers, cuts inevitable
- Predict: reconstruct true demand from censored sales + cut log (`True Demand ≈ Sales / Fill Rate`)
- Simulate: run allocation scenarios (proportional vs velocity-weighted vs key account protection)
- Optimize: maximise weighted fill rate subject to production capacity
- Verifier: `score = weighted fill rate achieved / max possible fill rate`

**UC2: New Product Launch — Promotional Build Quantity**
- Single production run, no sales history, analogue-based demand estimation
- Predict: scale analogue launch curves + promo uplift + Monte Carlo uncertainty
- Simulate: 4 production quantity options (70k/85k/100k/120k cases) × probabilistic demand
- Optimize: maximise `expected revenue - expected write-off cost`
- Verifier: `score = net_value(agent_qty) / net_value(optimal_qty)`

**Current direction at archive:** UC1 (Seasonal Peak Allocation) confirmed as the one to build first — faster to scaffold, cleaner verifier, more familiar territory for CPG clients.

---

## 4. Decisions & Outputs

**D1: Use autoagent (kevinrgu), not auto-harness (neosigmaai)**
- Rationale: auto-harness is tau-bench specific. autoagent is domain-agnostic, Harbor-based, same meta-agent loop
- Status: Decided

**D2: Problem = Order Cut Optimisation, not generic replenishment**
- Rationale: more commercially sharp, demand ≠ sales distinction makes it credible to CPG S&OP audience
- Status: Decided

**D3: UC1 (Seasonal Peak) first for 2-day PoC**
- Rationale: synthetic data controllable, verifier is deterministic, client story is immediate
- Status: Decided

**D4: Metric = weighted fill rate (shipment / true demand), weighted by SKU revenue**
- Rationale: shipment/sales ratio hides cuts. shipment/order is the correct uncensored signal
- Status: Decided

**D5: Frame to client as "proof of mechanism" not production system**
- Rationale: autoagent repo is days old, benchmark claims not yet verified on official leaderboards
- Status: Decided

**Repo structure agreed:**
```
supply-chain-autoagent/
├── program.md
├── agent.py
├── tasks/
│   └── order-cut-allocation/
│       ├── task.toml
│       ├── instruction.md
│       └── tests/
│           ├── test.sh
│           └── test.py          # computes weighted fill rate, writes score
├── data/
│   └── seasonal_peak_sample.csv # synthetic: 12 SKUs, 4 retailers, 16 weeks + cut log
└── results.tsv
```

**Key verifier logic (UC1):**
```python
# true_demand[sku][week] = orders_placed (not shipments)
# fill_rate[sku][retailer][week] = min(agent_allocation, available_supply) / true_demand
# weighted_fill_rate = sum(fill_rate * sku_revenue_weight)
# score = weighted_fill_rate (0.0 to 1.0)
# write score to /logs/reward.txt
```

**Key instruction.md inputs agreed:**
- 16 weeks order history + shipment actuals for 12 SKUs × 4 retail customers
- Production capacity: 8,500 cases/wk (wks 1-4), 10,000 cases/wk (wks 5-8)
- Cut log (orders placed vs fulfilled)
- Promo calendar (retailer A: 3-week promo starting wk 5)
- Agent output: allocation table + expected fill rate per customer

---

## 5. Current State

**Completed:**
- Both repos understood and evaluated
- Problem statement selected and refined (order cuts, not generic replenishment)
- Two full use cases designed with predict/simulate/optimize loops
- Repo structure agreed
- Verifier logic designed
- Client narrative agreed ("30-second allocation vs 2-day political process")

**In progress / next immediate step:**
- Build the actual repo scaffold: `program.md`, `task.toml`, `instruction.md`, `test.py` for UC1
- Generate synthetic `seasonal_peak_sample.csv` (12 SKUs × 4 retailers × 16 weeks, with deliberate cut events)
- Run baseline (iteration 0) to confirm the loop works before leaving overnight

**Not yet started:**
- UC2 (NPL build quantity) — designed but not scaffolded

---

## 6. Open Items

- [ ] Write `program.md` — meta-agent directive for order cut optimisation
- [ ] Write `instruction.md` template — what the task agent receives per task
- [ ] Write `test.py` — weighted fill rate verifier
- [ ] Generate synthetic dataset — synthetic peak allocation scenario with realistic cut events
- [ ] Confirm Docker + Harbor setup works locally before running overnight
- [ ] Decide: use GPT-5 or Claude Sonnet 4.6 as meta-agent? (autoagent defaults to GPT-5; Claude empathy finding suggests same-family pairing may matter)
- [ ] Decide: how many tasks in the benchmark suite? (recommendation: 10-15 SKU/retailer/week combos with varying cut severity)
- [ ] UC2 scaffolding — deprioritised until UC1 baseline runs

---

## 7. Raw Context

**autoagent loop mechanics (verbatim from repo):**
```
program.md → meta-agent directive
agent.py   → task agent (meta-agent edits this, human never touches)
tasks/     → each task has instruction.md + tests/test.py
             test.py writes score 0.0-1.0 to /logs/reward.txt
results.tsv→ iteration history (val_score, commit, evals, timestamp)
```

**Harbor task format:**
```
tasks/my-task/
  task.toml         # config (timeouts, metadata)
  instruction.md    # prompt sent to the agent
  tests/
    test.sh         # entry point, calls test.py, writes /logs/reward.txt
    test.py         # verification (deterministic or LLM-as-judge)
  environment/
    Dockerfile      # FROM autoagent-base
    files/          # reference files mounted into container
```

**Install / run commands:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
docker build -f Dockerfile.base -t autoagent-base .
# single task:
uv run harbor run -p tasks/ --task-name "order-cut-allocation" -l 1 -n 1 \
  --agent-import-path agent:AutoAgent -o jobs --job-name latest
# all tasks:
uv run harbor run -p tasks/ -n 100 --agent-import-path agent:AutoAgent \
  -o jobs --job-name latest > run.log 2>&1
```

**Demand reconstruction formula:**
```
True Demand ≈ Orders Placed  (not shipments — orders are uncensored)
Fill Rate   = Shipments / Orders Placed
Pent-up Demand = Orders Placed - Shipments (carries forward partially)
```

**Weighted fill rate verifier formula:**
```python
score = sum(
    min(agent_qty[sku][retailer][wk], available[sku][wk]) / true_demand[sku][retailer][wk]
    * revenue_weight[sku]
    for sku, retailer, wk in all_combinations
) / sum(revenue_weight.values())
```

**Client narrative (use verbatim):**
> "Your S&OP team manually allocates order cuts today — it takes 2 days, it's political, and it's based on last year's sales not this year's demand. This agent does it in 30 seconds and it was autonomously optimised against your own cut history."

**Repo to fork:** `https://github.com/kevinrgu/autoagent`
**Reference only:** `https://github.com/neosigmaai/auto-harness` (tau-bench specific, not used)
