# Seasonal Peak Allocation Task

## Scenario
Dual promo conflict

RET_A and RET_C have overlapping promotions that force sharper trade-offs in weeks 14-15.

You are acting as an allocation agent for a CPG manufacturer facing order cuts.

## Objective

Create a feasible allocation plan for weeks 13-16 that maximizes weighted fill rate.

Use the visible files in `/task/environment/files/`:

- `train_history.csv` - weeks 1-12 order history with shipment cuts
- `future_orders.csv` - order intent for weeks 13-16
- `capacity_schedule.csv` - weekly capacity limits
- `promo_calendar.csv` - historical and future promo events
- `scenario_notes.json` - scenario metadata

## Required method

Follow a predict -> simulate -> optimize workflow:

1. Inspect the historical cuts and promo pattern.
2. Use future order intent plus commercial priority signals.
3. Produce a feasible allocation for every row in `future_orders.csv`.

## Hard constraints

- Weekly sum of `recommended_qty` must not exceed `capacity_cases` for that week.
- `recommended_qty` must be non-negative.
- Write the final plan to `/app/output/allocation_plan.json`.

## Output format

Write a JSON array with one object per row:

```json
[
  {
    "week": 13,
    "sku": "SKU_01",
    "retailer": "RET_A",
    "recommended_qty": 123
  }
]
```

Include each visible `(week, sku, retailer)` row exactly once.

## Commercial guidance

- `orders_placed` is the demand proxy for this PoC.
- `revenue_weight` is the SKU revenue contribution used in evaluation.
- `priority_multiplier` is an explicit planning hint for promo and account protection.
- If trade-offs are required, prioritize higher-value and promo-sensitive rows first.

## Deliverable

1. Write `/app/output/allocation_plan.json`
2. Ensure the file is valid JSON before finishing.
