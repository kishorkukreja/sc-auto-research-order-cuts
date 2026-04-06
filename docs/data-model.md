# Data Model — Order Cut Optimisation Autoagent PoC

> Derived from conversation on 2026-04-06.

## Entity Overview

```
[SKU] N---------N [Retailer]
  |                    |
  |    via             |
  +---->[AllocationEvent]<----+
              |
              |
         [Week/Period]

[SKU] 1---------N [PricingConfig]
[SKU] N---------N [PromoCalendar]
[Retailer] N----N [PromoCalendar]
```

## Entities

### AllocationEvent (core fact table — seasonal_peak_sample.csv)

The primary dataset. Each row is one SKU × retailer × week observation.

| Field | Type | Notes |
|---|---|---|
| week | int | 1–16; weeks 1–12 = training (visible to agent), weeks 13–16 = holdout (verifier only) |
| sku | str | SKU_01 to SKU_12; 12 distinct SKUs |
| retailer | str | RET_A to RET_D; 4 retail customers |
| orders_placed | int | Retailer's intended order quantity; the uncensored demand signal |
| shipments | int | Actual units shipped; orders_placed × historical_fill_rate; censored by cuts |
| fill_rate | float | shipments / orders_placed; < 1.0 indicates a cut occurred |
| promo_flag | bool | 1 if this SKU/retailer/week has an active promotion |
| revenue_per_case | float | Used to compute revenue_weight in verifier |
| capacity | int | Total production capacity available this week; shared across all SKUs and retailers |

Key constraint: `sum(shipments[all_skus][all_retailers][week]) <= capacity[week]`

### HoldoutActuals (verifier-only — holdout_actuals.csv)

Weeks 13–16 actuals. Not mounted in instruction.md context. Verifier reads directly.

| Field | Type | Notes |
|---|---|---|
| week | int | 13–16 only |
| sku | str | Same domain as training |
| retailer | str | Same domain as training |
| true_demand | int | = orders_placed for these weeks; the ground truth the agent is scored against |
| available_supply | int | Actual supply available per SKU per week; may differ from stated capacity due to production variability |
| revenue_weight | float | revenue_per_case normalised to sum to 1.0 across all SKUs |

### CapacitySchedule (capacity_schedule.csv)

| Field | Type | Notes |
|---|---|---|
| week | int | 1–16 |
| capacity_cases | int | Weeks 1–4: 8,500; weeks 5–8: 10,000; subsequent weeks: to be defined in synthetic data |

### PromoCalendar (promo_calendar.csv)

| Field | Type | Notes |
|---|---|---|
| retailer | str | Retailer with promotion |
| sku | str | SKU on promotion (or ALL for retailer-wide promo) |
| week_start | int | First week of promotion |
| week_end | int | Last week of promotion (inclusive) |
| promo_type | str | TPRICE (temporary price reduction), DISPLAY, FEATURE, or MULTI |
| uplift_factor | float | Expected demand multiplier during promo vs non-promo baseline |

Key promo in synthetic data: RET_A, all SKUs, weeks 5–7, uplift_factor = 1.4

### AgentAllocationOutput (ephemeral — agent stdout)

What the task agent is expected to output. Verifier parses this.

| Field | Type | Notes |
|---|---|---|
| week | int | Week of recommendation (13–16) |
| sku | str | SKU being allocated |
| retailer | str | Retailer receiving allocation |
| recommended_qty | int | Agent's recommended shipment quantity |

Expected format: JSON array of objects. Verifier must also handle CSV fallback.

## Key Constraints

- `sum(recommended_qty[all_skus][all_retailers][week]) <= capacity_cases[week]` — hard physical constraint; allocations exceeding this are physically impossible
- `recommended_qty >= 0` — no negative allocations
- `fill_rate = min(recommended_qty, available_supply) / true_demand` — the verifier always applies available_supply as a ceiling, even if agent recommends more
- Revenue weights must sum to 1.0 across all SKUs for weighted fill rate to be interpretable as a percentage
- Weeks 13–16 holdout data must not appear in instruction.md (data leakage would invalidate the score)
