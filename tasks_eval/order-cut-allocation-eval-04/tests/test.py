from __future__ import annotations

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
