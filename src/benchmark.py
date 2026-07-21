"""
benchmark.py
============
Benchmarks 12 analytical queries on both the RDBMS (green_mobility_rdbms)
and the DW (green_mobility) databases using EXPLAIN ANALYZE.

Queries are hardcoded from:
  - src/DW/sql/olap.sql      (DW / OLAP queries)
  - src/RDBMS/sql/oltp.sql   (RDBMS / relational queries)

Metrics collected per query:
  - Planning time      (from EXPLAIN ANALYZE)
  - Execution time     (from EXPLAIN ANALYZE)
  - Total time         (planning + execution)
  - SQL lines          (non-blank, non-comment lines — verbosity)
  - Seq Scan nodes     (from the query plan)
  - JOIN nodes         (Hash Join / Nested Loop / Merge Join)
  - Aggregation nodes  (Aggregate / GroupAggregate / HashAggregate)

Output:
  - Formatted tables printed to stdout
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

import psycopg2


# ============================================================
# DW QUERIES  (from src/DW/sql/olap.sql)
# ============================================================

DW_QUERIES = {

"Q1": """
SELECT
    cont.continent,
    y.year,
    COALESCE(SUM(m.evSales), 0) AS total_ev_sales
FROM (
    SELECT DISTINCT continent
    FROM CountryDim
) cont
CROSS JOIN YearDim y
LEFT JOIN CountryDim c
    ON c.continent = cont.continent
LEFT JOIN EVMarket m
    ON m.keyC = c.keyC
   AND m.keyY = y.keyY
GROUP BY ROLLUP(cont.continent, y.year)
ORDER BY cont.continent, y.year
""",

"Q2": """
SELECT
    c.country,
    y.year,
    ce.renewableElectricityGeneration,
    cm.co2Emissions
FROM CountryEnergy ce
JOIN CountryMacroeconomics cm
    ON ce.keyC = cm.keyC
   AND ce.keyY = cm.keyY
JOIN CountryDim c ON ce.keyC = c.keyC
JOIN YearDim y ON ce.keyY = y.keyY
ORDER BY y.year, ce.renewableElectricityGeneration DESC
""",

"Q3": """
SELECT
    y.year,
    CASE
        WHEN cm.GDP >= 1000000000000 THEN 'High GDP'
        WHEN cm.GDP >= 100000000000 THEN 'Medium GDP'
        ELSE 'Low GDP'
    END AS GDP_class,
    AVG(em.evSalesShare) AS avg_ev_share
FROM CountryMacroeconomics cm
JOIN EVMarket em
    ON cm.keyC = em.keyC
   AND cm.keyY = em.keyY
JOIN YearDim y ON cm.keyY = y.keyY
GROUP BY y.year, GDP_class
ORDER BY y.year, GDP_class
""",

"Q4": """
SELECT
    y.year,
    c.country,
    SUM(evStock) AS stock,
    RANK() OVER (
        PARTITION BY y.year
        ORDER BY SUM(evStock) DESC
    ) AS ranking
FROM EVMarket m
JOIN CountryDim c ON m.keyC = c.keyC
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY y.year, c.country
""",

"Q5": """
SELECT
    v.vehicleType,
    p.powertrain,
    SUM(evSales) AS total_sales
FROM EVMarket m
JOIN VehicleTypeDim v ON m.keyV = v.keyV
JOIN PowertrainDim p ON m.keyP = p.keyP
GROUP BY CUBE(v.vehicleType, p.powertrain)
ORDER BY v.vehicleType, p.powertrain
""",

"Q6": """
SELECT
    y.pandemicPeriod,
    AVG(evSalesShare) AS avg_share
FROM EVMarket m
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY y.pandemicPeriod
""",

"Q7": """
SELECT
    c.country,
    y.year,
    evChargingPoints,
    LAG(evChargingPoints) OVER(
        PARTITION BY c.country
        ORDER BY y.year
    ) AS previous_year,
    evChargingPoints -
    LAG(evChargingPoints) OVER(
        PARTITION BY c.country
        ORDER BY y.year
    ) AS yearly_growth
FROM EVInfrastructure i
JOIN CountryDim c ON i.keyC = c.keyC
JOIN YearDim y ON i.keyY = y.keyY
""",

"Q8": """
SELECT
    c.country,
    y.year,
    SUM(em.evElectricityDemand) as evElectricityDemand,
    max(ce.renewableElectricityGeneration) as renewableElectricityGeneration,
    max(ce.fossilElectricityGeneration) as fossilElectricityGeneration
FROM EVMarket em
JOIN CountryEnergy ce
    ON em.keyC = ce.keyC
   AND em.keyY = ce.keyY
JOIN CountryDim c ON em.keyC = c.keyC
JOIN YearDim y ON em.keyY = y.keyY
WHERE em.evElectricityDemand > 0
GROUP BY c.country, y.year
ORDER BY c.country, y.year
""",

"Q9": """
SELECT
    c.continent,
    y.pandemicPeriod,
    SUM(evSales) AS sales
FROM EVMarket m
JOIN CountryDim c ON m.keyC = c.keyC
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY GROUPING SETS (
    (c.continent, y.pandemicPeriod),
    (c.continent),
    (y.pandemicPeriod),
    ()
)
""",

"Q10": """
SELECT
    c.country,
    y.year,
    ROUND(
        100 * renewableElectricityGeneration /
        electricityGeneration,
        2
    ) AS renewable_percentage
FROM CountryEnergy ce
JOIN CountryDim c ON ce.keyC = c.keyC
JOIN YearDim y ON ce.keyY = y.keyY
WHERE electricityGeneration > 0
ORDER BY c.country, y.year
""",

"Q11": """
SELECT
    c.country,
    MIN(y.year) AS first_year,
    MAX(y.year) AS last_year,
    MAX(evStockShare) - MIN(evStockShare) AS improvement
FROM EVMarket m
JOIN CountryDim c ON m.keyC = c.keyC
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY c.country
ORDER BY improvement DESC
""",

"Q12": """
SELECT
    c.country,
    y.year,
    SUM(em.evSalesShare) AS evSalesShare,
    AVG(ce.renewableElectricityGeneration) AS renewableElectricityGeneration,
    AVG(cm.co2PerCapita) AS co2PerCapita
FROM EVMarket em
JOIN CountryEnergy ce
    ON em.keyC = ce.keyC
    AND em.keyY = ce.keyY
JOIN CountryMacroeconomics cm
    ON em.keyC = cm.keyC
    AND em.keyY = cm.keyY
JOIN CountryDim c ON em.keyC = c.keyC
JOIN YearDim y ON em.keyY = y.keyY
GROUP BY
    c.country,
    y.year
ORDER BY
    c.country,
    y.year
""",

}


# ============================================================
# RDBMS QUERIES  (from src/RDBMS/sql/oltp.sql)
# ============================================================

RDBMS_QUERIES = {

"Q1": """
SELECT
    c.continent,
    y.year,
    COALESCE(SUM(s.ev_sales), 0)    AS total_ev_sales
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
JOIN Year    y ON s.year_id    = y.year_id
GROUP BY c.continent, y.year

UNION ALL

SELECT
    c.continent,
    NULL::INT                        AS year,
    COALESCE(SUM(s.ev_sales), 0)    AS total_ev_sales
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
GROUP BY c.continent

UNION ALL

SELECT
    NULL::VARCHAR                    AS continent,
    NULL::INT                        AS year,
    COALESCE(SUM(s.ev_sales), 0)    AS total_ev_sales
FROM EVSales s

ORDER BY continent, year
""",

"Q2": """
SELECT
    c.country_name                              AS country,
    y.year,
    e.renewable_electricity_generation,
    m.co2_emissions
FROM CountryEnergy e
JOIN CountryMacroeconomics m
    ON  e.country_id = m.country_id
    AND e.year_id    = m.year_id
JOIN Country c ON e.country_id = c.country_id
JOIN Year    y ON e.year_id    = y.year_id
ORDER BY y.year, e.renewable_electricity_generation DESC
""",

"Q3": """
SELECT
    y.year,
    CASE
        WHEN m.gdp >= 1000000000000 THEN 'High GDP'
        WHEN m.gdp >= 100000000000  THEN 'Medium GDP'
        ELSE                             'Low GDP'
    END                                 AS gdp_class,
    AVG(s.ev_sales_share)               AS avg_ev_share
FROM CountryMacroeconomics m
JOIN EVSales s
    ON  m.country_id = s.country_id
    AND m.year_id    = s.year_id
JOIN Year y ON m.year_id = y.year_id
GROUP BY y.year, gdp_class
ORDER BY y.year, gdp_class
""",

"Q4": """
WITH stock_by_country AS (
    SELECT
        c.country_name                  AS country,
        y.year,
        SUM(s.ev_stock)                 AS total_stock
    FROM EVSales s
    JOIN Country c ON s.country_id = c.country_id
    JOIN Year    y ON s.year_id    = y.year_id
    GROUP BY c.country_name, y.year
)
SELECT
    a.year,
    a.country,
    a.total_stock                       AS stock,
    1 + COUNT(b.country)                AS ranking
FROM stock_by_country a
LEFT JOIN stock_by_country b
    ON  a.year        = b.year
    AND b.total_stock > a.total_stock
GROUP BY a.year, a.country, a.total_stock
ORDER BY a.year, ranking
""",

"Q5": """
SELECT
    vt.type_name                        AS vehicle_type,
    pt.powertrain_name                  AS powertrain,
    SUM(s.ev_sales)                     AS total_sales
FROM EVSales s
JOIN VehicleType vt ON s.vehicle_type_id = vt.vehicle_type_id
JOIN Powertrain  pt ON s.powertrain_id   = pt.powertrain_id
GROUP BY vt.type_name, pt.powertrain_name

UNION ALL

SELECT
    vt.type_name,
    NULL         AS powertrain,
    SUM(s.ev_sales)                      AS total_sales
FROM EVSales s
JOIN VehicleType vt ON s.vehicle_type_id = vt.vehicle_type_id
GROUP BY vt.type_name

UNION ALL

SELECT
    NULL                      AS vehicle_type,
    pt.powertrain_name,
    SUM(s.ev_sales)                      AS total_sales
FROM EVSales s
JOIN Powertrain pt ON s.powertrain_id = pt.powertrain_id
GROUP BY pt.powertrain_name

UNION ALL

SELECT
    NULL                       AS vehicle_type,
    NULL                       AS powertrain,
    SUM(s.ev_sales)                      AS total_sales
FROM EVSales s

ORDER BY vehicle_type, powertrain
""",

"Q6": """
SELECT
    y.pandemic_period,
    AVG(s.ev_sales_share)               AS avg_share
FROM EVSales s
JOIN Year y ON s.year_id = y.year_id
GROUP BY y.pandemic_period
ORDER BY y.pandemic_period
""",

"Q7": """
SELECT
    c.country_name                      AS country,
    y.year,
    i.ev_charging_points,
    prev.ev_charging_points             AS previous_year,
    i.ev_charging_points
        - COALESCE(prev.ev_charging_points, 0)
                                        AS yearly_growth
FROM EVInfrastructure i
JOIN Country c   ON i.country_id  = c.country_id
JOIN Year    y   ON i.year_id     = y.year_id
LEFT JOIN (
    SELECT
        i2.country_id,
        y2.year                         AS this_year,
        i2.ev_charging_points
    FROM EVInfrastructure i2
    JOIN Year y2 ON i2.year_id = y2.year_id
) prev
    ON  prev.country_id = i.country_id
    AND prev.this_year  = y.year - 1
ORDER BY c.country_name, y.year
""",

"Q8": """
SELECT
    c.country_name                              AS country,
    y.year,
    SUM(s.ev_electricity_demand)                AS ev_electricity_demand,
    MAX(e.renewable_electricity_generation)     AS renewable_electricity_generation,
    MAX(e.fossil_electricity_generation)        AS fossil_electricity_generation
FROM EVSales s
JOIN CountryEnergy e
    ON  s.country_id = e.country_id
    AND s.year_id    = e.year_id
JOIN Country c ON s.country_id = c.country_id
JOIN Year    y ON s.year_id    = y.year_id
WHERE s.ev_electricity_demand > 0
GROUP BY c.country_name, y.year
ORDER BY c.country_name, y.year
""",

"Q9": """
SELECT
    c.continent,
    y.pandemic_period,
    SUM(s.ev_sales)                     AS sales
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
JOIN Year    y ON s.year_id    = y.year_id
GROUP BY c.continent, y.pandemic_period

UNION ALL

SELECT
    c.continent,
    NULL::VARCHAR                        AS pandemic_period,
    SUM(s.ev_sales)                      AS sales
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
GROUP BY c.continent

UNION ALL

SELECT
    NULL::VARCHAR                        AS continent,
    y.pandemic_period,
    SUM(s.ev_sales)                      AS sales
FROM EVSales s
JOIN Year y ON s.year_id = y.year_id
GROUP BY y.pandemic_period

UNION ALL

SELECT
    NULL::VARCHAR                        AS continent,
    NULL::VARCHAR                        AS pandemic_period,
    SUM(s.ev_sales)                      AS sales
FROM EVSales s

ORDER BY continent, pandemic_period
""",

"Q10": """
SELECT
    c.country_name                              AS country,
    y.year,
    ROUND(
        100.0 * e.renewable_electricity_generation
              / e.electricity_generation,
        2
    )                                           AS renewable_percentage
FROM CountryEnergy e
JOIN Country c ON e.country_id = c.country_id
JOIN Year    y ON e.year_id    = y.year_id
WHERE e.electricity_generation > 0
ORDER BY c.country_name, y.year
""",

"Q11": """
SELECT
    c.country_name                              AS country,
    MIN(y.year)                                 AS first_year,
    MAX(y.year)                                 AS last_year,
    MAX(s.ev_stock_share) - MIN(s.ev_stock_share)
                                                AS improvement
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
JOIN Year    y ON s.year_id    = y.year_id
GROUP BY c.country_name
ORDER BY improvement DESC
""",

"Q12": """
SELECT
    c.country_name                              AS country,
    y.year,
    SUM(s.ev_sales_share)                       AS ev_sales_share,
    AVG(e.renewable_electricity_generation)     AS renewable_electricity_generation,
    AVG(m.co2_per_capita)                       AS co2_per_capita
FROM EVSales s
JOIN CountryEnergy e
    ON  s.country_id = e.country_id
    AND s.year_id    = e.year_id
JOIN CountryMacroeconomics m
    ON  s.country_id = m.country_id
    AND s.year_id    = m.year_id
JOIN Country c ON s.country_id = c.country_id
JOIN Year    y ON s.year_id    = y.year_id
GROUP BY
    c.country_name,
    y.year
ORDER BY
    c.country_name,
    y.year
""",

}


# ============================================================
# Metadata
# ============================================================

QUERY_LABELS = {
    "Q1":  "EV Sales (Continent × Year)",
    "Q2":  "Renewable Electricity vs CO₂",
    "Q3":  "Rich vs Poor Countries",
    "Q4":  "Top Countries by EV Stock",
    "Q5":  "Vehicle Type Analysis",
    "Q6":  "Pandemic Impact",
    "Q7":  "Infrastructure Growth",
    "Q8":  "Green Elec & High EV Demand",
    "Q9":  "Continent × Pandemic Period",
    "Q10": "Renewable Share %",
    "Q11": "Countries Improving Most",
    "Q12": "Is EV Adoption Reducing CO₂?",
}

OLAP_FEATURE = {
    "Q1":  "ROLLUP",
    "Q2":  "Multi-fact JOIN",
    "Q3":  "CASE + GROUP BY",
    "Q4":  "RANK() window fn",
    "Q5":  "CUBE",
    "Q6":  "Simple GROUP BY",
    "Q7":  "LAG() window fn",
    "Q8":  "Multi-fact + WHERE",
    "Q9":  "GROUPING SETS",
    "Q10": "Arithmetic ratio",
    "Q11": "MIN/MAX aggregate",
    "Q12": "3-fact JOIN",
}


def _count_sql_lines(sql: str) -> int:
    """Count non-blank, non-comment lines in a SQL string."""
    return sum(
        1 for line in sql.splitlines()
        if line.strip() and not line.strip().startswith("--")
    )


# Precompute verbosity counts once
RDBMS_LINES = {qid: _count_sql_lines(sql) for qid, sql in RDBMS_QUERIES.items()}
DW_LINES    = {qid: _count_sql_lines(sql) for qid, sql in DW_QUERIES.items()}


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
    return {
        "execution_ms": float(exec_m.group(1)) if exec_m else 0.0,
        "planning_ms":  float(plan_m.group(1)) if plan_m else 0.0,
        "total_ms":     (float(exec_m.group(1)) if exec_m else 0.0)
                      + (float(plan_m.group(1)) if plan_m else 0.0),
        "seq_scans":  len(re.findall(r"Seq Scan",                         text)),
        "index_scans":len(re.findall(r"Index (?:Only )?Scan",             text)),
        "join_nodes": len(re.findall(r"Hash Join|Nested Loop|Merge Join", text)),
        "agg_nodes":  len(re.findall(r"(?:Hash)?Aggregate|GroupAggregate",text)),
    }


def _avg(metric_list: list) -> dict:
    valid = [m for m in metric_list if m is not None]
    if not valid:
        return {}
    return {k: sum(m[k] for m in valid) / len(valid) for k in valid[0]}


# ============================================================
# Benchmark runner
# ============================================================

def run_benchmark(rdbms_conn, dw_conn, warmup_runs=1, measured_runs=3) -> list:
    results = []
    query_ids = sorted(DW_QUERIES.keys(), key=lambda q: int(q[1:]))

    for qid in query_ids:
        label   = QUERY_LABELS[qid]
        feature = OLAP_FEATURE[qid]
        print(f"  {qid}: {label:<33}", end="", flush=True)

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
        winner  = "DW" if d_t < r_t else ("RDBMS" if r_t < d_t else "TIE")
        speedup = f"{r_t/d_t:.2f}x" if d_t and d_t > 0 else "N/A"
        print(f" RDBMS {r_t:7.2f}ms  DW {d_t:7.2f}ms  → {winner} ({speedup})")

        results.append({
            "query_id":        qid,
            "label":           label,
            "olap_feature":    feature,
            "rdbms_lines":     RDBMS_LINES[qid],
            "dw_lines":        DW_LINES[qid],
            "lines_ratio":     round(RDBMS_LINES[qid] / max(DW_LINES[qid], 1), 1),
            "rdbms_exec_ms":   round(rm.get("execution_ms", 0), 3),
            "dw_exec_ms":      round(dm.get("execution_ms", 0), 3),
            "rdbms_plan_ms":   round(rm.get("planning_ms",  0), 3),
            "dw_plan_ms":      round(dm.get("planning_ms",  0), 3),
            "rdbms_total_ms":  round(r_t if r_t != float("inf") else 0, 3),
            "dw_total_ms":     round(d_t if d_t != float("inf") else 0, 3),
            "rdbms_seq_scans": rm.get("seq_scans"),
            "dw_seq_scans":    dm.get("seq_scans"),
            "rdbms_joins":     rm.get("join_nodes"),
            "dw_joins":        dm.get("join_nodes"),
            "rdbms_agg_nodes": rm.get("agg_nodes"),
            "dw_agg_nodes":    dm.get("agg_nodes"),
        })

    return results


# ============================================================
# Report
# ============================================================

W = 128

def print_report(results: list):
    print(f"\n{'='*W}")
    print("  BENCHMARK: RDBMS (3NF)  vs  Data Warehouse (Star Schema + OLAP)")
    print(f"{'='*W}")

    # ① Timing
    print("\n  ① EXECUTION TIME  (average over measured runs, ms)\n")
    print(f"  {'ID':<4} {'OLAP Feature':<18} {'RDBMS exec':>11} {'DW exec':>9} "
          f"{'RDBMS total':>12} {'DW total':>9} {'Winner':>8} {'Speedup':>8}")
    print("  " + "─" * 90)
    for r in results:
        r_t = r["rdbms_total_ms"]; d_t = r["dw_total_ms"]
        winner  = "DW" if d_t < r_t else ("RDBMS" if r_t < d_t else "TIE")
        speedup = f"{r_t/d_t:.2f}x" if d_t > 0 else "N/A"
        print(f"  {r['query_id']:<4} {r['olap_feature']:<18} "
              f"{r['rdbms_exec_ms']:>11.3f} {r['dw_exec_ms']:>9.3f} "
              f"{r_t:>12.3f} {d_t:>9.3f}  {'→ '+winner:<8} {speedup:>8}")

    # ② Verbosity
    print("\n\n  ② SQL VERBOSITY  (non-blank, non-comment lines)\n")
    print(f"  {'ID':<4} {'OLAP Feature':<18} {'RDBMS':>8} {'DW':>6} {'Ratio':>7}  Note")
    print("  " + "─" * 90)
    for r in results:
        ratio = r["lines_ratio"]
        note  = ("★ RDBMS much more verbose"   if ratio >= 3   else
                 "△ RDBMS moderately verbose"   if ratio >= 1.5 else
                 "≈ similar complexity")
        print(f"  {r['query_id']:<4} {r['olap_feature']:<18} "
              f"{r['rdbms_lines']:>8} {r['dw_lines']:>6} {ratio:>7.1f}x  {note}")

    # ③ Plan complexity
    print("\n\n  ③ QUERY PLAN NODES\n")
    print(f"  {'ID':<4} {'OLAP Feature':<18} "
          f"{'RDBMS joins':>12} {'DW joins':>9} "
          f"{'RDBMS agg':>10} {'DW agg':>7} "
          f"{'RDBMS scans':>12} {'DW scans':>9}")
    print("  " + "─" * 90)
    for r in results:
        print(f"  {r['query_id']:<4} {r['olap_feature']:<18} "
              f"{str(r['rdbms_joins']):>12} {str(r['dw_joins']):>9} "
              f"{str(r['rdbms_agg_nodes']):>10} {str(r['dw_agg_nodes']):>7} "
              f"{str(r['rdbms_seq_scans']):>12} {str(r['dw_seq_scans']):>9}")

    # ④ Summary
    valid = [r for r in results if r["rdbms_total_ms"] and r["dw_total_ms"]]
    dw_wins    = sum(1 for r in valid if r["dw_total_ms"]    < r["rdbms_total_ms"])
    rdbms_wins = sum(1 for r in valid if r["rdbms_total_ms"] < r["dw_total_ms"])
    avg_sp     = (sum(r["rdbms_total_ms"] / r["dw_total_ms"]
                      for r in valid if r["dw_total_ms"] > 0) / len(valid)) if valid else 0
    avg_ratio  = sum(r["lines_ratio"] for r in results) / len(results)

    print(f"\n\n  ④ SUMMARY\n")
    print(f"  Queries benchmarked        : {len(results)}")
    print(f"  DW faster                  : {dw_wins} / {len(valid)}")
    print(f"  RDBMS faster               : {rdbms_wins} / {len(valid)}")
    print(f"  Avg DW speedup             : {avg_sp:.2f}x over RDBMS")
    print(f"  Avg RDBMS verbosity ratio  : {avg_ratio:.1f}x more SQL lines than DW")
    print(f"\n{'='*W}\n")


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
    parser.add_argument("--runs",      type=int, default=3,
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
        print_report(results)

        src_dir = Path(__file__).resolve().parent
        save_csv(results, src_dir / "benchmark_results.csv")

    finally:
        rdbms_conn.close()
        dw_conn.close()


if __name__ == "__main__":
    main()
