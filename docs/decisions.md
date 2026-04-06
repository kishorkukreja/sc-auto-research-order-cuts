# Decisions Log — Order Cut Optimisation Autoagent PoC

> Derived from conversation on 2026-04-06.

---

## Decision 1 — Framework Selection

| Field | Detail |
|---|---|
| Status | Decided |
| Date | 2026-04-06 |
| Decision | Use kevinrgu/autoagent as the base framework |
| Rationale | auto-harness (neosigmaai) is coupled to tau-bench — a retail/airline customer service benchmark. autoagent is domain-agnostic: any task with a Harbor-format verifier and a numeric score qualifies. Supply chain allocation is not a supported tau-bench domain |
| Alternatives | neosigmaai/auto-harness; build from scratch |
| Consequences | Must write custom tasks/, verifier, and synthetic data. No plug-and-play supply chain benchmark exists |
| Owner | Kish |

---

## Decision 2 — Problem Statement: Order Cuts over Generic Replenishment

| Field | Detail |
|---|---|
| Status | Decided |
| Date | 2026-04-06 |
| Decision | Frame the PoC around order cut allocation, not generic replenishment quantity recommendation |
| Rationale | Order cuts are commercially sharp — they have direct revenue impact, allocation politics, and a non-trivial demand signal problem (demand ≠ sales). Generic replenishment is familiar but doesn't force the demand reconstruction step that makes this interesting to a CPG S&OP audience |
| Alternatives | Demand forecast refinement (M5 dataset), supply exception classification, generic replenishment |
| Consequences | Must design predict → simulate → optimize loop. Verifier must account for shipment-to-demand ratio, not simpler metrics |
| Owner | Kish (reframe from original shortlist) |

---

## Decision 3 — UC1 (Seasonal Peak) First

| Field | Detail |
|---|---|
| Status | Decided |
| Date | 2026-04-06 |
| Decision | Build UC1 (Seasonal Peak Allocation) first for the 2-day PoC; defer UC2 (NPL Build Quantity) |
| Rationale | UC1 has a deterministic verifier (weighted fill rate from known actuals), simpler data structure, and a more familiar CPG scenario. UC2 requires Monte Carlo simulation and analogue scaling which adds implementation risk within 48 hours |
| Alternatives | UC2 first; both simultaneously |
| Consequences | UC2 design is complete but not scaffolded; can be added as second task set post-demo |
| Owner | Kish |

---

## Decision 4 — Demand Signal: Orders Placed, Not Sales

| Field | Detail |
|---|---|
| Status | Decided |
| Date | 2026-04-06 |
| Decision | Use orders_placed as the true demand proxy; never use sales or shipments as the demand ground truth |
| Rationale | Sales data is censored by cuts. If a retailer ordered 1,000 units and received 600 due to a cut, sales records 600 — permanently undercounting demand. Orders placed records 1,000, which is the retailer's actual intent. Using sales would teach the agent to optimise against a signal that already embeds previous cuts |
| Alternatives | Sell-through data (unavailable), econometric demand reconstruction (too complex for PoC), sales data (rejected) |
| Consequences | Synthetic dataset must include orders_placed separately from shipments; holdout actuals use orders_placed as true_demand in verifier |
| Owner | Kish + Claude |

---

## Decision 5 — Metric: Weighted Fill Rate

| Field | Detail |
|---|---|
| Status | Decided |
| Date | 2026-04-06 |
| Decision | Score = weighted fill rate, where fill_rate = min(allocated_qty, available_supply) / true_demand, weighted by SKU revenue contribution |
| Rationale | Unweighted fill rate treats a £0.50/case SKU equally to a £12/case SKU. Weighting by revenue aligns the agent's optimisation signal to what the client actually cares about: revenue protection under constrained supply |
| Alternatives | Unit fill rate (unweighted), binary pass/fail per task, WAPE (demand forecast metric — wrong for this problem) |
| Consequences | Synthetic dataset must include revenue_per_case; verifier must compute and apply weights |
| Owner | Kish + Claude |

---

## Decision 6 — Synthetic Data (No Client Data)

| Field | Detail |
|---|---|
| Status | Decided |
| Date | 2026-04-06 |
| Decision | Generate seasonal_peak_sample.csv synthetically for the PoC |
| Rationale | No client data available within the 48-hour window. Synthetic data allows deliberate control over cut events, capacity tightness, and promo timing — which makes the problem tractable and the improvement measurable |
| Alternatives | M5 Walmart dataset (demand forecasting focus, not allocation); client historical data (unavailable) |
| Consequences | Client numbers in the demo are illustrative, not from their actual data. Frame explicitly as such to maintain credibility |
| Owner | Kish |

---

## Decision 7 — Client Framing: Proof of Mechanism

| Field | Detail |
|---|---|
| Status | Decided |
| Date | 2026-04-06 |
| Decision | Present the PoC as "proof of mechanism" not "production system" |
| Rationale | autoagent is days old. Benchmark claims are from creator's own announcement and not yet verified on official leaderboards. Overclaiming reliability will backfire with a supply chain client who will immediately ask about data integration, audit trails, and failure modes |
| Alternatives | Present as production-ready (rejected); present as research only (undersells) |
| Consequences | Client story focuses on: the loop is real, the improvement is measured, the mechanism is demonstrably autonomous. Next conversation is about what data integration looks like |
| Owner | Kish |
