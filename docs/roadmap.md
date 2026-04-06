# Roadmap — Order Cut Optimisation Autoagent PoC

> Derived from conversation on 2026-04-06.

## Summary Timeline

```
Day 1 Morning         Day 1 Afternoon       Day 1 Evening         Day 2 Morning         Day 2 Afternoon
+-------------------+ +-------------------+ +-------------------+ +-------------------+ +-------------------+
| Fork repo         | | Write verifier    | | Write program.md  | | Read results.tsv  | | Build client deck |
| Generate data     | | Write tasks/      | | Kick off overnight| | Inspect diffs     | | Demo narrative    |
| Confirm env runs  | | Confirm baseline  | | run               | | Identify key wins | | Present           |
+-------------------+ +-------------------+ +-------------------+ +-------------------+ +-------------------+
```

## Phases / Milestones

### Phase 1 — Environment Setup (Day 1 Morning, ~3 hours)
- Timeframe: Day 1, 09:00–12:00
- Goal: Working repo, synthetic data, Docker environment confirmed
- Key deliverables:
  - [ ] Fork `github.com/kevinrgu/autoagent`
  - [ ] Generate `data/seasonal_peak_sample.csv` — 12 SKUs × 4 retailers × 16 weeks, with cut events at weeks 4 and 8, promo in week 5
  - [ ] `.env` configured with API key
  - [ ] `docker build -f Dockerfile.base -t autoagent-base .` completes successfully
  - [ ] `uv sync` completes, no dependency errors
- Dependencies: Docker installed, API key available
- Risks: Docker build failure on first attempt (check uv and Python version requirements)

### Phase 2 — Task + Verifier Build (Day 1 Afternoon, ~4 hours)
- Timeframe: Day 1, 13:00–17:00
- Goal: Single working task with a verifier that scores correctly and writes to `/logs/reward.txt`
- Key deliverables:
  - [ ] `tasks/order-cut-allocation/task.toml`
  - [ ] `tasks/order-cut-allocation/instruction.md` — task agent receives 12-week data, capacity schedule, promo calendar
  - [ ] `tasks/order-cut-allocation/tests/test.py` — weighted fill rate verifier, handles malformed output gracefully
  - [ ] `tasks/order-cut-allocation/environment/Dockerfile` — mounts synthetic data files
  - [ ] Iteration 0 baseline run completes — score is logged to `results.tsv`
- Dependencies: Phase 1 complete
- Risks: Agent produces malformed output on first run — verifier must return 0.0 not crash; test with known-bad input first

### Phase 3 — program.md + Overnight Run (Day 1 Evening)
- Timeframe: Day 1, 17:00–18:00 setup; run overnight
- Goal: Meta-agent directive written and overnight optimisation run initiated
- Key deliverables:
  - [ ] `program.md` written — domain context (CPG seasonal peak), success criteria (weighted fill rate > 0.80), harness guidance (decompose into predict/simulate/optimize steps)
  - [ ] Overnight run initiated: `harbor run -p tasks/ -n 100 ...`
  - [ ] `run.log` monitored for first 30 minutes to confirm iterations are progressing
- Dependencies: Phase 2 complete, baseline score confirmed
- Risks: Run stalls overnight — check API rate limits; reduce concurrency if needed

### Phase 4 — Results Analysis + Client Package (Day 2 Morning, ~3 hours)
- Timeframe: Day 2, 09:00–12:00
- Goal: Extract improvement story from results, identify what the meta-agent changed
- Key deliverables:
  - [ ] `results.tsv` reviewed — identify best iteration score vs baseline
  - [ ] Top 3 `agent.py` diffs inspected — what did the meta-agent change (prompt decomposition? new tool? routing logic?)
  - [ ] Before/after allocation table produced: baseline allocation vs optimised allocation for the peak week scenario
  - [ ] Score progression chart: iteration 0 → best iteration
- Dependencies: Overnight run completed with at least 5 iterations
- Risks: Score doesn't improve — fallback: show the loop working + diagnose why (probably agent output format mismatch)

### Phase 5 — Client Demo (Day 2 Afternoon)
- Timeframe: Day 2, 13:00–15:00 preparation; 15:00+ demo
- Goal: Present proof of mechanism to client with clear before/after story
- Key deliverables:
  - [ ] Demo narrative: "2-day political process → 30-second autonomous allocation"
  - [ ] `results.tsv` progression shown as evidence of autonomous improvement
  - [ ] One harness diff shown: what changed between iteration 0 and best iteration (make it concrete)
  - [ ] UC2 (NPL) described as the next use case to enable
- Dependencies: Phase 4 complete

## Critical Path

Phase 1 → Phase 2 (sequential, both Day 1)
Phase 2 → Phase 3 (must have working baseline before overnight run)
Phase 3 → Phase 4 (overnight run must complete before Day 2 analysis)
Phase 4 → Phase 5 (results must be interpreted before demo)

No parallel paths available given the 48-hour constraint.

## Open Items

- [ ] Decide on meta-agent model: Claude Sonnet 4.6 vs GPT-5 — impacts Day 1 `.env` setup
- [ ] Confirm task suite size: 10 tasks (fast iterations) vs 30 tasks (more robust score) — decision needed before overnight run
- [ ] Confirm client availability: Day 2 afternoon slot must be confirmed before Day 1 starts
- [ ] UC2 (NPL) scaffolding — not in scope for this PoC; next engagement
