# Architecture — Order Cut Optimisation via Autoagent

> Derived from conversation on 2026-04-06.

## Overview

A self-optimising agent system that autonomously improves a supply chain order cut allocation agent. A meta-agent iterates on the task agent's harness (prompt, tools, orchestration) overnight, hill-climbing on a weighted fill rate score. The human writes only `program.md`; everything else is autonomous.

## Component Diagram

```
+--------------------+
|  Human Operator    |
|  (writes once)     |
+--------+-----------+
         |
         | program.md (directive)
         v
+--------------------+      reads/writes      +-------------------+
|    Meta-Agent      |<--------------------->|   results.tsv     |
|  (Claude / GPT-5)  |                       |  (iteration log)  |
+--------+-----------+                       +-------------------+
         |
         | edits
         v
+--------------------+
|    agent.py        |
|  (task agent       |
|   harness)         |
+--------+-----------+
         |
         | run_task()
         v
+--------------------+      mounts      +-------------------------+
|  Harbor Runner     |<--------------->|  tasks/                 |
|  (task executor)   |                 |    order-cut-allocation/ |
+--------+-----------+                 |      instruction.md      |
         |                             |      tests/test.py       |
         | spawns                      |      environment/        |
         v                             |        Dockerfile        |
+--------------------+                 |        data/             |
|  Docker Container  |                 +-------------------------+
|  (sandboxed env)   |
+--------+-----------+
         |
         | writes
         v
+--------------------+
| /logs/reward.txt   |
| score: 0.0 - 1.0   |
+--------------------+
```

## Components

### Meta-Agent
- Purpose: Reads results, diagnoses failure modes in agent reasoning traces, edits agent.py to improve performance, gates changes (keep if score improves, discard if not)
- Tech: Claude Sonnet 4.6 or GPT-5 (same-family pairing recommended for "model empathy")
- Interfaces: Reads `results.tsv`, reads task traces, writes `agent.py`, reads `program.md`
- Key decisions: Human never touches agent.py; meta-agent owns the harness

### Task Agent (agent.py)
- Purpose: Receives a supply chain allocation task, runs predict → simulate → optimize loop, outputs recommended order quantities per SKU per retailer per week
- Tech: OpenAI Agents SDK; contains SYSTEM_PROMPT, MODEL, MAX_TURNS, tool definitions, orchestration logic
- Interfaces: Receives `instruction.md` content, calls tools, outputs structured allocation table
- Key decisions: Starts minimal (single bash tool); meta-agent adds specialised tools over iterations

### Harbor Task Runner
- Purpose: Executes tasks in parallel Docker containers, collects scores, returns results to meta-agent
- Tech: Harbor (open-source, pip installable)
- Interfaces: Reads `tasks/` directory structure, writes job output to `jobs/`
- Key decisions: Concurrency set to 100 for overnight runs; single task for spot-checking

### Docker Container (Task Environment)
- Purpose: Sandboxed execution environment per task; prevents harness from damaging host
- Tech: Docker, FROM autoagent-base
- Interfaces: Mounts `data/seasonal_peak_sample.csv`, writes to `/logs/reward.txt`
- Key decisions: Each task gets a fresh container; stateless between runs

### Verifier (test.py)
- Purpose: Computes weighted fill rate from agent allocation output vs held-out true demand; writes score
- Tech: Python, numpy/pandas
- Interfaces: Reads agent stdout (allocation table), reads holdout actuals, writes `/logs/reward.txt`
- Key decisions: Score = weighted fill rate (0.0–1.0); weights = SKU revenue contribution

### Synthetic Dataset
- Purpose: Training + evaluation data for UC1 seasonal peak allocation
- Contents: 12 SKUs × 4 retailers × 16 weeks; includes order history, shipment actuals (with deliberate cut events), production capacity by week, promo calendar
- Key decisions: Data generated synthetically (no client data at PoC stage); cut events are realistic (capacity-driven, not random)

## Data Flow

1. Human writes `program.md` with domain context and success criteria (weighted fill rate > threshold)
2. Meta-agent reads `program.md` and baseline `agent.py`, runs benchmark (iteration 0)
3. Harbor spawns Docker containers, mounts task data, passes `instruction.md` to task agent
4. Task agent runs predict → simulate → optimize, outputs allocation table
5. `test.py` compares allocation to held-out true demand, computes weighted fill rate, writes to `/logs/reward.txt`
6. Harbor collects scores, meta-agent reads results, appends to `results.tsv`
7. Meta-agent diagnoses failures (which SKUs/retailers had poor fill rates, why), edits `agent.py`
8. Gating: if new score > previous score, commit change; else discard
9. Repeat from step 3 overnight

## Integration Points

| System | Direction | Protocol | Notes |
|---|---|---|---|
| OpenAI / Anthropic API | Outbound | REST / SDK | Task agent and meta-agent LLM calls |
| Docker daemon | Outbound | Docker CLI | Container spawn per task |
| Harbor | Internal | Python CLI | Task runner, job orchestration |
| results.tsv | Read/Write | File I/O | Meta-agent's persistent iteration memory |
| /logs/reward.txt | Write (verifier) | File I/O | Score consumed by Harbor, returned to meta-agent |

## Open Architecture Questions

- [ ] Meta-agent model: Claude Sonnet 4.6 vs GPT-5 — model empathy finding suggests Claude+Claude may outperform mixed pairing; needs empirical test
- [ ] Task suite size: 10 tasks (fast iteration) vs 30 tasks (more robust score) for overnight run
- [ ] Tool design for task agent: single bash tool (default) vs pre-built `compute_fill_rate()` and `simulate_allocation()` tools — latter removes arithmetic errors but constrains harness exploration
