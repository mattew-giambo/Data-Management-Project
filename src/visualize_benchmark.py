import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

RDBMS_COLOR = "#4C72B0" 
DW_COLOR = "#DD8452"

sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams.update({
    "figure.dpi":        150,
    "savefig.dpi":       180,
    "font.family":       "sans-serif",
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

# Data loading

def load_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # DW speedup: ratio RDBMS/DW total time (>1 means DW is faster)
    df["speedup"] = df["rdbms_total_ms"] / df["dw_total_ms"].replace(0, np.nan)
    # Buffer columns are optional (added only after re-running benchmark.py)
    for col in ["rdbms_shared_hit", "dw_shared_hit", "rdbms_shared_read", "dw_shared_read"]:
        if col not in df.columns:
            df[col] = np.nan
    return df

def save(fig: plt.Figure, path: Path):
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path.name}")


def grouped_bar(ax, x, left_vals, right_vals, left_label, right_label,
                 left_color, right_color, ylabel, title):
    """Draw a labelled grouped bar chart on ax."""
    width = 0.38
    pos = np.arange(len(x))

    b1 = ax.bar(pos - width / 2, left_vals,  width,
                label=left_label,  color=left_color,  alpha=0.88, zorder=3)
    b2 = ax.bar(pos + width / 2, right_vals, width,
                label=right_label, color=right_color, alpha=0.88, zorder=3)

    top = max(max(left_vals), max(right_vals))
    for bar, val in list(zip(b1, left_vals)) + list(zip(b2, right_vals)):
        if pd.notna(val) and val > 0:
            color = bar.get_facecolor()
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + top * 0.012,
                    f"{val:.2f}", ha="center", va="bottom",
                    fontsize=7.5, color=color, fontweight="bold")

    ax.set_xticks(pos)
    ax.set_xticklabels(x, fontsize=8.5)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold", pad=10)
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.4, zorder=0)


# Chart 1 - Execution time

def chart_exec_time(df: pd.DataFrame, out: Path):
    fig, ax = plt.subplots(figsize=(14, 5))
    grouped_bar(
        ax,
        x            = df["query_id"].tolist(),
        left_vals    = df["rdbms_exec_ms"].values,
        right_vals   = df["dw_exec_ms"].values,
        left_label   = "RDBMS",
        right_label  = "Data Warehouse (Star Schema)",
        left_color   = RDBMS_COLOR,
        right_color  = DW_COLOR,
        ylabel       = "Execution time (ms)",
        title        = "Chart 1 - Query Execution Time: RDBMS vs DW",
    )
    fig.tight_layout()
    save(fig, out)


# Chart 2 - Planning time

def chart_plan_time(df: pd.DataFrame, out: Path):
    fig, ax = plt.subplots(figsize=(14, 5))
    grouped_bar(
        ax,
        x            = df["query_id"].tolist(),
        left_vals    = df["rdbms_plan_ms"].values,
        right_vals   = df["dw_plan_ms"].values,
        left_label   = "RDBMS",
        right_label  = "Data Warehouse (Star Schema)",
        left_color   = RDBMS_COLOR,
        right_color  = DW_COLOR,
        ylabel       = "Planning time (ms)",
        title        = "Chart 2 - Query Planning Time: RDBMS vs DW",
    )
    fig.tight_layout()
    save(fig, out)


# Chart 3 - Speedup horizontal bar

def chart_speedup(df: pd.DataFrame, out: Path):
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = [DW_COLOR if v >= 1 else RDBMS_COLOR for v in df["speedup"]]
    bars = ax.barh(df["query_id"], df["speedup"],
                   color=colors, alpha=0.90, zorder=3)
    ax.axvline(1.0, color="black", linewidth=1.2, linestyle="--", alpha=0.5)

    ax.invert_yaxis()

    for bar, val in zip(bars, df["speedup"]):
        offset = 0.03 if val >= 0 else -0.03
        ax.text(val + offset, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}x", va="center", ha="left", fontsize=9, fontweight="bold",
                color=DW_COLOR if val >= 1 else RDBMS_COLOR)

    ax.set_xlabel("Speedup factor  (RDBMS total ms / DW total ms)")
    ax.set_title("Chart 3 - DW Speedup over RDBMS (total time)",
                 fontweight="bold", pad=10)
    ax.legend(frameon=False)
    ax.grid(axis="x", alpha=0.4, zorder=0)

    fig.tight_layout()
    save(fig, out)


# Chart 4 - Stacked planning vs execution time

def chart_stacked(df: pd.DataFrame, out: Path):
    fig, axes = plt.subplots(1, 2, figsize=(15, 5), sharey=False)

    for (label, plan_col, exec_col, color), ax in zip(
        [
            ("RDBMS (OLTP)",             "rdbms_plan_ms", "rdbms_exec_ms", RDBMS_COLOR),
            ("Data Warehouse (OLAP)",   "dw_plan_ms",    "dw_exec_ms",    DW_COLOR),
        ],
        axes,
    ):
        x = np.arange(len(df))
        plan_vals = df[plan_col].values
        exec_vals = df[exec_col].values

        ax.bar(x, plan_vals, label="Planning",  color=color, alpha=0.45, zorder=3)
        ax.bar(x, exec_vals, bottom=plan_vals,
               label="Execution", color=color, alpha=0.88, zorder=3)

        ax.set_xticks(x)
        ax.set_xticklabels(df["query_id"], fontsize=9)
        ax.set_ylabel("Time (ms)")
        ax.set_title(label, fontweight="bold")
        ax.legend(frameon=False)
        ax.grid(axis="y", alpha=0.4, zorder=0)

    fig.suptitle("Chart 4 - DBMS vs DW Total Time",
                 fontweight="bold", fontsize=13, y=1.02)
    fig.tight_layout()
    save(fig, out)


# Chart 5 - Shared Buffer Hit

def chart_shared_hit(df: pd.DataFrame, out: Path):
    """Grouped bar: shared buffer hits per query (blocks served from RAM)."""
    if df["rdbms_shared_hit"].isna().all():
        print("  [skip] shared_hit data not available — re-run benchmark.py first.")
        return
    fig, ax = plt.subplots(figsize=(14, 5))
    grouped_bar(
        ax,
        x           = df["query_id"].tolist(),
        left_vals   = df["rdbms_shared_hit"].fillna(0).values,
        right_vals  = df["dw_shared_hit"].fillna(0).values,
        left_label  = "RDBMS",
        right_label = "Data Warehouse (Star Schema)",
        left_color  = RDBMS_COLOR,
        right_color = DW_COLOR,
        ylabel      = "Shared buffer hits (blocks)",
        title       = "Chart 5 - Shared Buffer Hits: RDBMS vs DW  (higher = more cache reuse)",
    )
    fig.tight_layout()
    save(fig, out)


# Chart 6 - Shared Read (Disk I/O)

def chart_shared_read(df: pd.DataFrame, out: Path):
    """Grouped bar: shared read blocks per query (blocks fetched from disk / OS cache)."""
    if df["rdbms_shared_read"].isna().all():
        print("  [skip] shared_read data not available — re-run benchmark.py first.")
        return
    fig, ax = plt.subplots(figsize=(14, 5))
    grouped_bar(
        ax,
        x           = df["query_id"].tolist(),
        left_vals   = df["rdbms_shared_read"].fillna(0).values,
        right_vals  = df["dw_shared_read"].fillna(0).values,
        left_label  = "RDBMS",
        right_label = "Data Warehouse (Star Schema)",
        left_color  = RDBMS_COLOR,
        right_color = DW_COLOR,
        ylabel      = "Shared read blocks (blocks)",
        title       = "Chart 6 - Shared Read (Disk I/O): RDBMS vs DW  (lower = less disk access)",
    )
    fig.tight_layout()
    save(fig, out)

def main():
    parser = argparse.ArgumentParser(
        description="Visualise timing benchmark results from benchmark_results.csv"
    )
    parser.add_argument(
        "--csv", default=None,
        help="Path to benchmark_results.csv  (default: src/benchmark_results.csv)",
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

    chart_exec_time  (df, figures_dir / "01_execution_time.png")
    chart_plan_time  (df, figures_dir / "02_planning_time.png")
    chart_speedup    (df, figures_dir / "03_speedup.png")
    chart_stacked    (df, figures_dir / "04_time_breakdown.png")
    chart_shared_hit (df, figures_dir / "05_shared_hit.png")
    chart_shared_read(df, figures_dir / "06_shared_read.png")

    print(f"\nCharts saved in: {figures_dir}")


if __name__ == "__main__":
    main()
