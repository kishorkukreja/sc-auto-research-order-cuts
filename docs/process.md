# Process / Workflow — Order Cut Optimisation PoC

> Derived from conversation on 2026-04-06.

---

## The Predict → Simulate → Optimize Loop

Trigger: Task agent receives an allocation task instruction
Owner: Task agent (harness defined in agent.py, autonomously improved by meta-agent)
Frequency: Once per benchmark task; repeated across iterations as meta-agent improves harness

### Steps

1. **Predict — Reconstruct True Demand**
   - Input: Order history (orders placed, not shipments), shipment actuals, cut log
   - Formula: `True Demand ≈ Orders Placed` (orders are less censored than sales)
   - Compute: `Fill Rate by period = Shipments / Orders Placed`
   - Identify: Weeks with significant cuts (fill rate < 1.0) and flag them
   - Apply: Seasonal index and promo uplift where promo calendar indicates

2. **Simulate — Run Allocation Scenarios**
   - Input: Reconstructed true demand, production capacity by week, retailer order intent
   - Run scenarios:
     - Proportional allocation (orders cut pro-rata across all retailers)
     - Velocity-weighted (protect high-velocity SKUs, cut slower movers first)
     - Key account protection (strategic accounts receive minimum guarantee)
   - For each scenario: compute `shipments[sku][retailer][week]` given capacity constraint
   - Compute: `weighted fill rate = sum(fill_rate * revenue_weight) / sum(revenue_weight)`

3. **Optimize — Select and Output Best Allocation**
   - Compare scenario fill rates
   - Select scenario maximising weighted fill rate subject to: total shipments ≤ capacity
   - Output: Allocation table (SKU × retailer × week → recommended qty) + expected fill rate per customer

### Decision Points

| If... | Then... |
|---|---|
| Orders placed for a week exceed production capacity | Cuts are necessary; choose allocation strategy |
| A retailer has a live promotion | Apply promo protection — cut non-promo SKUs first |
| A SKU is in high-velocity tier (top 20% revenue) | Protect fill rate for this SKU across all retailers |
| Total demand is below capacity | Fulfil all orders; no cut decision needed |

### Exceptions / Edge Cases

- **Promo collision:** Two retailers have concurrent promotions; prioritise by revenue × promo multiplier
- **Zero order history:** New retailer or new SKU; fall back to category average demand proxy
- **Capacity spike:** Production capacity drops mid-run (e.g. line shutdown); re-optimise remaining weeks

---

## The Meta-Agent Optimisation Loop

Trigger: Human writes `program.md` and initiates first benchmark run
Owner: Meta-agent (Claude or GPT-5)
Frequency: Continuous overnight; typically 6-15 iterations in 8 hours

### Steps

1. Read `program.md` (human directive, success criteria, domain context)
2. Read current `agent.py` (baseline or last committed harness)
3. Read sample task instructions from `tasks/` to understand the domain
4. Run full benchmark: `harbor run -p tasks/ -n 100 ...`
5. Collect scores from `results.tsv`; compute `passed` count and `avg_score`
6. Read task traces: identify which tasks failed, where the agent's reasoning broke down
7. Diagnose failure mode (e.g. agent failed to decompose problem into predict/simulate/optimize; arithmetic errors in fill rate; ignored promo flag)
8. Propose harness change: edit SYSTEM_PROMPT, add a tool, modify orchestration logic
9. Spot-check: run isolated tasks affected by the change (faster than full suite)
10. Gate: if spot-check score improves, run full suite; else discard and try different change
11. Commit if full suite score improves; log to `results.tsv`; update `learnings.md`
12. Repeat from step 5

### Decision Points

| If... | Then... |
|---|---|
| Score improves after harness change | Commit change to agent.py, log to results.tsv |
| Score is flat or decreases | Discard change, try different diagnosis |
| Same failure mode appears in 3+ iterations | Log to learnings.md, escalate to human via flag in program.md |
| Simpler harness achieves same score | Keep the simpler version (complexity is penalised) |

### Exceptions / Edge Cases

- **First run must be unmodified baseline:** Do not attempt any improvement until iteration 0 score is logged
- **Model constraint:** Do not change the LLM model unless human explicitly changes the constraint in program.md
- **Fixed adapter boundary:** Section of agent.py below the boundary comment must not be modified under any circumstances

---

## Day 1 / Day 2 Build Process (Human Workflow)

Trigger: PoC build initiated
Owner: Kish / Coefficient Advisory
Timeframe: 48 hours

### Day 1 Steps

1. Fork `github.com/kevinrgu/autoagent`
2. Generate synthetic dataset: `data/seasonal_peak_sample.csv` (12 SKUs × 4 retailers × 16 weeks, with deliberate cut events at weeks 4, 8, and promo in week 5)
3. Write `tasks/order-cut-allocation/instruction.md` — task agent receives data + constraints
4. Write `tasks/order-cut-allocation/tests/test.py` — weighted fill rate verifier, writes to `/logs/reward.txt`
5. Write `program.md` — meta-agent directive
6. Build Docker base image: `docker build -f Dockerfile.base -t autoagent-base .`
7. Run iteration 0 (baseline): confirm the loop completes and a score is written
8. Kick off overnight run: `harbor run -p tasks/ -n 100 ...`

### Day 2 Steps

1. Morning: read `results.tsv`; pull 3 best iterations; inspect `agent.py` diffs to see what meta-agent changed
2. Identify the single biggest harness improvement (usually: decomposing prompt into steps, or adding a calculation tool)
3. Build client-facing comparison: baseline fill rate vs best iteration fill rate, with iteration log as evidence
4. Prepare demo narrative: show `results.tsv` progression, show the harness diff, show the allocation output

### Exceptions / Edge Cases

- **Overnight run fails silently:** Check `run.log`; most common cause is Docker build failure or missing API key in `.env`
- **Score doesn't improve:** Lower the difficulty of the task suite (fewer SKUs, cleaner capacity constraint); confirm baseline produces reasonable output first
- **Client asks about production readiness:** Frame as "proof of mechanism" — the loop is real, the improvement is measured, productionising requires data integration and UI work
