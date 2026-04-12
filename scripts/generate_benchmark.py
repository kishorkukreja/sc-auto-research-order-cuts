from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "tasks"
TASKS_EVAL_DIR = ROOT / "tasks_eval"
DATA_DIR = ROOT / "data" / "generated"

SKUS = [f"SKU_{i:02d}" for i in range(1, 13)]
RETAILERS = ["RET_A", "RET_B", "RET_C", "RET_D"]
HISTORY_WEEKS = list(range(1, 13))
FUTURE_WEEKS = list(range(13, 17))


SCENARIOS = [
    {
        "slug": "order-cut-allocation-01",
        "seed": 1001,
        "title": "Promo protection on RET_A",
        "description": "RET_A runs a major summer feature in weeks 13-14 while capacity is tight in both weeks.",
        "retailer_boosts": {"RET_A": 1.08},
        "future_capacity_factors": [0.78, 0.76, 0.87, 0.90],
        "future_promos": [("RET_A", "ALL", 13, 14, "FEATURE", 1.35)],
    },
    {
        "slug": "order-cut-allocation-02",
        "seed": 1002,
        "title": "Dual promo conflict",
        "description": "RET_A and RET_C have overlapping promotions that force sharper trade-offs in weeks 14-15.",
        "retailer_boosts": {"RET_A": 1.05, "RET_C": 1.07},
        "future_capacity_factors": [0.84, 0.73, 0.75, 0.88],
        "future_promos": [
            ("RET_A", "ALL", 14, 15, "DISPLAY", 1.30),
            ("RET_C", "SKU_03", 14, 15, "TPRICE", 1.42),
            ("RET_C", "SKU_08", 14, 15, "TPRICE", 1.38),
        ],
    },
    {
        "slug": "order-cut-allocation-03",
        "seed": 1003,
        "title": "Capacity drop in week 15",
        "description": "A line outage in week 15 creates a one-week shock after a relatively healthy start.",
        "retailer_boosts": {"RET_B": 1.06},
        "future_capacity_factors": [0.95, 0.92, 0.63, 0.88],
        "future_promos": [("RET_B", "ALL", 15, 15, "FEATURE", 1.28)],
    },
    {
        "slug": "order-cut-allocation-04",
        "seed": 1004,
        "title": "High-margin premium scarcity",
        "description": "Premium SKUs are margin-critical and selected RET_D rows are launching into a sparse week 16.",
        "retailer_boosts": {"RET_D": 1.09},
        "future_capacity_factors": [0.86, 0.83, 0.81, 0.74],
        "future_promos": [
            ("RET_D", "SKU_10", 16, 16, "FEATURE", 1.45),
            ("RET_D", "SKU_11", 16, 16, "FEATURE", 1.40),
        ],
    },
    {
        "slug": "order-cut-allocation-05",
        "seed": 1005,
        "title": "Balanced shortage across all weeks",
        "description": "Capacity stays below demand for the whole horizon with no single catastrophic week.",
        "retailer_boosts": {"RET_A": 1.04, "RET_B": 1.03},
        "future_capacity_factors": [0.84, 0.84, 0.83, 0.82],
        "future_promos": [("RET_A", "SKU_02", 13, 14, "MULTI", 1.33)],
    },
    {
        "slug": "order-cut-allocation-06",
        "seed": 1006,
        "title": "Strategic account protection",
        "description": "RET_B is a strategic customer and needs to be protected during a broad capacity squeeze.",
        "retailer_boosts": {"RET_B": 1.12},
        "future_capacity_factors": [0.80, 0.79, 0.82, 0.85],
        "future_promos": [("RET_B", "ALL", 13, 13, "DISPLAY", 1.25)],
    },
    {
        "slug": "order-cut-allocation-07",
        "seed": 1007,
        "title": "Promo mix shift to premium",
        "description": "Premium SKUs receive heavy promotional pressure from RET_A and RET_D in the back half.",
        "retailer_boosts": {"RET_A": 1.05, "RET_D": 1.06},
        "future_capacity_factors": [0.89, 0.77, 0.76, 0.80],
        "future_promos": [
            ("RET_A", "SKU_09", 14, 15, "FEATURE", 1.44),
            ("RET_D", "SKU_12", 15, 16, "FEATURE", 1.41),
        ],
    },
    {
        "slug": "order-cut-allocation-08",
        "seed": 1008,
        "title": "Late-horizon retailer launch",
        "description": "RET_C has a late launch event on selected SKUs just as capacity tightens in week 16.",
        "retailer_boosts": {"RET_C": 1.08},
        "future_capacity_factors": [0.93, 0.90, 0.82, 0.70],
        "future_promos": [
            ("RET_C", "SKU_04", 16, 16, "FEATURE", 1.47),
            ("RET_C", "SKU_07", 16, 16, "FEATURE", 1.39),
        ],
    },
    {
        "slug": "order-cut-allocation-09",
        "seed": 1009,
        "title": "Two weak weeks then recovery",
        "description": "Weeks 13-14 are severely short, then production recovers enough to catch up partially.",
        "retailer_boosts": {"RET_A": 1.07, "RET_C": 1.05},
        "future_capacity_factors": [0.69, 0.72, 0.96, 0.98],
        "future_promos": [
            ("RET_A", "ALL", 13, 14, "TPRICE", 1.31),
            ("RET_C", "SKU_05", 13, 14, "DISPLAY", 1.36),
        ],
    },
    {
        "slug": "order-cut-allocation-10",
        "seed": 1010,
        "title": "High-volume low-margin trap",
        "description": "Large low-margin orders can soak up capacity unless the agent follows commercial weighting correctly.",
        "retailer_boosts": {"RET_D": 1.04},
        "future_capacity_factors": [0.82, 0.80, 0.78, 0.86],
        "future_promos": [("RET_D", "ALL", 14, 14, "DISPLAY", 1.22)],
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate dev and/or eval benchmark task suites."
    )
    parser.add_argument(
        "--split",
        choices=["dev", "eval", "all"],
        default="all",
        help="Which benchmark split to generate.",
    )
    parser.add_argument("--dev-tasks-dir", type=Path, default=TASKS_DIR)
    parser.add_argument("--eval-tasks-dir", type=Path, default=TASKS_EVAL_DIR)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    return parser.parse_args()


def build_eval_scenarios() -> list[dict]:
    eval_scenarios: list[dict] = []
    for idx, scenario in enumerate(SCENARIOS, start=1):
        adjusted = dict(scenario)
        adjusted["slug"] = f"order-cut-allocation-eval-{idx:02d}"
        adjusted["seed"] = int(scenario["seed"]) + 7000
        adjusted["title"] = f"{scenario['title']} (Eval)"
        adjusted["description"] = (
            scenario["description"]
            + " This held-out eval variant uses a different hidden random seed and a shifted shortage profile."
        )
        adjusted["future_capacity_factors"] = [
            round(float(min(0.98, max(0.60, factor + delta))), 2)
            for factor, delta in zip(
                scenario["future_capacity_factors"],
                [0.03, -0.02, 0.01, -0.01],
                strict=True,
            )
        ]
        eval_scenarios.append(adjusted)
    return eval_scenarios


TASK_TOML = '''schema_version = "1.1"

[task]
name = "supply-chain/{task_name}"
description = "{description}"
authors = []
keywords = ["supply-chain", "allocation", "order-cuts"]

[metadata]
author_name = "OpenAI Codex"
author_email = "noreply@example.com"
difficulty = "medium"
category = "supply-chain"
tags = ["allocation", "seasonal-peak", "order-cut-optimisation"]

[verifier]
timeout_sec = 120.0

[agent]
timeout_sec = 240.0

[environment]
build_timeout_sec = 600.0
cpus = 1
memory_mb = 4096
storage_mb = 10240
gpus = 0
allow_internet = true
mcp_servers = []

[verifier.env]

[environment.env]

[solution.env]
'''


TEST_SH = '''#!/bin/bash
set -euo pipefail

python /tests/test.py || {
  mkdir -p /logs/verifier
  echo 0.0 > /logs/verifier/reward.txt
}
'''


TEST_PY = r'''from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


OUTPUT_PATH = Path(os.getenv("ALLOC_OUTPUT_PATH", "/app/output/allocation_plan.json"))
HOLDOUT_PATH = Path(os.getenv("HOLDOUT_PATH", "/tests/holdout_actuals.csv"))
REWARD_PATH = Path(os.getenv("REWARD_PATH", "/logs/verifier/reward.txt"))
DETAILS_PATH = Path(os.getenv("DETAILS_PATH", "/logs/verifier/score_breakdown.json"))

KEYS = ["week", "sku", "retailer"]
REQ_COLS = KEYS + ["recommended_qty"]


def _load_output(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=REQ_COLS)

    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return pd.DataFrame(columns=REQ_COLS)

    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get("allocations", [])
        df = pd.DataFrame(payload)
    except Exception:
        try:
            df = pd.read_csv(path)
        except Exception:
            return pd.DataFrame(columns=REQ_COLS)

    missing = [c for c in REQ_COLS if c not in df.columns]
    if missing:
        return pd.DataFrame(columns=REQ_COLS)

    df = df[REQ_COLS].copy()
    df["week"] = pd.to_numeric(df["week"], errors="coerce")
    df["recommended_qty"] = pd.to_numeric(df["recommended_qty"], errors="coerce")
    df = df.dropna(subset=["week", "recommended_qty", "sku", "retailer"])
    if df.empty:
        return pd.DataFrame(columns=REQ_COLS)

    df["week"] = df["week"].astype(int)
    df["recommended_qty"] = df["recommended_qty"].clip(lower=0)
    df = (
        df.groupby(KEYS, as_index=False)["recommended_qty"]
        .sum()
        .sort_values(KEYS)
        .reset_index(drop=True)
    )
    return df


def compute_score() -> tuple[float, dict]:
    truth = pd.read_csv(HOLDOUT_PATH)
    alloc = _load_output(OUTPUT_PATH)

    merged = truth.merge(alloc, on=KEYS, how="left")
    merged["recommended_qty"] = pd.to_numeric(merged["recommended_qty"], errors="coerce").fillna(0.0)

    weekly_totals = (
        merged.groupby("week", as_index=False)
        .agg(total_recommended=("recommended_qty", "sum"), capacity_cases=("capacity_cases", "first"))
    )
    capacity_violations = weekly_totals[weekly_totals["total_recommended"] > weekly_totals["capacity_cases"] + 1e-9]
    if not capacity_violations.empty:
        details = {
            "score": 0.0,
            "error": "capacity_violation",
            "violations": capacity_violations.to_dict(orient="records"),
            "weekly_capacity": weekly_totals.to_dict(orient="records"),
        }
        return 0.0, details

    merged["shipped_qty"] = np.minimum(merged["recommended_qty"], merged["available_supply"])
    merged["fill_rate"] = merged["shipped_qty"] / merged["true_demand"].clip(lower=1e-9)
    merged["weighted_fill"] = merged["fill_rate"] * merged["revenue_weight"]

    denom = float(merged["revenue_weight"].sum())
    if denom <= 0:
        return 0.0, {"reason": "zero_denominator"}

    score = float(np.clip(merged["weighted_fill"].sum() / denom, 0.0, 1.0))

    merged["max_possible_fill_rate"] = np.minimum(merged["available_supply"], merged["true_demand"]) / merged["true_demand"].clip(lower=1e-9)
    merged["max_possible_weighted_fill"] = merged["max_possible_fill_rate"] * merged["revenue_weight"]
    max_feasible_score = float(np.clip(merged["max_possible_weighted_fill"].sum() / denom, 0.0, 1.0))

    details = {
        "score": score,
        "max_feasible_score": max_feasible_score,
        "output_found": OUTPUT_PATH.exists(),
        "rows_scored": int(len(merged)),
        "weekly_capacity": weekly_totals.to_dict(orient="records"),
    }
    return score, details


def main() -> None:
    REWARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    DETAILS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        score, details = compute_score()
    except Exception as exc:
        score = 0.0
        details = {"score": 0.0, "error": str(exc)}

    REWARD_PATH.write_text(f"{score:.6f}", encoding="utf-8")
    DETAILS_PATH.write_text(json.dumps(details, indent=2), encoding="utf-8")
    print(json.dumps(details, indent=2))


if __name__ == "__main__":
    main()
'''


ENV_DOCKERFILE = '''FROM autoagent-base

WORKDIR /app

COPY files/ /task/environment/files/

RUN mkdir -p /task/environment/files /app/output
'''


def seasonal_factor(week: int) -> float:
    return 1.0 + 0.18 * math.sin((week - 3) / 16 * 2 * math.pi) + 0.015 * week


def promo_lookup(promos: list[tuple[str, str, int, int, str, float]], retailer: str, sku: str, week: int) -> tuple[int, float]:
    for p_retailer, p_sku, start, end, _ptype, uplift in promos:
        if p_retailer == retailer and start <= week <= end and (p_sku == "ALL" or p_sku == sku):
            return 1, float(uplift)
    return 0, 1.0


def priority_multiplier(
    scenario: dict,
    retailer: str,
    sku: str,
    week: int,
    promo_flag: int,
    revenue_per_case: float,
) -> float:
    multiplier = 1.0
    multiplier *= scenario.get("retailer_boosts", {}).get(retailer, 1.0)
    if promo_flag:
        multiplier *= 1.18
    if sku in {"SKU_09", "SKU_10", "SKU_11", "SKU_12"} and revenue_per_case >= 15:
        multiplier *= 1.06
    if scenario["slug"] == "order-cut-allocation-10" and sku in {"SKU_01", "SKU_02", "SKU_03"}:
        multiplier *= 0.93
    return round(multiplier, 4)


def allocate_history_week(df: pd.DataFrame, capacity: float) -> pd.DataFrame:
    work = df.copy()
    work["base_allocation"] = np.floor(work["orders_placed"] * 0.55)
    base_total = float(work["base_allocation"].sum())
    if base_total > capacity:
        scale = capacity / max(base_total, 1.0)
        work["shipments"] = np.floor(work["base_allocation"] * scale)
        return work

    remaining = capacity - base_total
    work["remaining_need"] = work["orders_placed"] - work["base_allocation"]
    work["priority_score"] = work["revenue_per_case"] * work["priority_multiplier"]
    weighted_need = work["remaining_need"] * work["priority_score"]
    total_weight = float(weighted_need.sum())
    if total_weight > 0 and remaining > 0:
        work["extra"] = np.floor(remaining * weighted_need / total_weight)
    else:
        work["extra"] = 0

    work["shipments"] = np.minimum(
        work["orders_placed"],
        work["base_allocation"] + work["extra"],
    )

    leftover = int(round(capacity - float(work["shipments"].sum())))
    if leftover > 0:
        work = work.sort_values(["priority_score", "remaining_need"], ascending=[False, False]).reset_index(drop=True)
        idx = 0
        while leftover > 0:
            if idx >= len(work):
                idx = 0
            current_gap = int(work.loc[idx, "orders_placed"] - work.loc[idx, "shipments"])
            if current_gap > 0:
                work.loc[idx, "shipments"] += 1
                leftover -= 1
            idx += 1

    return work


def allocate_hidden_supply(df: pd.DataFrame, capacity_cases: int, rng: np.random.Generator) -> pd.DataFrame:
    work = df.copy().reset_index(drop=True)
    work["priority_score"] = (
        work["orders_placed"].astype(float)
        * work["revenue_per_case"].astype(float)
        * work["priority_multiplier"].astype(float)
        * (1.0 + rng.normal(0.0, 0.015, len(work)))
    )
    work["priority_score"] = work["priority_score"].clip(lower=1e-6)
    total_priority = float(work["priority_score"].sum())
    work["available_supply"] = np.floor(capacity_cases * work["priority_score"] / total_priority)
    work["available_supply"] = np.minimum(work["available_supply"], work["orders_placed"])

    allocated = int(work["available_supply"].sum())
    remaining = int(capacity_cases - allocated)
    if remaining > 0:
        work["gap"] = work["orders_placed"] - work["available_supply"]
        work = work.sort_values(["priority_score", "gap"], ascending=[False, False]).reset_index(drop=True)
        idx = 0
        while remaining > 0:
            if idx >= len(work):
                idx = 0
            if work.loc[idx, "gap"] > 0:
                work.loc[idx, "available_supply"] += 1
                work.loc[idx, "gap"] -= 1
                remaining -= 1
            idx += 1
    elif remaining < 0:
        work = work.sort_values(["priority_score", "available_supply"], ascending=[True, False]).reset_index(drop=True)
        idx = 0
        while remaining < 0:
            if idx >= len(work):
                idx = 0
            if work.loc[idx, "available_supply"] > 0:
                work.loc[idx, "available_supply"] -= 1
                remaining += 1
            idx += 1

    work["available_supply"] = work["available_supply"].astype(int)
    return work


def build_dataset(scenario: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(scenario["seed"])

    sku_base = {
        sku: int(rng.integers(150, 420)) + idx * 18
        for idx, sku in enumerate(SKUS)
    }
    sku_revenue = {
        sku: round(float(rng.uniform(6.5, 18.0) + (0.7 if idx >= 8 else 0)), 2)
        for idx, sku in enumerate(SKUS)
    }
    revenue_weight_map = {
        sku: sku_revenue[sku] / sum(sku_revenue.values())
        for sku in SKUS
    }
    retailer_share = {"RET_A": 0.31, "RET_B": 0.27, "RET_C": 0.23, "RET_D": 0.19}

    historical_promos = [
        ("RET_A", "ALL", 5, 7, "FEATURE", 1.32),
        ("RET_C", "SKU_03", 8, 9, "DISPLAY", 1.25),
    ]
    future_promos = scenario["future_promos"]
    all_promos = historical_promos + future_promos

    rows = []
    for week in HISTORY_WEEKS + FUTURE_WEEKS:
        for sku in SKUS:
            for retailer in RETAILERS:
                promo_flag, uplift = promo_lookup(all_promos, retailer, sku, week)
                order_noise = float(rng.normal(1.0, 0.06))
                retailer_multiplier = {"RET_A": 1.05, "RET_B": 0.98, "RET_C": 0.93, "RET_D": 0.88}[retailer]
                sku_multiplier = 1.0 + (0.05 if sku in {"SKU_09", "SKU_10", "SKU_11", "SKU_12"} else 0.0)
                orders = sku_base[sku] * retailer_share[retailer] * retailer_multiplier * sku_multiplier * seasonal_factor(week) * uplift * order_noise
                orders_placed = max(25, int(round(orders)))
                priority = priority_multiplier(
                    scenario,
                    retailer,
                    sku,
                    week,
                    promo_flag,
                    sku_revenue[sku],
                )
                rows.append(
                    {
                        "week": week,
                        "sku": sku,
                        "retailer": retailer,
                        "orders_placed": orders_placed,
                        "promo_flag": promo_flag,
                        "promo_uplift": round(uplift, 2),
                        "revenue_per_case": sku_revenue[sku],
                        "priority_multiplier": priority,
                        "revenue_weight": round(revenue_weight_map[sku], 6),
                    }
                )

    full = pd.DataFrame(rows)
    full["unit_value"] = full["revenue_per_case"] * full["priority_multiplier"]

    history = full[full["week"].isin(HISTORY_WEEKS)].copy()
    history_parts = []
    for week, week_df in history.groupby("week", sort=True):
        shortage = 0.91 if week not in {4, 8, 11} else 0.78
        capacity = float(week_df["orders_placed"].sum()) * shortage
        allocated = allocate_history_week(week_df, capacity)
        allocated["capacity_cases"] = int(round(capacity))
        allocated["fill_rate"] = (
            allocated["shipments"] / allocated["orders_placed"].clip(lower=1)
        ).round(4)
        history_parts.append(allocated)
    history = pd.concat(history_parts, ignore_index=True)

    future = full[full["week"].isin(FUTURE_WEEKS)].copy()
    caps = []
    for idx, week in enumerate(FUTURE_WEEKS):
        week_df = future[future["week"] == week]
        total_orders = float(week_df["orders_placed"].sum())
        caps.append(
            {
                "week": week,
                "capacity_cases": int(round(total_orders * scenario["future_capacity_factors"][idx])),
            }
        )
    capacity = pd.DataFrame(caps)

    promo_rows = []
    for retailer, sku, start, end, promo_type, uplift in all_promos:
        promo_rows.append(
            {
                "retailer": retailer,
                "sku": sku,
                "week_start": start,
                "week_end": end,
                "promo_type": promo_type,
                "uplift_factor": uplift,
            }
        )
    promo_calendar = pd.DataFrame(promo_rows)

    future_visible = future[
        [
            "week",
            "sku",
            "retailer",
            "orders_placed",
            "promo_flag",
            "promo_uplift",
            "revenue_per_case",
            "revenue_weight",
            "priority_multiplier",
            "unit_value",
        ]
    ].copy()
    future_visible = future_visible.merge(capacity, on="week", how="left")

    hidden_parts = []
    for week, week_df in future_visible.groupby("week", sort=True):
        cap = int(capacity.loc[capacity["week"] == week, "capacity_cases"].iloc[0])
        hidden_parts.append(allocate_hidden_supply(week_df, cap, rng))
    hidden = pd.concat(hidden_parts, ignore_index=True)

    holdout = hidden.rename(columns={"orders_placed": "true_demand"})[
        [
            "week",
            "sku",
            "retailer",
            "true_demand",
            "available_supply",
            "revenue_weight",
            "revenue_per_case",
            "capacity_cases",
        ]
    ].copy()

    history_out = history[
        [
            "week",
            "sku",
            "retailer",
            "orders_placed",
            "shipments",
            "fill_rate",
            "promo_flag",
            "promo_uplift",
            "revenue_per_case",
            "revenue_weight",
            "priority_multiplier",
        ]
    ].copy()
    return history_out, future_visible, capacity, promo_calendar, holdout


def instruction_text(scenario: dict) -> str:
    return f'''# Seasonal Peak Allocation Task

## Scenario
{scenario["title"]}

{scenario["description"]}

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
  {{
    "week": 13,
    "sku": "SKU_01",
    "retailer": "RET_A",
    "recommended_qty": 123
  }}
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
'''


def write_task(task_root: Path, scenario: dict, history: pd.DataFrame, future: pd.DataFrame, capacity: pd.DataFrame, promo: pd.DataFrame, holdout: pd.DataFrame) -> None:
    env_files = task_root / "environment" / "files"
    tests_dir = task_root / "tests"
    env_dir = task_root / "environment"

    env_files.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    (task_root / "instruction.md").write_text(instruction_text(scenario), encoding="utf-8")
    (task_root / "task.toml").write_text(
        TASK_TOML.format(task_name=scenario["slug"], description=scenario["description"].replace('"', "'")),
        encoding="utf-8",
    )
    (tests_dir / "test.sh").write_text(TEST_SH, encoding="utf-8")
    (tests_dir / "test.py").write_text(TEST_PY, encoding="utf-8")
    (env_dir / "Dockerfile").write_text(ENV_DOCKERFILE, encoding="utf-8")

    history.to_csv(env_files / "train_history.csv", index=False)
    future.to_csv(env_files / "future_orders.csv", index=False)
    capacity.to_csv(env_files / "capacity_schedule.csv", index=False)
    promo.to_csv(env_files / "promo_calendar.csv", index=False)
    holdout.to_csv(tests_dir / "holdout_actuals.csv", index=False)

    scenario_notes = {
        "slug": scenario["slug"],
        "title": scenario["title"],
        "description": scenario["description"],
        "seed": scenario["seed"],
    }
    (env_files / "scenario_notes.json").write_text(
        json.dumps(scenario_notes, indent=2),
        encoding="utf-8",
    )


def write_split(
    *,
    split_name: str,
    scenarios: list[dict],
    tasks_dir: Path,
    data_dir: Path,
) -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for scenario in scenarios:
        task_root = tasks_dir / scenario["slug"]
        if task_root.exists():
            shutil.rmtree(task_root)

        history, future, capacity, promo, holdout = build_dataset(scenario)
        write_task(task_root, scenario, history, future, capacity, promo, holdout)

        scenario_dir = data_dir / scenario["slug"]
        if scenario_dir.exists():
            shutil.rmtree(scenario_dir)
        scenario_dir.mkdir(parents=True, exist_ok=True)
        history.to_csv(scenario_dir / "train_history.csv", index=False)
        future.to_csv(scenario_dir / "future_orders.csv", index=False)
        capacity.to_csv(scenario_dir / "capacity_schedule.csv", index=False)
        promo.to_csv(scenario_dir / "promo_calendar.csv", index=False)
        holdout.to_csv(scenario_dir / "holdout_actuals.csv", index=False)

        manifest.append(
            {
                "benchmark_split": split_name,
                "task_name": f"supply-chain/{scenario['slug']}",
                "slug": scenario["slug"],
                "title": scenario["title"],
                "description": scenario["description"],
                "seed": scenario["seed"],
            }
        )

    (data_dir / "benchmark_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(f"Generated {len(manifest)} {split_name} tasks in {tasks_dir}")


def main() -> None:
    args = parse_args()

    if args.split in {"dev", "all"}:
        write_split(
            split_name="dev",
            scenarios=SCENARIOS,
            tasks_dir=args.dev_tasks_dir,
            data_dir=args.data_dir / "dev",
        )

    if args.split in {"eval", "all"}:
        write_split(
            split_name="eval",
            scenarios=build_eval_scenarios(),
            tasks_dir=args.eval_tasks_dir,
            data_dir=args.data_dir / "eval",
        )


if __name__ == "__main__":
    main()
