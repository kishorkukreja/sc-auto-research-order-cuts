from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_PATH = ROOT / "results.tsv"
DEFAULT_PNG_PATH = ROOT / "progress.png"
DEFAULT_SVG_PATH = ROOT / "progress.svg"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a run-history progress chart from results.tsv."
    )
    parser.add_argument(
        "--results-path",
        type=Path,
        default=DEFAULT_RESULTS_PATH,
        help="Path to results.tsv",
    )
    parser.add_argument(
        "--png-path",
        type=Path,
        default=DEFAULT_PNG_PATH,
        help="Output PNG path",
    )
    parser.add_argument(
        "--svg-path",
        type=Path,
        default=DEFAULT_SVG_PATH,
        help="Output SVG path",
    )
    return parser.parse_args()


def load_results(results_path: Path) -> pd.DataFrame:
    if not results_path.exists() or not results_path.read_text(encoding="utf-8-sig").strip():
        return pd.DataFrame()

    df = pd.read_csv(results_path, sep="\t", encoding="utf-8-sig")
    if df.empty:
        return df

    df["avg_score"] = pd.to_numeric(df.get("avg_score"), errors="coerce")
    df["avg_turns"] = pd.to_numeric(df.get("avg_turns"), errors="coerce")
    df["avg_input_tokens"] = pd.to_numeric(df.get("avg_input_tokens"), errors="coerce")
    df["avg_output_tokens"] = pd.to_numeric(df.get("avg_output_tokens"), errors="coerce")
    df["cost_usd"] = pd.to_numeric(df.get("cost_usd"), errors="coerce")

    passed_parts = df.get("passed", pd.Series(dtype=str)).fillna("").astype(str).str.split("/", n=1, expand=True)
    if len(passed_parts.columns) >= 2:
        df["passed_num"] = pd.to_numeric(passed_parts[0], errors="coerce")
        df["passed_den"] = pd.to_numeric(passed_parts[1], errors="coerce")
        df["passed_rate"] = df["passed_num"] / df["passed_den"].replace({0: np.nan})
    else:
        df["passed_rate"] = np.nan

    df = df[df["avg_score"].notna()].copy()
    df["run_index"] = np.arange(1, len(df) + 1)
    return df


def render_placeholder(png_path: Path, svg_path: Path) -> None:
    fig = plt.figure(figsize=(14, 8), dpi=180, facecolor="#08111f")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0f1b2d")
    ax.axis("off")
    ax.text(
        0.5,
        0.56,
        "No runs logged yet",
        ha="center",
        va="center",
        fontsize=30,
        color="white",
        fontweight="bold",
    )
    ax.text(
        0.5,
        0.44,
        "Run scripts/run_benchmark.py to populate results.tsv and generate progress visuals.",
        ha="center",
        va="center",
        fontsize=14,
        color="#a9b7c9",
    )
    save_outputs(fig, png_path, svg_path)


def save_outputs(fig: plt.Figure, png_path: Path, svg_path: Path) -> None:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(svg_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def render_chart(df: pd.DataFrame, png_path: Path, svg_path: Path) -> None:
    fig = plt.figure(figsize=(15, 9), dpi=180, facecolor="#08111f")
    gs = fig.add_gridspec(2, 3, height_ratios=[4.8, 1.4], hspace=0.28, wspace=0.18)

    ax = fig.add_subplot(gs[0, :])
    cards = [fig.add_subplot(gs[1, i]) for i in range(3)]

    ax.set_facecolor("#0f1b2d")
    x = df["run_index"].to_numpy()
    y = df["avg_score"].to_numpy()

    ax.plot(
        x,
        y,
        color="#54c7ec",
        linewidth=3.0,
        marker="o",
        markersize=8,
        markerfacecolor="#54c7ec",
        markeredgecolor="white",
        markeredgewidth=1.4,
        zorder=3,
    )
    ax.fill_between(x, y, 0, color="#54c7ec", alpha=0.12, zorder=1)

    if df["passed_rate"].notna().any():
        ax2 = ax.twinx()
        ax2.set_facecolor("none")
        ax2.plot(
            x,
            df["passed_rate"].to_numpy(),
            color="#7ef29a",
            linewidth=2.2,
            linestyle="--",
            marker="s",
            markersize=6,
            alpha=0.9,
            zorder=2,
        )
        ax2.set_ylim(0, 1.05)
        ax2.set_ylabel("Pass rate", color="#c7d7e6", fontsize=11)
        ax2.tick_params(colors="#c7d7e6")
        for spine in ax2.spines.values():
            spine.set_visible(False)

    best_idx = int(df["avg_score"].idxmax())
    best_row = df.loc[best_idx]
    latest_row = df.iloc[-1]
    baseline_row = df.iloc[0]
    delta = float(latest_row["avg_score"] - baseline_row["avg_score"])

    ax.scatter(
        [best_row["run_index"]],
        [best_row["avg_score"]],
        s=180,
        color="#ffd166",
        edgecolor="white",
        linewidth=1.5,
        zorder=4,
    )
    ax.annotate(
        f"Best run #{int(best_row['run_index'])}\n{best_row['avg_score']:.3f}",
        xy=(best_row["run_index"], best_row["avg_score"]),
        xytext=(12, 18),
        textcoords="offset points",
        fontsize=11,
        color="white",
        bbox=dict(boxstyle="round,pad=0.45", fc="#16263b", ec="#ffd166", alpha=0.95),
        arrowprops=dict(arrowstyle="->", color="#ffd166", lw=1.4),
    )

    if len(df) > 1:
        ax.annotate(
            f"{delta:+.3f} vs baseline",
            xy=(latest_row["run_index"], latest_row["avg_score"]),
            xytext=(-10, -32),
            textcoords="offset points",
            ha="right",
            fontsize=11,
            color="#7ef29a" if delta >= 0 else "#ff7b7b",
            bbox=dict(
                boxstyle="round,pad=0.35",
                fc="#16263b",
                ec="#7ef29a" if delta >= 0 else "#ff7b7b",
                alpha=0.95,
            ),
        )

    ax.set_xlim(1, max(len(df), 2))
    ymin = max(0.0, float(df["avg_score"].min()) - 0.08)
    ymax = min(1.0, float(df["avg_score"].max()) + 0.08)
    if ymax - ymin < 0.15:
        center = (ymax + ymin) / 2
        ymin = max(0.0, center - 0.08)
        ymax = min(1.0, center + 0.08)
    ax.set_ylim(ymin, ymax)

    ax.set_xticks(x)
    ax.set_xlabel("Run", color="white", fontsize=12)
    ax.set_ylabel("Average score", color="white", fontsize=12)
    ax.tick_params(colors="#dbe7f3", labelsize=11)
    ax.grid(True, axis="y", alpha=0.18, color="white", linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_color("#2a3d55")

    fig.suptitle(
        "Supply Chain AutoAgent — Score Progress Across Runs",
        fontsize=24,
        fontweight="bold",
        color="white",
        x=0.06,
        y=0.97,
        ha="left",
    )
    ax.set_title(
        "Average score per benchmark run, with pass-rate overlay",
        fontsize=13,
        color="#b8c7d9",
        loc="left",
        pad=12,
    )

    profile = str(latest_row.get("model_profile", "")).strip() or "unknown"
    fig.text(
        0.06,
        0.915,
        f"Model profile: {profile}    |    Total runs: {len(df)}",
        color="#8fb3d9",
        fontsize=12,
    )

    card_specs = [
        ("Baseline", f"{baseline_row['avg_score']:.3f}", "#54c7ec"),
        ("Latest", f"{latest_row['avg_score']:.3f}", "#7ef29a"),
        ("Best", f"{best_row['avg_score']:.3f}", "#ffd166"),
    ]
    subtitles = [
        str(baseline_row.get("description", ""))[:54],
        str(latest_row.get("description", ""))[:54],
        f"Run #{int(best_row['run_index'])}",
    ]

    for ax_card, (label, value, accent), subtitle in zip(cards, card_specs, subtitles, strict=True):
        ax_card.set_facecolor("#0f1b2d")
        ax_card.set_xticks([])
        ax_card.set_yticks([])
        for spine in ax_card.spines.values():
            spine.set_color("#22344b")
        ax_card.axhline(0.98, color=accent, linewidth=5, alpha=0.95)
        ax_card.text(0.06, 0.68, label, transform=ax_card.transAxes, color="#9fb4ca", fontsize=12)
        ax_card.text(
            0.06,
            0.35,
            value,
            transform=ax_card.transAxes,
            color="white",
            fontsize=28,
            fontweight="bold",
        )
        ax_card.text(0.06, 0.12, subtitle, transform=ax_card.transAxes, color="#6f879f", fontsize=10)

    fig.text(
        0.06,
        0.03,
        "Auto-generated from results.tsv. Suitable for blog screenshots and LinkedIn visuals.",
        color="#6f879f",
        fontsize=10,
    )

    save_outputs(fig, png_path, svg_path)


def main() -> None:
    args = parse_args()
    df = load_results(args.results_path)
    if df.empty:
        render_placeholder(args.png_path, args.svg_path)
    else:
        render_chart(df, args.png_path, args.svg_path)
    print(f"Wrote {args.png_path} and {args.svg_path}")


if __name__ == "__main__":
    main()

