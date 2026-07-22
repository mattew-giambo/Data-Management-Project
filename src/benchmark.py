"""
benchmark.py
============
Benchmarks 12 analytical queries on both the RDBMS (green_mobility_rdbms)
and the DW (green_mobility) databases using EXPLAIN ANALYZE.

Queries are hardcoded from:
  - src/DW/sql/olap.sql      (DW / OLAP queries)
  - src/RDBMS/sql/oltp.sql   (RDBMS / relational queries)

Metrics collected per query:
  - Planning time   (ms)
  - Execution time  (ms)
  - Total time      (ms)  ← planning + execution

Output:
  - Formatted table printed to stdout
  - src/benchmark_results.csv

Usage
-----
    python src/benchmark.py

    python src/benchmark.py --rdbms-db green_mobility_rdbms \\
                             --dw-db green_mobility \\
                             --user postgres --password postgres
"""

import argparse
import csv
import re
from pathlib import Path
from utility.constants import DW_QUERIES, RDBMS_QUERIES
import psycopg2

QUERY_LABELS = {
    "Q1":  "EV Sales (Continent x Year)",
    "Q2":  "Renewable Electricity vs CO2",
    "Q3":  "Rich vs Poor Countries",
    "Q4":  "Top Countries by EV Stock",
    "Q5":  "Vehicle Type Analysis",
    "Q6":  "Pandemic Impact",
    "Q7":  "Infrastructure Growth",
    "Q8":  "Green Elec & High EV Demand",
    "Q9":  "Continent x Pandemic Period",
    "Q10": "Renewable Share %",
    "Q11": "Countries Improving Most",
    "Q12": "Is EV Adoption Reducing CO2?",
}


# ============================================================
# PostgreSQL helpers
# ============================================================

def connect(host, port, dbname, user, password):
    return psycopg2.connect(
        host=host, port=port, dbname=dbname,
        user=user, password=password,
    )


def run_explain(conn, sql: str) -> dict:
    """Wrap sql with EXPLAIN ANALYZE, execute, return parsed metrics."""
    wrapped = "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)\n" + sql.strip()
    with conn.cursor() as cur:
        cur.execute(wrapped)
        rows = [r[0] for r in cur.fetchall()]
    return _parse_explain(rows)


def _parse_explain(lines: list) -> dict:
    text = "\n".join(lines)
    exec_m = re.search(r"Execution Time:\s*([\d.]+)\s*ms", text)
    plan_m = re.search(r"Planning Time:\s*([\d.]+)\s*ms",  text)
    exec_ms = float(exec_m.group(1)) if exec_m else 0.0
    plan_ms = float(plan_m.group(1)) if plan_m else 0.0
    return {
        "execution_ms": exec_ms,
        "planning_ms":  plan_ms,
        "total_ms":     exec_ms + plan_ms,
    }


def _avg(metric_list: list) -> dict:
    valid = [m for m in metric_list if m is not None]
    if not valid:
        return {}
    return {k: sum(m[k] for m in valid) / len(valid) for k in valid[0]}


# ============================================================
# Benchmark runner
# ============================================================

def run_benchmark(rdbms_conn, dw_conn, warmup_runs=1, measured_runs=4) -> list:
    results = []
    query_ids = sorted(DW_QUERIES.keys(), key=lambda q: int(q[1:]))

    for qid in query_ids:
        label   = QUERY_LABELS[qid]

        rdbms_sql = RDBMS_QUERIES[qid]
        dw_sql    = DW_QUERIES[qid]

        # Warmup (fills buffer cache)
        for _ in range(warmup_runs):
            try: run_explain(rdbms_conn, rdbms_sql)
            except Exception: pass
            try: run_explain(dw_conn,    dw_sql)
            except Exception: pass

        # Measured runs
        rm_list, dm_list = [], []
        for _ in range(measured_runs):
            try:    rm_list.append(run_explain(rdbms_conn, rdbms_sql))
            except Exception as e:
                print(f"\n    [RDBMS ERR] {e}"); rm_list.append(None)
            try:    dm_list.append(run_explain(dw_conn, dw_sql))
            except Exception as e:
                print(f"\n    [DW ERR] {e}"); dm_list.append(None)

        rm = _avg(rm_list)
        dm = _avg(dm_list)

        r_t = rm.get("total_ms", float("inf"))
        d_t = dm.get("total_ms", float("inf"))

        results.append({
            "query_id":       qid,
            "label":          label,
            "rdbms_exec_ms":  round(rm.get("execution_ms", 0), 3),
            "dw_exec_ms":     round(dm.get("execution_ms", 0), 3),
            "rdbms_plan_ms":  round(rm.get("planning_ms",  0), 3),
            "dw_plan_ms":     round(dm.get("planning_ms",  0), 3),
            "rdbms_total_ms": round(r_t if r_t != float("inf") else 0, 3),
            "dw_total_ms":    round(d_t if d_t != float("inf") else 0, 3),
        })

    return results


def save_csv(results: list, path: Path):
    if not results:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"  CSV saved → {path}\n")


# ============================================================
# Entry point
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark RDBMS vs DW queries (hardcoded from SQL files)."
    )
    parser.add_argument("--host",      default="localhost")
    parser.add_argument("--port",      type=int, default=5432)
    parser.add_argument("--rdbms-db",  default="green_mobility_rdbms")
    parser.add_argument("--dw-db",     default="green_mobility")
    parser.add_argument("--user",      default="postgres")
    parser.add_argument("--password",  default="postgres")
    parser.add_argument("--warmup",    type=int, default=1,
                        help="Warmup runs before measuring (default: 1)")
    parser.add_argument("--runs",      type=int, default=5,
                        help="Measured runs per query (default: 3)")
    args = parser.parse_args()

    print(f"\nConnecting to RDBMS db '{args.rdbms_db}' ...")
    rdbms_conn = connect(args.host, args.port, args.rdbms_db, args.user, args.password)
    rdbms_conn.autocommit = True

    print(f"Connecting to DW db '{args.dw_db}' ...")
    dw_conn = connect(args.host, args.port, args.dw_db, args.user, args.password)
    dw_conn.autocommit = True

    print(f"\nRunning benchmark  "
          f"({args.warmup} warmup + {args.runs} measured runs per query)...\n")

    try:
        results = run_benchmark(rdbms_conn, dw_conn,
                                warmup_runs=args.warmup,
                                measured_runs=args.runs)
        
        src_dir = Path(__file__).resolve().parent
        save_csv(results, src_dir / "benchmark_results.csv")

    finally:
        rdbms_conn.close()
        dw_conn.close()


if __name__ == "__main__":
    main()
