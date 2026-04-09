from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_PATH = ROOT / "results.tsv"
DEFAULT_RESULTS_DETAILED_PATH = ROOT / "results_detailed.tsv"
DEFAULT_PNG_PATH = ROOT / "artifacts" / "plots" / "progress.png"
DEFAULT_SVG_PATH = ROOT / "artifacts" / "plots" / "progress.svg"
DEFAULT_BEST_PNG_PATH = ROOT / "artifacts" / "plots" / "best_so_far.png"
DEFAULT_BEST_SVG_PATH = ROOT / "artifacts" / "plots" / "best_so_far.svg"
DEFAULT_EFFICIENCY_PNG_PATH = ROOT / "artifacts" / "plots" / "efficiency.png"
DEFAULT_EFFICIENCY_SVG_PATH = ROOT / "artifacts" / "plots" / "efficiency.svg"
DEFAULT_DELTA_PNG_PATH = ROOT / "artifacts" / "plots" / "per_task_delta.png"
DEFAULT_DELTA_SVG_PATH = ROOT / "artifacts" / "plots" / "per_task_delta.svg"
DEFAULT_DASHBOARD_MD_PATH = ROOT / "artifacts" / "reports" / "benchmark_dashboard.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate benchmark progress visuals and a markdown dashboard from results.tsv."
    )
    parser.add_argument("--results-path", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--results-detailed-path", type=Path, default=DEFAULT_RESULTS_DETAILED_PATH)
    parser.add_argument("--png-path", type=Path, default=DEFAULT_PNG_PATH)
    parser.add_argument("--svg-path", type=Path, default=DEFAULT_SVG_PATH)
    parser.add_argument("--best-png-path", type=Path, default=DEFAULT_BEST_PNG_PATH)
    parser.add_argument("--best-svg-path", type=Path, default=DEFAULT_BEST_SVG_PATH)
    parser.add_argument("--efficiency-png-path", type=Path, default=DEFAULT_EFFICIENCY_PNG_PATH)
    parser.add_argument("--efficiency-svg-path", type=Path, default=DEFAULT_EFFICIENCY_SVG_PATH)
    parser.add_argument("--delta-png-path", type=Path, default=DEFAULT_DELTA_PNG_PATH)
    parser.add_argument("--delta-svg-path", type=Path, default=DEFAULT_DELTA_SVG_PATH)
    parser.add_argument("--dashboard-md-path", type=Path, default=DEFAULT_DASHBOARD_MD_PATH)
    return parser.parse_args()


def save_outputs(fig: plt.Figure, png_path: Path, svg_path: Path) -> None:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(svg_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def render_placeholder(png_path: Path, svg_path: Path, title: str, subtitle: str) -> None:
    fig = plt.figure(figsize=(14, 8), dpi=180, facecolor="#08111f")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0f1b2d")
    ax.axis("off")
    ax.text(0.5, 0.56, title, ha="center", va="center", fontsize=28, color="white", fontweight="bold")
    ax.text(0.5, 0.44, subtitle, ha="center", va="center", fontsize=13, color="#a9b7c9")
    save_outputs(fig, png_path, svg_path)


def load_results(results_path: Path) -> pd.DataFrame:
    if not results_path.exists() or not results_path.read_text(encoding="utf-8-sig").strip():
        return pd.DataFrame()

    df = pd.read_csv(results_path, sep="\t", encoding="utf-8-sig")
    if df.empty:
        return df

    if "benchmark_scope" not in df.columns:
        passed_text = df.get("passed", pd.Series(dtype=str)).fillna("").astype(str)
        denominator = pd.to_numeric(passed_text.str.split("/", n=1, expand=True).get(1), errors="coerce")
        df["benchmark_scope"] = np.where(denominator > 1, "full", "smoke")

    for column in ["avg_score", "avg_turns", "avg_input_tokens", "avg_output_tokens", "cost_usd"]:
        df[column] = pd.to_numeric(df.get(column), errors="coerce")

    passed_parts = df.get("passed", pd.Series(dtype=str)).fillna("").astype(str).str.split("/", n=1, expand=True)
    if len(passed_parts.columns) >= 2:
        df["passed_num"] = pd.to_numeric(passed_parts[0], errors="coerce")
        df["passed_den"] = pd.to_numeric(passed_parts[1], errors="coerce")
        df["passed_rate"] = df["passed_num"] / df["passed_den"].replace({0: np.nan})
    else:
        df["passed_num"] = np.nan
        df["passed_den"] = np.nan
        df["passed_rate"] = np.nan

    df = df[df["avg_score"].notna()].copy()
    df["run_index"] = np.arange(1, len(df) + 1)
    df["is_full"] = df["benchmark_scope"].eq("full")
    return df


def load_detailed(results_detailed_path: Path) -> pd.DataFrame:
    if not results_detailed_path.exists() or not results_detailed_path.read_text(encoding="utf-8-sig").strip():
        return pd.DataFrame()
    df = pd.read_csv(results_detailed_path, sep="\t", encoding="utf-8-sig")
    if df.empty:
        return df
    for column in ["score", "turns", "input_tokens", "output_tokens", "cost_usd"]:
        df[column] = pd.to_numeric(df.get(column), errors="coerce")
    return df


def compare_rows(candidate: pd.Series, incumbent: pd.Series) -> int:
    if int(candidate.get("passed_num", 0)) != int(incumbent.get("passed_num", 0)):
        return 1 if int(candidate.get("passed_num", 0)) > int(incumbent.get("passed_num", 0)) else -1
    if abs(float(candidate.get("avg_score", 0.0)) - float(incumbent.get("avg_score", 0.0))) > 1e-12:
        return 1 if float(candidate.get("avg_score", 0.0)) > float(incumbent.get("avg_score", 0.0)) else -1
    cand_turns = candidate.get("avg_turns")
    inc_turns = incumbent.get("avg_turns")
    if pd.notna(cand_turns) and pd.notna(inc_turns) and abs(float(cand_turns) - float(inc_turns)) > 1e-12:
        return 1 if float(cand_turns) < float(inc_turns) else -1
    cand_input = candidate.get("avg_input_tokens")
    inc_input = incumbent.get("avg_input_tokens")
    if pd.notna(cand_input) and pd.notna(inc_input) and abs(float(cand_input) - float(inc_input)) > 1e-12:
        return 1 if float(cand_input) < float(inc_input) else -1
    return 0


def choose_best_rows(df_full: pd.DataFrame) -> tuple[pd.Series, list[int]]:
    best = df_full.iloc[0]
    best_indices = [int(best["run_index"])]
    for _, row in df_full.iloc[1:].iterrows():
        if compare_rows(row, best) > 0:
            best = row
        best_indices.append(int(best["run_index"]))
    return best, best_indices


def render_progress(df_full: pd.DataFrame, png_path: Path, svg_path: Path) -> None:
    fig = plt.figure(figsize=(15, 9), dpi=180, facecolor="#08111f")
    gs = fig.add_gridspec(2, 3, height_ratios=[4.8, 1.4], hspace=0.28, wspace=0.18)
    ax = fig.add_subplot(gs[0, :])
    cards = [fig.add_subplot(gs[1, i]) for i in range(3)]
    ax.set_facecolor("#0f1b2d")

    x = df_full["run_index"].to_numpy()
    y = df_full["avg_score"].to_numpy()
    _, frontier = choose_best_rows(df_full)

    ax.plot(x, y, color="#54c7ec", linewidth=3.0, marker="o", markersize=8, markeredgecolor="white", markeredgewidth=1.2, zorder=3, label="Raw avg score")
    ax.plot(x, frontier, color="#ffd166", linewidth=2.6, linestyle="--", zorder=2, label="Best-so-far")
    ax.fill_between(x, y, 0, color="#54c7ec", alpha=0.12, zorder=1)

    ax2 = ax.twinx()
    ax2.set_facecolor("none")
    ax2.plot(x, df_full["passed_rate"].to_numpy(), color="#7ef29a", linewidth=2.0, linestyle=":", marker="s", markersize=6, alpha=0.9, label="Pass rate")
    ax2.set_ylim(0, 1.05)
    ax2.set_ylabel("Pass rate", color="#c7d7e6", fontsize=11)
    ax2.tick_params(colors="#c7d7e6")
    for spine in ax2.spines.values():
        spine.set_visible(False)

    baseline = df_full.iloc[0]
    latest = df_full.iloc[-1]
    best = df_full.loc[df_full["avg_score"].idxmax()]
    delta = float(latest["avg_score"] - baseline["avg_score"])

    ax.scatter([best["run_index"]], [best["avg_score"]], s=180, color="#ffd166", edgecolor="white", linewidth=1.4, zorder=4)
    ax.annotate(f"Latest {latest['avg_score']:.3f}\n{int(latest['passed_num'])}/{int(latest['passed_den'])} passed", xy=(latest["run_index"], latest["avg_score"]), xytext=(-12, 18), textcoords="offset points", ha="right", fontsize=10, color="white", bbox=dict(boxstyle="round,pad=0.35", fc="#16263b", ec="#54c7ec", alpha=0.96))
    ax.annotate(f"{delta:+.3f} vs baseline", xy=(latest["run_index"], latest["avg_score"]), xytext=(-10, -32), textcoords="offset points", ha="right", fontsize=10.5, color="#7ef29a" if delta >= 0 else "#ff7b7b", bbox=dict(boxstyle="round,pad=0.35", fc="#16263b", ec="#7ef29a" if delta >= 0 else "#ff7b7b", alpha=0.95))

    ymin = max(0.0, float(df_full["avg_score"].min()) - 0.08)
    ymax = min(1.0, max(float(df_full["avg_score"].max()), max(frontier)) + 0.08)
    if ymax - ymin < 0.15:
        center = (ymax + ymin) / 2
        ymin = max(0.0, center - 0.08)
        ymax = min(1.0, center + 0.08)
    ax.set_ylim(ymin, ymax)
    ax.set_xlim(1, max(len(df_full), 2))
    ax.set_xticks(x)
    ax.set_xlabel("Full benchmark run", color="white", fontsize=12)
    ax.set_ylabel("Average score", color="white", fontsize=12)
    ax.tick_params(colors="#dbe7f3", labelsize=11)
    ax.grid(True, axis="y", alpha=0.18, color="white", linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_color("#2a3d55")

    fig.suptitle("Supply Chain AutoAgent ? Full Benchmark Progress", fontsize=24, fontweight="bold", color="white", x=0.06, y=0.97, ha="left")
    ax.set_title("Raw run score, best-so-far frontier, and pass-rate overlay", fontsize=13, color="#b8c7d9", loc="left", pad=12)
    fig.text(0.06, 0.915, f"Model profile: {latest.get('model_profile', 'unknown')}    |    Total full runs: {len(df_full)}", color="#8fb3d9", fontsize=12)

    card_specs = [
        ("Baseline", f"{baseline['avg_score']:.3f}", "#54c7ec", str(baseline.get("description", ""))[:54]),
        ("Latest", f"{latest['avg_score']:.3f}", "#7ef29a", str(latest.get("description", ""))[:54]),
        ("Best", f"{best['avg_score']:.3f}", "#ffd166", f"Run #{int(best['run_index'])}"),
    ]
    for ax_card, (label, value, accent, subtitle) in zip(cards, card_specs, strict=True):
        ax_card.set_facecolor("#0f1b2d")
        ax_card.set_xticks([])
        ax_card.set_yticks([])
        for spine in ax_card.spines.values():
            spine.set_color("#22344b")
        ax_card.axhline(0.98, color=accent, linewidth=5, alpha=0.95)
        ax_card.text(0.06, 0.68, label, transform=ax_card.transAxes, color="#9fb4ca", fontsize=12)
        ax_card.text(0.06, 0.35, value, transform=ax_card.transAxes, color="white", fontsize=28, fontweight="bold")
        ax_card.text(0.06, 0.12, subtitle, transform=ax_card.transAxes, color="#6f879f", fontsize=10)

    fig.text(0.06, 0.03, "Use this as the public chart: comparable full benchmark runs only.", color="#6f879f", fontsize=10)
    save_outputs(fig, png_path, svg_path)


def render_best_so_far(df_full: pd.DataFrame, png_path: Path, svg_path: Path) -> None:
    fig = plt.figure(figsize=(14, 8), dpi=180, facecolor="#08111f")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0f1b2d")
    x = df_full["run_index"].to_numpy()
    _, frontier = choose_best_rows(df_full)
    ax.plot(x, frontier, color="#ffd166", linewidth=3.2, marker="o", markersize=8, markeredgecolor="white", markeredgewidth=1.2)
    ax.fill_between(x, frontier, 0, color="#ffd166", alpha=0.15)
    latest_frontier = frontier[-1]
    ax.annotate(f"Best so far\n{latest_frontier:.3f}", xy=(x[-1], latest_frontier), xytext=(-18, 18), textcoords="offset points", ha="right", fontsize=11, color="white", bbox=dict(boxstyle="round,pad=0.35", fc="#16263b", ec="#ffd166", alpha=0.96))
    ax.set_xlim(1, max(len(df_full), 2))
    ax.set_xticks(x)
    ax.set_xlabel("Full benchmark run", color="white", fontsize=12)
    ax.set_ylabel("Best-so-far avg score", color="white", fontsize=12)
    ax.tick_params(colors="#dbe7f3", labelsize=11)
    ax.grid(True, axis="y", alpha=0.18, color="white")
    for spine in ax.spines.values():
        spine.set_color("#2a3d55")
    fig.suptitle("Supply Chain AutoAgent ? Best-So-Far Frontier", fontsize=24, fontweight="bold", color="white", x=0.06, y=0.96, ha="left")
    ax.set_title("This is the cleanest ""is the harness improving?"" visualization", fontsize=12.5, color="#b8c7d9", loc="left", pad=12)
    save_outputs(fig, png_path, svg_path)


def render_efficiency(df_full: pd.DataFrame, png_path: Path, svg_path: Path) -> None:
    fig = plt.figure(figsize=(14, 8), dpi=180, facecolor="#08111f")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0f1b2d")
    data = df_full.dropna(subset=["avg_input_tokens", "avg_score"]).copy()
    if data.empty:
        render_placeholder(png_path, svg_path, "No efficiency data yet", "Need runs with token metrics to draw efficiency trade-offs.")
        return
    sizes = np.where(data["avg_turns"].notna(), data["avg_turns"] * 35, 180)
    scatter = ax.scatter(data["avg_input_tokens"], data["avg_score"], s=sizes, c=data["run_index"], cmap="viridis", alpha=0.9, edgecolor="white", linewidth=1.0)
    for _, row in data.iterrows():
        ax.annotate(str(int(row["run_index"])), (row["avg_input_tokens"], row["avg_score"]), xytext=(8, 8), textcoords="offset points", color="white", fontsize=10)
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Run index", color="white")
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')
    ax.set_xlabel("Average input tokens", color="white", fontsize=12)
    ax.set_ylabel("Average score", color="white", fontsize=12)
    ax.tick_params(colors="#dbe7f3", labelsize=11)
    ax.grid(True, alpha=0.15, color="white")
    for spine in ax.spines.values():
        spine.set_color("#2a3d55")
    fig.suptitle("Supply Chain AutoAgent ? Efficiency Trade-off", fontsize=24, fontweight="bold", color="white", x=0.06, y=0.96, ha="left")
    ax.set_title("Lower-left is cheaper; upper-left is better. Bubble size tracks avg turns.", fontsize=12.5, color="#b8c7d9", loc="left", pad=12)
    save_outputs(fig, png_path, svg_path)


def build_per_task_delta(detailed: pd.DataFrame, df_full: pd.DataFrame) -> tuple[pd.DataFrame | None, pd.Series | None, pd.Series | None]:
    if detailed.empty or len(df_full) < 2:
        return None, None, None
    latest = df_full.iloc[-1]
    prior = df_full.iloc[:-1].copy()
    if prior.empty:
        return None, None, None
    incumbent = prior.iloc[0]
    for _, row in prior.iloc[1:].iterrows():
        if compare_rows(row, incumbent) > 0:
            incumbent = row

    latest_job = extract_job_name(latest.get("description", ""))
    inc_job = extract_job_name(incumbent.get("description", ""))
    if not latest_job or not inc_job:
        return None, latest, incumbent

    d_latest = detailed[detailed["job_name"] == latest_job][["task_name", "score"]].rename(columns={"score": "latest_score"})
    d_inc = detailed[detailed["job_name"] == inc_job][["task_name", "score"]].rename(columns={"score": "incumbent_score"})
    merged = d_inc.merge(d_latest, on="task_name", how="outer")
    if merged.empty:
        return None, latest, incumbent
    merged["delta"] = merged["latest_score"].fillna(0) - merged["incumbent_score"].fillna(0)
    merged = merged.sort_values("delta")
    return merged, latest, incumbent


def extract_job_name(description: str) -> str | None:
    import re
    match = re.search(r"\bjob=([^\s|]+)", str(description))
    return match.group(1) if match else None


def render_per_task_delta(merged: pd.DataFrame | None, latest: pd.Series | None, incumbent: pd.Series | None, png_path: Path, svg_path: Path) -> None:
    if merged is None or latest is None or incumbent is None:
        render_placeholder(png_path, svg_path, "No per-task delta view yet", "Need at least two full runs plus results_detailed.tsv.")
        return
    fig = plt.figure(figsize=(15, 9), dpi=180, facecolor="#08111f")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0f1b2d")
    colors = ["#7ef29a" if x >= 0 else "#ff7b7b" for x in merged["delta"]]
    ax.barh(merged["task_name"], merged["delta"], color=colors, alpha=0.9)
    ax.axvline(0, color="white", linewidth=1.0, alpha=0.6)
    for i, (_, row) in enumerate(merged.iterrows()):
        ax.text(float(row["delta"]) + (0.003 if row["delta"] >= 0 else -0.003), i, f"{row['delta']:+.3f}", va="center", ha="left" if row["delta"] >= 0 else "right", color="white", fontsize=10)
    ax.set_xlabel("Latest score minus incumbent score", color="white", fontsize=12)
    ax.set_ylabel("Task", color="white", fontsize=12)
    ax.tick_params(colors="#dbe7f3", labelsize=11)
    for spine in ax.spines.values():
        spine.set_color("#2a3d55")
    fig.suptitle("Supply Chain AutoAgent ? Per-Task Delta", fontsize=24, fontweight="bold", color="white", x=0.06, y=0.96, ha="left")
    ax.set_title(f"Latest job {extract_job_name(latest.get('description', ''))} vs incumbent {extract_job_name(incumbent.get('description', ''))}", fontsize=12.5, color="#b8c7d9", loc="left", pad=12)
    save_outputs(fig, png_path, svg_path)


def write_dashboard(df_full: pd.DataFrame, detailed: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if df_full.empty:
        path.write_text("# Benchmark dashboard\n\nNo full runs logged yet.\n", encoding="utf-8")
        return
    latest = df_full.iloc[-1]
    best = df_full.iloc[0]
    for _, row in df_full.iloc[1:].iterrows():
        if compare_rows(row, best) > 0:
            best = row
    merged, _, incumbent = build_per_task_delta(detailed, df_full)
    lines = [
        "# Benchmark dashboard",
        "",
        f"- total full runs: **{len(df_full)}**",
        f"- latest run: **run #{int(latest['run_index'])}** ? avg_score **{latest['avg_score']:.6f}**, passed **{int(latest['passed_num'])}/{int(latest['passed_den'])}**",
        f"- best run by policy: **run #{int(best['run_index'])}** ? avg_score **{best['avg_score']:.6f}**, passed **{int(best['passed_num'])}/{int(best['passed_den'])}**",
        f"- latest avg_turns: **{latest.get('avg_turns')}**",
        f"- latest avg_input_tokens: **{latest.get('avg_input_tokens')}**",
        "",
        "## Visuals",
        "- `progress.png` / `progress.svg` ? main full-run chart",
        "- `best_so_far.png` / `best_so_far.svg` ? monotonic improvement frontier",
        "- `efficiency.png` / `efficiency.svg` ? score vs token/turn trade-off",
        "- `per_task_delta.png` / `per_task_delta.svg` ? latest vs incumbent per-task deltas",
        "",
        "## Full run ledger",
    ]
    for _, row in df_full.iterrows():
        lines.append(
            f"- run #{int(row['run_index'])}: score={row['avg_score']:.6f}, passed={int(row['passed_num'])}/{int(row['passed_den'])}, status={row.get('status', '')}, description={row.get('description', '')}"
        )
    if merged is not None and incumbent is not None:
        lines.extend(["", "## Largest latest deltas vs incumbent"])
        top_pos = merged.sort_values("delta", ascending=False).head(3)
        top_neg = merged.sort_values("delta", ascending=True).head(3)
        lines.append("### Improvements")
        for _, row in top_pos.iterrows():
            lines.append(f"- {row['task_name']}: {row['delta']:+.4f}")
        lines.append("### Regressions")
        for _, row in top_neg.iterrows():
            lines.append(f"- {row['task_name']}: {row['delta']:+.4f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    df = load_results(args.results_path)
    detailed = load_detailed(args.results_detailed_path)
    df_full = df[df["benchmark_scope"] == "full"].copy() if not df.empty else pd.DataFrame()
    if not df_full.empty:
        df_full["run_index"] = np.arange(1, len(df_full) + 1)

    if df_full.empty:
        render_placeholder(args.png_path, args.svg_path, "No full benchmark runs yet", "Run scripts/run_benchmark.py to populate results.tsv.")
        render_placeholder(args.best_png_path, args.best_svg_path, "No best-so-far view yet", "Need at least one full benchmark run.")
        render_placeholder(args.efficiency_png_path, args.efficiency_svg_path, "No efficiency view yet", "Need at least one full benchmark run with token metrics.")
        render_placeholder(args.delta_png_path, args.delta_svg_path, "No per-task delta view yet", "Need at least two full runs plus results_detailed.tsv.")
        write_dashboard(df_full, detailed, args.dashboard_md_path)
        print(f"Wrote {args.png_path} and {args.svg_path}")
        return

    render_progress(df_full, args.png_path, args.svg_path)
    render_best_so_far(df_full, args.best_png_path, args.best_svg_path)
    render_efficiency(df_full, args.efficiency_png_path, args.efficiency_svg_path)
    merged, latest, incumbent = build_per_task_delta(detailed, df_full)
    render_per_task_delta(merged, latest, incumbent, args.delta_png_path, args.delta_svg_path)
    write_dashboard(df_full, detailed, args.dashboard_md_path)
    print(
        "Wrote "
        f"{args.png_path}, {args.svg_path}, {args.best_png_path}, {args.best_svg_path}, "
        f"{args.efficiency_png_path}, {args.efficiency_svg_path}, {args.delta_png_path}, {args.delta_svg_path}, {args.dashboard_md_path}"
    )


if __name__ == "__main__":
    main()
