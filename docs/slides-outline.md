# Slide Outline — Order Cut Optimisation via Self-Optimising Agent

> 10 slides | Complex | Generated 2026-04-06

---

## Slide 1 — Title
Headline: Autonomous Order Cut Optimisation
Subheadline: A self-improving AI agent that allocates constrained supply — without human prompt engineering
Visual: Clean dark background; Coefficient Advisory logo; single line: "Proof of Mechanism — April 2026"
Speaker notes: Set the frame immediately — this is not a dashboard, not a recommendation engine. It's a loop that gets better at allocation on its own. Don't show the tool yet. Start with the problem.

---

## Slide 2 — The Problem: Order Cuts Are a Silent Revenue Leak
Headline: Every cut is two losses — the sale you missed and the demand signal you corrupted
Body:
- When shipments < orders placed, you lose the sale — and record a lower number than was ever demanded
- That lower number becomes next year's forecast baseline
- During a promotional peak or new launch, cuts don't recover — they compound
- Your S&OP team spends 2 days on allocation decisions that are political, not analytical
Visual: Simple flow diagram — True Demand → Orders Placed → Cut → Shipments (smaller arrow) → Sales recorded (even smaller) → Next year's plan (distorted)
Speaker notes: Make this personal — "Has your team ever gone into a peak and come out wondering why fill rates were worse than the forecast said they should be? This is why."

---

## Slide 3 — The Demand ≠ Sales Problem
Headline: Your fill rate is measured against the wrong denominator
Body:
- Shipment / Sales looks fine when you've cut 30% of orders — because sales already reflects the cut
- Shipment / Orders Placed shows the real service level — the one your retailers are measuring you by
- Pent-up demand from a cut during promo week doesn't carry forward — it walks to the competitor
Visual: Two-column table — "What you measure" vs "What retailers measure" — with fill rate calculated both ways for a sample cut scenario, showing the gap
Speaker notes: This is the intellectual anchor of the whole demo. If the client is tracking fill rate against sales, they are flying blind.

---

## Slide 4 — The Approach: Predict → Simulate → Optimize
Headline: Three steps the agent runs autonomously — in 30 seconds
Body:
- Predict: Reconstruct true demand from orders placed + cut log (not from sales)
- Simulate: Run allocation scenarios against production capacity; compute fill rates by retailer and SKU
- Optimize: Select the allocation that maximises weighted fill rate — weighted by revenue, not units
Visual: Three-box horizontal flow with brief description under each; arrows between boxes
Speaker notes: This is what a good S&OP analyst does manually in two days. The agent does it in one API call. The question is: how good is the agent? That's what the next slide answers.

---

## Slide 5 — The Self-Optimising Loop
Headline: We don't tune the agent. The agent tunes itself.
Body:
- The meta-agent reads failure traces and edits the task agent's harness overnight
- Each iteration: run benchmark → score → keep if better → discard if worse → repeat
- Human writes one directive (program.md). Everything else is autonomous.
Visual: Loop diagram — program.md → meta-agent → agent.py (harness) → benchmark tasks → score → results.tsv → back to meta-agent; arrow labelled "overnight" going around the loop
Speaker notes: The key insight: you don't need to know why the agent failed. The meta-agent reads the traces and figures it out. Your job is to write the success criterion and let it run.

---

## Slide 6 — What Improved (Results)
Headline: Weighted fill rate: [X]% baseline → [Y]% after [N] iterations
Body:
- Baseline (iteration 0): untuned agent, single instruction, no specialised tools
- Best iteration: decomposed predict/simulate/optimize steps, calculation tool added
- Key harness change: [describe the actual diff from results.tsv — e.g. "meta-agent added explicit step decomposition and a fill rate calculation tool; removed arithmetic from LLM reasoning"]
- [N] iterations completed overnight, zero human interventions
Visual: Line chart — iteration number (x-axis) vs weighted fill rate (y-axis); baseline marked with dashed line; best iteration marked with star; progression visible
Speaker notes: Show the actual results.tsv numbers. Don't round up. The credibility is in the specificity. If improvement is small, say "this ran for 8 hours; a 72-hour run would go further."

---

## Slide 7 — Before / After: The Allocation Itself
Headline: Iteration 0 left retailer A's promo week 30% undersupplied. Iteration [N] didn't.
Body:
- Show a simplified allocation table: SKU_03, week 5 (promo), RET_A vs RET_B
- Baseline: proportional cut — both retailers take the same hit, promo retailer suffers
- Optimised: promo-aware allocation — RET_A's promo SKUs protected, non-promo cut absorbed by RET_B
Visual: Side-by-side table — Baseline allocation vs Optimised allocation; highlight the promo rows
Speaker notes: Make it concrete. Abstract fill rate improvement is good. Showing that the agent learned to protect a promo allocation without being told to — that's the moment.

---

## Slide 8 — Use Case 2: New Product Launch Build Quantity
Headline: The highest-stakes order cut decision happens before you have a single data point
Body:
- NPL: one production run, no sales history, order intent not binding
- Agent uses analogue launch curves + promo uplift + Monte Carlo uncertainty to size the build
- Optimises: expected revenue captured minus write-off risk — not just "build as much as possible"
- A cut in launch week is permanent — consumers try once, find nothing, move on
Visual: S-curve launch profile for 3 analogues overlaid; shaded uncertainty band; vertical line at recommended build quantity
Speaker notes: This is the second use case we've designed. It's not in today's PoC but the same loop applies — different instruction, different verifier, same overnight run.

---

## Slide 9 — What This Is (And What It Isn't)
Headline: A proven mechanism. Not a production system. Yet.
Body:
- This is proof that an autonomous loop can improve a supply chain allocation agent without human tuning
- The improvement is real and measured — not a claim, an observation from results.tsv
- Productionising requires: your ERP/WMS data as input, a UI for planners, audit trails, approval workflow
- The loop itself is the IP — the harness it discovers becomes the starting point for your deployment
Visual: Two-column — "What we proved today" vs "What Phase 2 builds"
Speaker notes: Pre-empt the "but can we use this in production?" question. Frame it as: "Today we established the floor. Phase 2 lifts the ceiling."

---

## Slide 10 — Next Steps
Headline: Three things need to happen in the next two weeks
Body:
- [ ] Agree on the target use case for Phase 2 — seasonal allocation or NPL build quantity
- [ ] Identify the data source — which system holds orders placed vs shipments + cut log?
- [ ] Scope the integration — read-only data pull from your S&OP tool into the harness
Visual: Three-row action list with owner and date columns
Speaker notes: Don't leave without a named action and a named owner. The demo is the opening; this slide is the ask.

---

## Usage Notes

- Slides 1–6: Core 15-minute demo — problem, approach, results
- Slides 7–8: Use if audience is technically curious or wants supply chain specifics
- Slides 9–10: Always include — credibility management and next steps
- Slide 6 visual is the most important: fill the chart with real results.tsv data before presenting
