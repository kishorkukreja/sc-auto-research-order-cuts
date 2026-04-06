from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd


def allocate(future_orders: pd.DataFrame, capacity: pd.DataFrame) -> pd.DataFrame:
    future = future_orders.copy()
    future["unit_value"] = (
        future["revenue_per_case"].astype(float)
        * future["priority_multiplier"].astype(float)
    )

    capacity_map = dict(
        zip(capacity["week"].astype(int), capacity["capacity_cases"].astype(float), strict=False)
    )

    outputs = []
    for week, week_df in future.groupby("week", sort=True):
        remaining = float(capacity_map[int(week)])
        ordered = week_df.sort_values(
            ["unit_value", "promo_flag", "orders_placed"],
            ascending=[False, False, False],
        ).copy()
        for row in ordered.itertuples(index=False):
            qty = min(float(row.orders_placed), remaining)
            remaining -= qty
            outputs.append(
                {
                    "week": int(row.week),
                    "sku": row.sku,
                    "retailer": row.retailer,
                    "recommended_qty": int(math.floor(qty)),
                }
            )

    return pd.DataFrame(outputs)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "Usage: python scripts/heuristic_solver.py <future_orders.csv> "
            "<capacity_schedule.csv> <output_path>"
        )

    future_orders_path = Path(sys.argv[1])
    capacity_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])

    future_orders = pd.read_csv(future_orders_path)
    capacity = pd.read_csv(capacity_path)
    allocation = allocate(future_orders, capacity)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(allocation.to_dict(orient="records"), indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(allocation)} rows to {output_path}")


if __name__ == "__main__":
    main()

