# Glossary — Order Cut Optimisation / Autoagent PoC

> Auto-generated from conversation on 2026-04-06.
> Covers all acronyms, domain terms, and abbreviations used in this discussion.

| Term / Acronym | Full Form | Definition |
|---|---|---|
| S&OP | Sales & Operations Planning | Cross-functional process aligning supply capacity with commercial demand; the primary planning cadence for CPG manufacturers |
| PoC | Proof of Concept | Working demonstration of a mechanism, scoped to validate feasibility rather than production readiness |
| CPG | Consumer Packaged Goods | Fast-moving retail goods category; clients include PepsiCo, L'Oréal, Unilever |
| SKU | Stock Keeping Unit | A distinct inventory item; defined by product variant, pack size, and retailer configuration |
| OOS | Out of Stock | A condition where demand exists but no inventory is available to fulfil it |
| Fill Rate | — | Ratio of units shipped to units ordered (or demanded). In this PoC, `fill rate = shipments / orders placed`, NOT shipments / sales |
| Shipment-to-Demand Ratio | — | Same as fill rate when demand is approximated by orders placed. The correct uncensored service level metric — used here instead of shipment-to-sales to avoid cut-induced distortion |
| Order Cut | — | An instance where a retailer's order is fulfilled partially or not at all, resulting in shipments < orders placed. The primary event this PoC optimises against |
| Pent-up Demand | — | Unfulfilled demand that persists after a cut event. May partially carry forward to the next period or be permanently lost to a competitor |
| True Demand | — | The actual quantity consumers would purchase if supply were unconstrained. Approximated here by orders placed, which is less censored than sales (which reflect cuts already applied) |
| Censored Signal | — | A demand measurement that has been distorted by supply constraints; sales data is censored because cuts reduce what can be sold |
| WAPE | Weighted Absolute Percentage Error | Forecast accuracy metric: `sum(|actual - pred|) / sum(actual)`. Mentioned as the metric for demand forecasting (UC1 originally); superseded by weighted fill rate in final framing |
| Weighted Fill Rate | — | Fill rate averaged across SKUs, weighted by revenue contribution per SKU. The primary optimisation metric and agent score |
| Allocation | — | The act of distributing constrained supply across multiple retailers or customers when total demand exceeds available production |
| Harness | — | In the autoagent context: the scaffolding around an LLM — system prompt, tool definitions, routing logic, orchestration — that determines how the agent behaves on a task |
| Meta-agent | — | The autonomous agent that engineers and improves the task agent's harness. Reads scores from results.tsv, diagnoses failures, edits agent.py, re-runs benchmark |
| Task Agent | — | The inner agent that actually solves supply chain tasks. Its harness (agent.py) is what the meta-agent optimises |
| Hill-climbing | — | The iterative optimisation strategy: run, score, keep if better, discard if worse, repeat |
| Harbor | — | The open-source task runner used by autoagent to execute benchmark tasks in Docker containers and collect scores |
| Docker | — | Container runtime used to isolate each task execution in autoagent, preventing the agent from damaging the host environment |
| program.md | — | The markdown directive written by the human that steers the meta-agent. Defines domain, goal, constraints, and success criteria |
| agent.py | — | The single file containing the entire task agent harness. Only file the meta-agent is permitted to edit |
| results.tsv | — | Tab-separated log of every iteration: score, commit hash, tasks evaluated, timestamp. The meta-agent's memory of what it has tried |
| UC1 | Use Case 1 | Seasonal Peak Allocation — the primary PoC use case: allocating constrained production across retailers during a summer peak |
| UC2 | Use Case 2 | New Product Launch Build Quantity — secondary use case: choosing optimal production run size for a limited-edition SKU with no sales history |
| NPL | New Product Launch | The process of bringing a new SKU to market; UC2 is centred on this |
| Monte Carlo | — | Simulation technique using random sampling over uncertain inputs to build a probability distribution of outcomes; used in UC2 to model demand uncertainty |
| Lead Time | — | The elapsed time from a purchase order being placed to goods being available for shipment |
| Safety Stock | — | Buffer inventory held above expected demand to absorb demand variability and supply uncertainty |
| YC W25 | Y Combinator Winter 2025 | The cohort of ThirdLayer (Kevin Gu's company), who built and open-sourced autoagent |
| ThirdLayer | — | The startup (YC W25) that built and released the autoagent repo |
| MIT License | — | Open-source licence under which autoagent is released; permits commercial use |
| Predict → Simulate → Optimize | — | The three-step loop that structures each use case: reconstruct demand, run scenarios, find optimal quantity |

---
*Source: Order Cut Optimisation / Autoagent PoC discussion, 2026-04-06*
