# Risks & Issues — Order Cut Optimisation Autoagent PoC

> Derived from conversation on 2026-04-06.

## Risk Register

| ID | Description | Likelihood | Impact | Owner | Mitigation |
|---|---|---|---|---|---|
| R1 | autoagent repo is days old; undocumented failure modes in Harbor or Docker setup | H | H | Kish | Allocate 3 hours on Day 1 morning for env setup; have fallback of running meta-agent loop manually if Harbor fails |
| R2 | Meta-agent produces no score improvement overnight (loop runs but score is flat) | M | H | Kish | Ensure baseline produces a non-zero score first; if flat, simplify task (fewer SKUs, cleaner capacity constraint) and re-run Day 2 morning |
| R3 | Verifier crashes on malformed agent output, stopping the loop silently | H | H | Kish | Wrap all test.py logic in try/except; always write 0.0 on any exception; test with known-bad output before overnight run |
| R4 | Agent output format is inconsistent (sometimes JSON, sometimes prose) — verifier can't parse | H | M | Kish | Add explicit output format instruction to instruction.md; verifier must attempt multiple parse strategies before returning 0.0 |
| R5 | Client questions production readiness in demo; PoC framing fails | M | M | Kish | Frame explicitly as "proof of mechanism" from the start; prepare 3-sentence answer on what productionising requires |
| R6 | Synthetic data is too easy (agent gets near-perfect score from iteration 0) — no improvement to show | M | M | Kish | Build deliberate tension: capacity = 85% of total orders placed; promo creates a conflict between two retailers in the same week |
| R7 | Docker image build fails due to dependency conflict in autoagent-base | M | H | Kish | Test build on Day 1 first thing; check Python 3.12+ requirement; if fails, raise issue on autoagent GitHub |
| R8 | API rate limits hit during overnight run (100 concurrent tasks × multiple LLM calls each) | L | M | Kish | Reduce concurrency from 100 to 20 if rate limits are a concern; use Tier 2+ API key |
| R9 | Client demands to see their real data, not synthetic | L | M | Kish | Frame as: "This is a sterile sandbox PoC. Phase 2 connects to your actual S&OP data. Today we're proving the mechanism works." |
| R10 | Benchmark score claims from autoagent creator not yet independently verified | H | L | Kish | Already decided: frame PoC as "proof of mechanism" not "validated benchmark system" — R10 is pre-mitigated by D7 |

## Open Issues

| ID | Description | Raised | Status | Next Action |
|---|---|---|---|---|
| I1 | Meta-agent model not yet selected (Claude vs GPT-5) | 2026-04-06 | Open | Decide before Day 1 afternoon; if using Claude, confirm Anthropic API key + OpenAI Agents SDK adapter works |
| I2 | Task suite size (10 vs 30) not finalised | 2026-04-06 | Open | Default to 15 tasks for balance; review after iteration 0 runtime |
| I3 | Success threshold for program.md not calibrated | 2026-04-06 | Open | Run iteration 0, check baseline score, set threshold at baseline + 0.15 |

## Blockers

- None currently. All blockers are resolved by the synthetic data decision (no client data dependency) and the autoagent framework selection (no custom framework build required).
- **Potential blocker:** Docker not available on build machine — must be resolved before Day 1 afternoon can begin.
