# Requirements — Order Cut Optimisation Autoagent PoC

> Derived from conversation on 2026-04-06.

## Functional Requirements

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| FR-1 | System must autonomously improve a task agent's harness without human editing of agent.py | Must | Core autoagent mechanic |
| FR-2 | Task agent must receive order history, cut log, capacity schedule, and promo calendar as input | Must | Defined in instruction.md |
| FR-3 | Task agent must output a recommended allocation table (SKU × retailer × week → qty) | Must | Verifier depends on this format |
| FR-4 | Verifier must compute weighted fill rate from agent output vs held-out true demand | Must | Score drives meta-agent hill-climbing |
| FR-5 | Verifier must write a float 0.0–1.0 to /logs/reward.txt | Must | Harbor requirement |
| FR-6 | Verifier must handle malformed agent output gracefully (return 0.0, not crash) | Must | Otherwise Harbor errors and stops the loop |
| FR-7 | Demand must be proxied by orders placed, not shipments or sales | Must | Core demand ≠ sales principle |
| FR-8 | Fill rate must be computed as shipments / orders placed (not shipments / sales) | Must | Uncensored signal requirement |
| FR-9 | Weighted fill rate must weight SKUs by revenue contribution | Must | Aligns score to commercial priorities |
| FR-10 | Meta-agent must log every iteration to results.tsv | Must | Evidence of autonomous improvement for client demo |
| FR-11 | Total agent allocations must not exceed weekly production capacity constraint | Must | Physical constraint; allocations that exceed capacity are invalid |
| FR-12 | System must run overnight without human intervention | Must | 48-hour PoC constraint |
| FR-13 | UC2 (NPL build quantity) must be designed and documented | Should | Designed; not scaffolded at PoC stage |
| FR-14 | Pent-up demand must be flagged in the predict step | Should | Improves agent's contextual reasoning; not scored directly |
| FR-15 | Promo calendar must be used to adjust allocation priority during promo weeks | Should | Retailer A has a 3-week promo in the synthetic data |

## Non-Functional Requirements

| ID | Category | Requirement | Target |
|---|---|---|---|
| NFR-1 | Speed | Full overnight benchmark run must complete within 8 hours | < 8 hours for 100 concurrent tasks |
| NFR-2 | Reliability | Verifier must not crash on any agent output format | 0 crashes; return 0.0 on parse failure |
| NFR-3 | Reproducibility | Baseline score (iteration 0) must be logged before any harness changes | results.tsv row 0 = unmodified agent |
| NFR-4 | Portability | Repo must run on any machine with Docker + Python 3.12+ | No host-specific dependencies outside .env |
| NFR-5 | Credibility | Demo must show measured improvement across iterations, not just a single good output | results.tsv progression as evidence |
| NFR-6 | Safety | Agent execution must be Docker-sandboxed | No host filesystem writes outside mounted volumes |
| NFR-7 | Simplicity | agent.py changes that achieve the same score with less complexity must be preferred | Per autoagent program.md directive |

## Out of Scope

- Production data integration (no client ERP, WMS, or S&OP system connectivity at PoC stage)
- Real-time or near-real-time allocation (batch only for PoC)
- UI or dashboard (results.tsv + console output is sufficient for demo)
- Model fine-tuning (prompt/harness optimisation only; no weight updates)
- UC2 (NPL Build Quantity) scaffolding (designed but deferred)
- Regulatory or compliance requirements (no audit trail, no approval workflow)
- Multi-echelon inventory (single-level: manufacturer to retailer only)

## Open / TBD

- [ ] Exact task suite size (10 vs 30 tasks) — affects iteration count vs score robustness trade-off
- [ ] Meta-agent model selection (Claude Sonnet 4.6 vs GPT-5) — model empathy finding suggests Claude+Claude may outperform, needs empirical test
- [ ] Minimum acceptable score threshold for program.md success criteria — suggested: weighted fill rate > 0.80; needs confirmation against baseline to ensure it's achievable
- [ ] Whether pent-up demand carry-forward should be modelled across weeks (adds realism but increases verifier complexity)
