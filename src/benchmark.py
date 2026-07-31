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
    return parse_explain(rows)


def parse_explain(lines: list) -> dict:
    text = "\n".join(lines)
    exec_m  = re.search(r"Execution Time:\s*([\d.]+)\s*ms", text)
    plan_m  = re.search(r"Planning Time:\s*([\d.]+)\s*ms",  text)
    # BUFFERS: accumulate all "shared hit=N" and "shared read=N" across all plan nodes
    hit_vals  = [int(v) for v in re.findall(r"shared hit=(\d+)",  text)]
    read_vals = [int(v) for v in re.findall(r"shared read=(\d+)", text)]
    exec_ms = float(exec_m.group(1)) if exec_m else 0.0
    plan_ms = float(plan_m.group(1)) if plan_m else 0.0
    return {
        "execution_ms":  exec_ms,
        "planning_ms":   plan_ms,
        "total_ms":      exec_ms + plan_ms,
        "shared_hit":    max(hit_vals)  if hit_vals  else 0,
        "shared_read":   max(read_vals) if read_vals else 0,
    }


def avg(metric_list: list) -> dict:
    valid = [m for m in metric_list if m is not None]
    if not valid:
        return {}
    return {k: sum(m[k] for m in valid) / len(valid) for k in valid[0]}


# Benchmark runner

def run_benchmark(rdbms_conn, dw_conn, measured_runs=10) -> list:
    results = []
    query_ids = sorted(DW_QUERIES.keys(), key=lambda q: int(q[1:]))

    for qid in query_ids:
        label   = QUERY_LABELS[qid]

        rdbms_sql = RDBMS_QUERIES[qid]
        dw_sql    = DW_QUERIES[qid]

        # Measured runs
        rm_list, dm_list = [], []
        for _ in range(measured_runs):
            try:    rm_list.append(run_explain(rdbms_conn, rdbms_sql))
            except Exception as e:
                print(f"\n    [RDBMS ERR] {e}"); rm_list.append(None)
            try:    dm_list.append(run_explain(dw_conn, dw_sql))
            except Exception as e:
                print(f"\n    [DW ERR] {e}"); dm_list.append(None)

        rm = avg(rm_list)
        dm = avg(dm_list)

        r_t = rm.get("total_ms", float("inf"))
        d_t = dm.get("total_ms", float("inf"))

        results.append({
            "query_id":          qid,
            "label":             label,
            "rdbms_exec_ms":     round(rm.get("execution_ms", 0), 3),
            "dw_exec_ms":        round(dm.get("execution_ms", 0), 3),
            "rdbms_plan_ms":     round(rm.get("planning_ms",  0), 3),
            "dw_plan_ms":        round(dm.get("planning_ms",  0), 3),
            "rdbms_total_ms":    round(r_t if r_t != float("inf") else 0, 3),
            "dw_total_ms":       round(d_t if d_t != float("inf") else 0, 3),
            "rdbms_shared_hit":  round(rm.get("shared_hit",  0), 1),
            "dw_shared_hit":     round(dm.get("shared_hit",  0), 1),
            "rdbms_shared_read": round(rm.get("shared_read", 0), 1),
            "dw_shared_read":    round(dm.get("shared_read", 0), 1),
        })

    return results


def save_csv(results: list, path: Path):
    if not results:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"  CSV saved -> {path}\n")
    

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
    parser.add_argument("--runs",      type=int, default=10,
                        help="Measured runs per query (default: 3)")
    args = parser.parse_args()

    print(f"\nConnecting to RDBMS db '{args.rdbms_db}' ...")
    rdbms_conn = connect(args.host, args.port, args.rdbms_db, args.user, args.password)
    rdbms_conn.autocommit = True

    print(f"Connecting to DW db '{args.dw_db}' ...")
    dw_conn = connect(args.host, args.port, args.dw_db, args.user, args.password)
    dw_conn.autocommit = True

    print(f"\nRunning benchmark  "
          f"{args.runs} measured runs per query...\n")

    try:
        results = run_benchmark(rdbms_conn, dw_conn,
                                measured_runs=args.runs)
        
        src_dir = Path(__file__).resolve().parent
        save_csv(results, src_dir / "benchmark_results.csv")

    finally:
        rdbms_conn.close()
        dw_conn.close()


if __name__ == "__main__":
    main()
