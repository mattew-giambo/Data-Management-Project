"""
visualize_benchmark.py
======================
Reads benchmark_results.csv (produced by benchmark.py) and generates
a multi-panel comparison report saved as PNG figures.

Charts produced:
  1. Grouped bar — Total execution time (RDBMS vs DW) per query
  2. Horizontal bar — DW speedup factor over RDBMS
  3. Grouped bar — SQL verbosity (lines of code) per query
  4. Grouped bar — Query-plan node count (joins + scans + aggregations)
  5. Stacked bar — Planning vs Execution time breakdown (both systems)
  6. Scatter     — Verbosity ratio vs DW speedup (quadrant analysis)
  7. Heatmap     — Normalised metrics comparison matrix

Usage
-----
    python src/visualize_benchmark.py

    # Custom CSV path:
    python src/visualize_benchmark.py --csv path/to/benchmark_results.csv

Output: src/figures/  (one PNG per chart + one combined PDF)
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

# ---------------------------------------------------------------------------
# Style setup
# ---------------------------------------------------------------------------

RDBMS_COLOR = "#4C72B0"   # blue
DW_COLOR    = "#DD8452"   # orange
ACCENT      = "#55A868"   # green (for positive highlights)
NEUTRAL     = "#8C8C8C"

sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams.update({
    "figure.dpi":      150,
    "savefig.dpi":     180,
    "font.family":     "sans-serif",
    "axes.spines.top": False,
    "axes.spines.right": False,
})


# ---------------------------------------------------------------------------
# Data loading & derived columns
# ---------------------------------------------------------------------------

def load_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Short label for x-axis ticks
    df["short_label"] = df["query_id"] + "\n" + df["olap_feature"].str.replace(" ", "\n", n=1)

    # Speedup: how many times faster is DW vs RDBMS (>1 = DW wins)
    df["speedup"] = df["rdbms_total_ms"] / df["dw_total_ms"].replace(0, np.nan)

    # Total plan complexity
    df["rdbms_total_nodes"] = df["rdbms_joins"] + df["rdbms_seq_scans"] + df["rdbms_agg_nodes"]
    df["dw_total_nodes"]    = df["dw_joins"]    + df["dw_seq_scans"]    + df["dw_agg_nodes"]

    return df


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _save(fig: plt.Figure, path: Path, title: str):
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path.name}")


def _grouped_bars(ax, x, left_vals, right_vals, left_label, right_label,
                  left_color, right_color, ylabel, title, fmt="{:.1f}"):
    """Draw a grouped bar chart on ax and annotate each bar."""
    width = 0.38
    positions = np.arange(len(x))

    b1 = ax.bar(positions - width / 2, left_vals,  width,
                label=left_label,  color=left_color,  alpha=0.88, zorder=3)
    b2 = ax.bar(positions + width / 2, right_vals, width,
                label=right_label, color=right_color, alpha=0.88, zorder=3)

    for bar, val in zip(b1, left_vals):
        if pd.notna(val) and val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(left_vals + right_vals) * 0.01,
                    fmt.format(val), ha="center", va="bottom",
                    fontsize=7.5, color=left_color, fontweight="bold")
    for bar, val in zip(b2, right_vals):
        if pd.notna(val) and val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(left_vals + right_vals) * 0.01,
                    fmt.format(val), ha="center", va="bottom",
                    fontsize=7.5, color=right_color, fontweight="bold")

    ax.set_xticks(positions)
    ax.set_xticklabels(x, fontsize=8.5)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold", pad=10)
    ax.legend(frameon=False)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter(fmt.replace("{:.1f}", "%.1f")))
    ax.grid(axis="y", alpha=0.4, zorder=0)


# ---------------------------------------------------------------------------
# Individual charts
# ---------------------------------------------------------------------------

def chart_execution_time(df: pd.DataFrame, out: Path):
    """Chart 1 — Grouped bar: total execution time per query."""
    fig, ax = plt.subplots(figsize=(14, 5))
    _grouped_bars(
        ax,
        x            = df["short_label"].tolist(),
        left_vals    = df["rdbms_total_ms"].values,
        right_vals   = df["dw_total_ms"].values,
        left_label   = "RDBMS (3NF)",
        right_label  = "Data Warehouse (Star Schema)",
        left_color   = RDBMS_COLOR,
        right_color  = DW_COLOR,
        ylabel       = "Total time  (planning + execution, ms)",
        title        = "Chart 1 — Total Query Execution Time: RDBMS vs DW",
        fmt          = "{:.2f}",
    )
    fig.tight_layout()
    _save(fig, out, "execution time")


def chart_speedup(df: pd.DataFrame, out: Path):
    """Chart 2 — Horizontal bar: DW speedup factor over RDBMS."""
    df_sorted = df.sort_values("speedup", ascending=True)

    fig, ax = plt.subplots(figsize=(9, 6))
    colors = [DW_COLOR if v >= 1 else RDBMS_COLOR for v in df_sorted["speedup"]]
    bars = ax.barh(
        df_sorted["query_id"], df_sorted["speedup"],
        color=colors, alpha=0.88, zorder=3
    )
    ax.axvline(1.0, color="black", linewidth=1.2, linestyle="--", label="Break-even (1×)")

    for bar, val in zip(bars, df_sorted["speedup"]):
        label_x = val + 0.03 if val >= 0 else val - 0.03
        ha = "left" if val >= 0 else "right"
        ax.text(label_x, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}×", va="center", ha=ha, fontsize=9, fontweight="bold",
                color=DW_COLOR if val >= 1 else RDBMS_COLOR)

    ax.set_xlabel("Speedup factor  (>1 = DW faster, <1 = RDBMS faster)")
    ax.set_title("Chart 2 — DW Speedup over RDBMS per Query", fontweight="bold", pad=10)
    ax.legend(frameon=False)
    ax.grid(axis="x", alpha=0.4, zorder=0)

    # Annotate quadrant labels
    xmax = df_sorted["speedup"].max()
    ax.text(xmax * 0.98, len(df_sorted) - 0.6, "DW faster →",
            ha="right", va="top", color=DW_COLOR, fontsize=9, style="italic")
    ax.text(1.02, 0.2, "← RDBMS faster",
            ha="left", va="bottom", color=RDBMS_COLOR, fontsize=9, style="italic")

    fig.tight_layout()
    _save(fig, out, "speedup")


def chart_verbosity(df: pd.DataFrame, out: Path):
    """Chart 3 — Grouped bar: lines of SQL code per query."""
    fig, ax = plt.subplots(figsize=(14, 5))
    _grouped_bars(
        ax,
        x            = df["short_label"].tolist(),
        left_vals    = df["rdbms_lines"].values.astype(float),
        right_vals   = df["dw_lines"].values.astype(float),
        left_label   = "RDBMS (3NF)",
        right_label  = "Data Warehouse (Star Schema)",
        left_color   = RDBMS_COLOR,
        right_color  = DW_COLOR,
        ylabel       = "Non-blank, non-comment SQL lines",
        title        = "Chart 3 — SQL Verbosity: Lines of Code per Query",
        fmt          = "{:.0f}",
    )
    # Annotate ratio on top of the pair
    positions = np.arange(len(df))
    for i, row in df.iterrows():
        idx = df.index.get_loc(i)
        ratio = row["lines_ratio"]
        if ratio >= 1.5:
            ax.text(idx, max(row["rdbms_lines"], row["dw_lines"]) + 0.8,
                    f"{ratio:.1f}×", ha="center", va="bottom",
                    fontsize=8, color="#B03A2E", fontweight="bold")

    fig.tight_layout()
    _save(fig, out, "verbosity")


def chart_plan_complexity(df: pd.DataFrame, out: Path):
    """Chart 4 — Grouped bar: total query-plan nodes."""
    fig, ax = plt.subplots(figsize=(14, 5))
    _grouped_bars(
        ax,
        x            = df["short_label"].tolist(),
        left_vals    = df["rdbms_total_nodes"].values.astype(float),
        right_vals   = df["dw_total_nodes"].values.astype(float),
        left_label   = "RDBMS (3NF)",
        right_label  = "Data Warehouse (Star Schema)",
        left_color   = RDBMS_COLOR,
        right_color  = DW_COLOR,
        ylabel       = "Plan nodes  (joins + scans + aggregations)",
        title        = "Chart 4 — Query Plan Complexity: Execution-Plan Nodes",
        fmt          = "{:.0f}",
    )
    fig.tight_layout()
    _save(fig, out, "plan complexity")


def chart_time_breakdown(df: pd.DataFrame, out: Path):
    """Chart 5 — Stacked bar: planning vs execution time for both systems."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 5), sharey=False)

    systems = [
        ("RDBMS (3NF)",              "rdbms_plan_ms", "rdbms_exec_ms", RDBMS_COLOR, axes[0]),
        ("Data Warehouse (OLAP)",    "dw_plan_ms",    "dw_exec_ms",    DW_COLOR,    axes[1]),
    ]

    for label, plan_col, exec_col, color, ax in systems:
        x = np.arange(len(df))
        plan_vals = df[plan_col].values
        exec_vals = df[exec_col].values

        ax.bar(x, plan_vals, label="Planning time", color=color, alpha=0.45, zorder=3)
        ax.bar(x, exec_vals, bottom=plan_vals,
               label="Execution time", color=color, alpha=0.88, zorder=3)

        ax.set_xticks(x)
        ax.set_xticklabels(df["short_label"], fontsize=8)
        ax.set_ylabel("Time (ms)")
        ax.set_title(f"{label}", fontweight="bold")
        ax.legend(frameon=False)
        ax.grid(axis="y", alpha=0.4, zorder=0)

    fig.suptitle("Chart 5 — Planning vs Execution Time Breakdown",
                 fontweight="bold", fontsize=13, y=1.02)
    fig.tight_layout()
    _save(fig, out, "time breakdown")


def chart_scatter_verbosity_vs_speedup(df: pd.DataFrame, out: Path):
    """Chart 6 — Scatter: verbosity ratio vs DW speedup (quadrant analysis)."""
    fig, ax = plt.subplots(figsize=(9, 7))

    scatter = ax.scatter(
        df["lines_ratio"], df["speedup"],
        s=120, c=df["speedup"], cmap="RdYlGn",
        vmin=df["speedup"].min(), vmax=df["speedup"].max(),
        edgecolors="white", linewidth=0.8, zorder=3, alpha=0.9,
    )
    plt.colorbar(scatter, ax=ax, label="DW speedup factor")

    # Annotate each point
    for _, row in df.iterrows():
        ax.annotate(
            row["query_id"],
            xy=(row["lines_ratio"], row["speedup"]),
            xytext=(5, 5), textcoords="offset points",
            fontsize=9, fontweight="bold",
        )

    # Reference lines
    ax.axhline(1.0, color="black", linewidth=1.0, linestyle="--", alpha=0.6, label="Same speed")
    ax.axvline(1.0, color="black", linewidth=1.0, linestyle=":",  alpha=0.6, label="Same verbosity")

    # Quadrant labels
    xmax, ymax = df["lines_ratio"].max(), df["speedup"].max()
    xmin, ymin = df["lines_ratio"].min(), df["speedup"].min()
    mid_x = (xmax + 1.0) / 2
    mid_y = (ymax + 1.0) / 2
    ax.text(mid_x, mid_y, "DW faster\n& more concise",
            ha="center", va="center", fontsize=9,
            color=DW_COLOR, alpha=0.5, style="italic")
    ax.text(1.2, (ymin + 1.0) / 2, "RDBMS faster\nbut verbose",
            ha="left", va="center", fontsize=9,
            color=RDBMS_COLOR, alpha=0.5, style="italic")

    ax.set_xlabel("Verbosity ratio  (RDBMS lines / DW lines)", fontsize=11)
    ax.set_ylabel("DW speedup factor  (RDBMS time / DW time)", fontsize=11)
    ax.set_title("Chart 6 — Verbosity vs Performance Trade-off", fontweight="bold", pad=10)
    ax.legend(frameon=False)
    ax.grid(alpha=0.3, zorder=0)

    fig.tight_layout()
    _save(fig, out, "scatter")


def chart_heatmap(df: pd.DataFrame, out: Path):
    """Chart 7 — Heatmap of normalised metrics (RDBMS − DW, positive = RDBMS worse)."""
    metrics = {
        "Exec time\n(ms)":       ("rdbms_exec_ms",    "dw_exec_ms"),
        "Planning\n(ms)":        ("rdbms_plan_ms",     "dw_plan_ms"),
        "SQL lines":             ("rdbms_lines",       "dw_lines"),
        "JOIN nodes":            ("rdbms_joins",       "dw_joins"),
        "Seq scans":             ("rdbms_seq_scans",   "dw_seq_scans"),
        "Agg nodes":             ("rdbms_agg_nodes",   "dw_agg_nodes"),
    }

    # Build diff matrix: RDBMS - DW  (normalised 0-1 per column)
    diff_data = {}
    for label, (r_col, d_col) in metrics.items():
        diff = df[r_col].astype(float) - df[d_col].astype(float)
        # Normalise to [-1, 1]
        max_abs = diff.abs().max()
        diff_data[label] = (diff / max_abs) if max_abs > 0 else diff

    heat_df = pd.DataFrame(diff_data, index=df["query_id"])

    fig, ax = plt.subplots(figsize=(11, 7))
    sns.heatmap(
        heat_df,
        annot=True, fmt=".2f", linewidths=0.5,
        cmap="RdYlGn_r",    # red = RDBMS worse, green = RDBMS better
        center=0,
        vmin=-1, vmax=1,
        ax=ax,
        cbar_kws={"label": "Normalised difference\n(positive = RDBMS worse)", "shrink": 0.8},
    )
    ax.set_title("Chart 7 — Normalised Metric Comparison Heatmap\n"
                 "(red = RDBMS worse, green = RDBMS better / similar)",
                 fontweight="bold", pad=12)
    ax.set_xlabel("")
    ax.set_ylabel("Query")

    fig.tight_layout()
    _save(fig, out, "heatmap")


# ---------------------------------------------------------------------------
# Combined PDF / PNG summary
# ---------------------------------------------------------------------------

def chart_summary_dashboard(df: pd.DataFrame, out: Path):
    """
    Chart 8 — 2×3 dashboard combining key metrics on a single figure.
    Useful as a single-slide overview.
    """
    fig = plt.figure(figsize=(20, 12))
    fig.suptitle(
        "RDBMS (3NF) vs Data Warehouse (Star Schema + OLAP)\n"
        "Green Mobility — Benchmark Summary Dashboard",
        fontsize=15, fontweight="bold", y=1.01,
    )

    gs = fig.add_gridspec(2, 3, hspace=0.45, wspace=0.35)

    ax1 = fig.add_subplot(gs[0, 0])   # execution time
    ax2 = fig.add_subplot(gs[0, 1])   # speedup
    ax3 = fig.add_subplot(gs[0, 2])   # verbosity
    ax4 = fig.add_subplot(gs[1, 0])   # plan nodes
    ax5 = fig.add_subplot(gs[1, 1])   # scatter
    ax6 = fig.add_subplot(gs[1, 2])   # heatmap (mini)

    x      = np.arange(len(df))
    width  = 0.38
    labels = df["query_id"].tolist()

    # — ax1: execution time
    ax1.bar(x - width/2, df["rdbms_total_ms"], width, label="RDBMS", color=RDBMS_COLOR, alpha=0.85)
    ax1.bar(x + width/2, df["dw_total_ms"],    width, label="DW",    color=DW_COLOR,    alpha=0.85)
    ax1.set_xticks(x); ax1.set_xticklabels(labels, fontsize=7)
    ax1.set_title("Execution Time (ms)", fontweight="bold")
    ax1.set_ylabel("ms"); ax1.legend(fontsize=8, frameon=False)
    ax1.grid(axis="y", alpha=0.4)

    # — ax2: speedup horizontal
    colors = [DW_COLOR if v >= 1 else RDBMS_COLOR for v in df["speedup"]]
    ax2.barh(df["query_id"], df["speedup"], color=colors, alpha=0.85)
    ax2.axvline(1.0, color="black", linewidth=1, linestyle="--")
    ax2.set_title("DW Speedup over RDBMS", fontweight="bold")
    ax2.set_xlabel("× factor  (>1 = DW faster)")
    ax2.grid(axis="x", alpha=0.4)

    # — ax3: verbosity
    ax3.bar(x - width/2, df["rdbms_lines"], width, label="RDBMS", color=RDBMS_COLOR, alpha=0.85)
    ax3.bar(x + width/2, df["dw_lines"],    width, label="DW",    color=DW_COLOR,    alpha=0.85)
    ax3.set_xticks(x); ax3.set_xticklabels(labels, fontsize=7)
    ax3.set_title("SQL Verbosity (lines)", fontweight="bold")
    ax3.set_ylabel("Lines of code"); ax3.legend(fontsize=8, frameon=False)
    ax3.grid(axis="y", alpha=0.4)

    # — ax4: plan complexity
    ax4.bar(x - width/2, df["rdbms_total_nodes"], width, label="RDBMS", color=RDBMS_COLOR, alpha=0.85)
    ax4.bar(x + width/2, df["dw_total_nodes"],    width, label="DW",    color=DW_COLOR,    alpha=0.85)
    ax4.set_xticks(x); ax4.set_xticklabels(labels, fontsize=7)
    ax4.set_title("Query Plan Nodes", fontweight="bold")
    ax4.set_ylabel("Nodes"); ax4.legend(fontsize=8, frameon=False)
    ax4.grid(axis="y", alpha=0.4)

    # — ax5: scatter verbosity vs speedup
    sc = ax5.scatter(df["lines_ratio"], df["speedup"],
                     s=90, c=df["speedup"], cmap="RdYlGn",
                     edgecolors="white", linewidth=0.6, alpha=0.9)
    for _, row in df.iterrows():
        ax5.annotate(row["query_id"],
                     xy=(row["lines_ratio"], row["speedup"]),
                     xytext=(4, 3), textcoords="offset points", fontsize=7)
    ax5.axhline(1.0, color="black", linewidth=0.9, linestyle="--", alpha=0.6)
    ax5.axvline(1.0, color="black", linewidth=0.9, linestyle=":",  alpha=0.6)
    ax5.set_xlabel("Verbosity ratio (RDBMS/DW lines)", fontsize=9)
    ax5.set_ylabel("DW speedup factor", fontsize=9)
    ax5.set_title("Verbosity vs Speed Trade-off", fontweight="bold")
    ax5.grid(alpha=0.3)

    # — ax6: mini heatmap (speedup + lines_ratio)
    mini = df[["query_id", "speedup", "lines_ratio"]].set_index("query_id")
    mini.columns = ["DW\nSpeedup", "Lines\nRatio"]
    sns.heatmap(mini, annot=True, fmt=".1f", cmap="RdYlGn",
                center=1, ax=ax6, linewidths=0.4,
                cbar_kws={"shrink": 0.7})
    ax6.set_title("Key Metrics Heatmap", fontweight="bold")
    ax6.set_ylabel("")

    _save(fig, out, "dashboard")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Visualise benchmark results from benchmark_results.csv"
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to benchmark_results.csv (default: src/benchmark_results.csv)",
    )
    args = parser.parse_args()

    src_dir  = Path(__file__).resolve().parent
    csv_path = Path(args.csv) if args.csv else src_dir / "benchmark_results.csv"

    if not csv_path.exists():
        print(f"ERROR: CSV not found at {csv_path}")
        print("       Run 'python src/benchmark.py' first to generate it.")
        return

    figures_dir = src_dir / "figures"
    figures_dir.mkdir(exist_ok=True)

    print(f"\nReading: {csv_path}")
    df = load_data(csv_path)
    print(f"  {len(df)} queries loaded.\n")
    print("Generating charts...")

    chart_execution_time(             df, figures_dir / "01_execution_time.png")
    chart_speedup(                    df, figures_dir / "02_speedup.png")
    chart_verbosity(                  df, figures_dir / "03_verbosity.png")
    chart_plan_complexity(            df, figures_dir / "04_plan_complexity.png")
    chart_time_breakdown(             df, figures_dir / "05_time_breakdown.png")
    chart_scatter_verbosity_vs_speedup(df, figures_dir / "06_scatter.png")
    chart_heatmap(                    df, figures_dir / "07_heatmap.png")
    chart_summary_dashboard(          df, figures_dir / "00_dashboard.png")

    print(f"\nAll charts saved in: {figures_dir}")
    print("  00_dashboard.png      — single-slide summary")
    print("  01_execution_time.png — grouped bar: total time per query")
    print("  02_speedup.png        — horizontal bar: DW speedup factor")
    print("  03_verbosity.png      — grouped bar: SQL lines of code")
    print("  04_plan_complexity.png— grouped bar: query-plan nodes")
    print("  05_time_breakdown.png — stacked: planning vs execution time")
    print("  06_scatter.png        — scatter: verbosity vs speed trade-off")
    print("  07_heatmap.png        — heatmap: normalised metrics matrix\n")


if __name__ == "__main__":
    main()
