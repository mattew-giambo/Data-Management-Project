# RDBMS vs Data Warehouse: A Comparative Performance and Architectural Analysis
### Data Management Project - Task 2

---

## Table of Contents

- [1. Problem Definition & Domain Context](#1-problem-definition--domain-context)
- [2. Architectural Comparison: RDBMS vs. DW (Star Schema)](#2-architectural-comparison-rdbms-3nf-vs-dw-star-schema)
  - [2.1 The Relational RDBMS Approach](#21-the-relational-rdbms-approach-3nf)
  - [2.2 The Data Warehouse Approach (Star Schema)](#22-the-data-warehouse-approach-star-schema)
- [3. Benchmark Methodology & Results](#3-benchmark-methodology--results)
  - [3.1 Benchmark Setup](#31-benchmark-setup)
  - [3.2 Empirical Benchmark Results](#32-empirical-benchmark-results)
- [6. Architectural Trade-offs & Discussion](#6-architectural-trade-offs--discussion)
- [7. Conclusions](#7-conclusions)

---

This report documents **Task 2** of the Data Management project, which required identifying a data analysis problem and comparing two different technological approaches to address it. The chosen domain is **green mobility and energy transition**, and the comparison is drawn between:
1. A **Relational Database Management System (RDBMS)** normalized in **Third Normal Form**, running on PostgreSQL (`green_mobility_rdbms`).
2. A **Data Warehouse (DW)** implemented as a **Relational OLAP (ROLAP) Star Schema** with full OLAP feature support, also running on PostgreSQL (`green_mobility`).

The benchmark evaluates both architectures across **11 analytical queries** designed to investigate the relationship between electric vehicle (EV) adoption, electricity grid cleanliness, and national $CO_2$ emissions. Performance was measured empirically using PostgreSQL's `EXPLAIN (ANALYZE, BUFFERS)` facility across 10 execution runs per query. 

Overall, the Data Warehouse star schema outperformed the 3NF relational database with an overall execution speedup of **1.37x** (24.47 ms total for DW vs. 33.48 ms for RDBMS). The DW achieved its highest speedups on queries that exploit native OLAP operators such as `CUBE`, `GROUPING SETS`, and window functions like `RANK()` (peaking at **3.43x** speedup for Q4). Furthermore, the star schema reduced SQL code verbosity by an average factor of **1.43x**, minimizing query complexity and potential human error.

---

## 1. Problem Definition & Domain Context

The core research question driving this comparative analysis is:

> **Does the widespread adoption of electric vehicles (EVs), combined with a cleaner electricity grid, lead to a measurable reduction in $CO_2$ emissions at country level, or does it shift pollution from vehicle tailpipes to fossil-fuel power plants?**

To answer this question, data was integrated from four sources:

| Dataset | Content |
|---|---|
| IEA EV Sales | Annual EV sales, stock and electricity demand by country, vehicle type and powertrain |
| IEA EV Infrastructure | Annual charging-point counts by country |
| OWID $CO_2$ | Annual $CO_2$ emissions, per-capita figures, GDP, population |
| OWID Energy | Annual electricity generation breakdown by source (renewable, fossil, nuclear, etc.) |

Eleven analytical queries (Q1 to Q11) were designed to examine this problem from multiple analytical angles, ranging from simple aggregations to multi-fact joins, window functions, and multi-dimensional roll-ups.

---

## 2. Architectural Comparison: RDBMS vs. DW (Star Schema)

### 2.1 The Relational RDBMS Approach

The relational schema ([sql/relational_schema.sql](sql/relational_schema.sql)) adheres to Third Normal Form. Every entity is normalized in its own table, and referential integrity is enforced through foreign keys and surrogate primary keys (`SERIAL`). The tables are:

| Table | Role |
|---|---|
| `Country` | Geographic dimension (iso code, continent) |
| `Year` | Temporal dimension (year, half-decade, pandemic period) |
| `VehicleType` | Vehicle category lookup |
| `Powertrain` | Powertrain technology lookup |
| `EVSales` | Association table: sales figures keyed by (country, year, vehicle type, powertrain) |
| `EVInfrastructure` | Association table: charging-point counts keyed by (country, year) |
| `CountryEnergy` | Association table: electricity generation data keyed by (country, year) |
| `CountryMacroeconomics` | Association table: GDP, population and $CO_2$ figures keyed by (country, year) |

This design completely avoids redundancies, but it introduces additional `JOIN` operations for every analytical query.

Data was loaded into the RDBMS using the standalone Python script [`load_db.py`](load_db.py), which reads the pre-cleaned CSVs produced by the ETL pipeline and populates all tables in dependency order.

---

### 2.2 The Data Warehouse Approach (Star Schema)

The Data Warehouse schema (`green_mobility`) organizes the same data into a classic **Multi-Fact Star Schema**, with four dimension tables and four fact tables that share composite primary keys:

| Table | Role |
|---|---|
| `CountryDim` | Country dimension |
| `YearDim` | Year dimension |
| `VehicleTypeDim` | Vehicle type dimension |
| `PowertrainDim` | Powertrain dimension |
| `EVMarket` | Central fact table (evSales, evStock, evSalesShare, evElectricityDemand) |
| `EVInfrastructure` | Fact table for charging infrastructure |
| `CountryEnergy` | Fact table for electricity generation |
| `CountryMacroeconomics` | Fact table for GDP, population, $CO_2$ |

The DW is populated through a dedicated ETL pipeline ([`etl.py`](../DW/etl.py)) that handles extraction, transformation and loading.

---

## 3. Benchmark Methodology & Results

### 3.1 Benchmark Setup

All queries were benchmarked using the Python script [`benchmark.py`](../benchmark.py), which wraps every query with PostgreSQL's `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)` directive and parses the output to extract:

- **Planning time** (ms): time the query planner spent generating an execution plan;
- **Execution time** (ms): time the engine spent actually executing the plan;
- **Total time** (ms): sum of planning and execution time.

Each query was run **10 times** on both databases. The reported values are the averages of the measured runs.

---

### 3.2 Empirical Benchmark Results

The raw results are stored in [`benchmark_results.csv`](../benchmark_results.csv). Below are the benchmark results for all 11 queries, sorted by Query ID:

| ID | Query Description | RDBMS Plan (ms) | RDBMS Exec (ms) | DW Plan (ms) | DW Exec (ms) | RDBMS Total (ms) | DW Total (ms) | DW Speedup |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **Q1** | EV Sales (Continent x Year) | 0.377 | 3.381 | 0.227 | 3.582 | 3.758 | 3.809 | **0.99x** |
| **Q2** | Renewable Electricity vs $CO_2$ | 0.344 | 3.208 | 0.323 | 3.104 | 3.552 | 3.427 | **1.04x** |
| **Q3** | Rich vs Poor Countries | 0.151 | 2.698 | 0.158 | 2.559 | 2.849 | 2.717 | **1.05x** |
| **Q4** | Top Countries by EV Stock | 0.144 | 7.162 | 0.123 | 2.005 | 7.306 | 2.129 | **3.43x** |
| **Q5** | Vehicle Type Analysis | 0.155 | 3.460 | 0.084 | 1.879 | 3.615 | 1.964 | **1.84x** |
| **Q6** | Pandemic Impact | 0.034 | 1.020 | 0.033 | 1.003 | 1.054 | 1.037 | **1.02x** |
| **Q7** | Infrastructure Growth | 0.150 | 0.441 | 0.078 | 0.345 | 0.591 | 0.424 | **1.39x** |
| **Q8** | Green Elec & High EV Demand | 0.268 | 0.393 | 0.269 | 0.389 | 0.661 | 0.658 | **1.00x** |
| **Q9** | Continent x Pandemic Period | 0.156 | 3.390 | 0.078 | 1.738 | 3.546 | 1.816 | **1.95x** |
| **Q10**| Renewable Share % | 0.088 | 2.302 | 0.085 | 2.319 | 2.391 | 2.404 | **0.99x** |
| **Q11**| Is EV Adoption Reducing $CO_2$? | 0.882 | 3.272 | 0.862 | 3.218 | 4.155 | 4.081 | **1.02x** |
| **Total**| **Cumulative Benchmarks** | **2.749** | **30.727** | **2.320** | **22.146** | **33.478** | **24.466** | **1.37x** |

Overall, the Data Warehouse (DW) model outperforms the standard RDBMS across most benchmarked scenarios, achieving a **1.37x** total execution speedup (33.48 ms total for RDBMS vs. 24.47 ms for DW) and demonstrating faster performance in 9 out of 11 queries.
The performance difference is particularly noticeable in complex analytical queries involving multiple joins and aggregations:
- **High speedup queries (Q4, Q5, Q9)**: The Data Warehouse achieves significant gains, peaking at **3.43x** for Q4 (Top Countries by EV Stock), **1.95x** for Q9 (Continent x Pandemic Period), and **1.84x** for Q5 (Vehicle Type Analysis). This improvement is primarily driven by the denormalized star schema, which minimizes costly runtime table joins and avoids repetitive table scans.
- **Moderate speedup queries (Q7)**: Query Q7 (Infrastructure Growth) shows a **1.39x** speedup, benefiting from native window functions (`LAG()`) over correlated self-joins.
- **Comparable queries (Q1–Q3, Q6, Q8, Q10, Q11)**: Lightweight queries exhibit almost identical performance (~0.99x to 1.05x speedup). In these cases, execution time is dominated by fixed PostgreSQL overhead rather than scanning large volumes of data, making both architectures equally fast.
---

<!-- ## 4. Detailed Performance & Execution Analysis

### 4.1 Scenario 1: Significant Data Warehouse Victories (High Speedup)

**Q4 - Top Countries by EV Stock (RANK window function)**: The DW executes in **2.59 ms** versus **9.97 ms** for the RDBMS - a speedup of **3.85x**. The DW uses PostgreSQL's built-in `RANK() OVER (PARTITION BY year ORDER BY SUM(evStock) DESC)` evaluated in a single pass over the fact table. The RDBMS equivalent requires a CTE materialisation followed by a self-join (`stock_by_country a LEFT JOIN stock_by_country b`) to count the number of countries with a higher stock in the same year. This is inherently O(n²) in the worst case and results in more join nodes in the query plan (2 vs 2, but with a much heavier self-join overhead).

**Q5 - Vehicle Type Analysis (CUBE)**: The DW completes in **2.86 ms** versus **6.86 ms** - a speedup of **2.39x**. The DW uses `GROUP BY CUBE(vehicleType, powertrain)`, which generates all four grouping combinations in a single scan of the `EVMarket` table (1 aggregation node). The RDBMS version must issue four separate `GROUP BY` queries connected by `UNION ALL`, resulting in 8 sequential scans and 4 aggregation nodes.

**Q9 - Continent x Pandemic Period (GROUPING SETS)**: The DW executes in **2.91 ms** versus **4.48 ms** - a speedup of **1.54x**. Similar to Q5, `GROUPING SETS` processes all four grouping levels in one pass, while the RDBMS requires four `UNION ALL` blocks scanning the data multiple times.

### 4.2 Queries Where the Two Approaches Are Comparable

**Q2, Q6, Q7, Q8, Q10, Q11**: These queries use standard SQL constructs (simple `GROUP BY`, arithmetic ratios, `MIN/MAX` aggregations, multi-table joins) that translate directly between the two paradigms with no structural disadvantage on either side. The speedup differences are all below 1.25x and could be attributed to minor variance in buffer cache state rather than a genuine architectural advantage.

**Q12 - Is EV Adoption Reducing $CO_2$?**: Interestingly, the RDBMS is marginally faster here (**6.21 ms** vs **6.68 ms**). Both versions perform a three-fact-table join of identical logical complexity. The RDBMS planner may have produced a slightly more efficient join order given the surrogate key statistics available to it.

### 4.3 The RDBMS Win: Q6
**Q6 - Pandemic Impact** is the only query where the RDBMS is clearly faster (**1.39 ms** vs **1.77 ms**). This is a very simple single-table aggregation (`AVG(ev_sales_share) GROUP BY pandemic_period`). The RDBMS stores `pandemic_period` directly in the `Year` lookup table; the DW stores it in `YearDim`. Both schemas require one join, and the slight RDBMS advantage here is likely due to the smaller number of rows in `EVSales` compared to `EVMarket` after filtering, combined with random variation.

---

## 5. SQL Code Verbosity Comparison

In addition to query execution time, another key dimension of comparison is **SQL code complexity and verbosity**. The table below compares non-blank, non-comment lines of SQL required for each query implementation:

| ID | Analytical Concept | RDBMS 3NF Lines | DW Star Schema Lines | Verbosity Ratio | Structural Cause |
|---|---|---:|---:|---:|---|
| **Q1** | `ROLLUP` | 23 | 16 | **1.4x** | 3 `UNION ALL` blocks vs native `ROLLUP` |
| **Q2** | Multi-fact JOIN | 12 | 12 | **1.0x** | Identical 2-fact join pattern |
| **Q3** | `CASE` + `GROUP BY` | 15 | 15 | **1.0x** | Identical conditional logic |
| **Q4** | `RANK()` Window Function | 21 | 12 | **1.8x** | CTE + Self-join vs native `RANK()` |
| **Q5** | `CUBE` | 31 | 9 | **3.4x** | 4 `UNION ALL` blocks vs native `CUBE` |
| **Q6** | Simple `GROUP BY` | 7 | 6 | **1.2x** | Minor table alias difference |
| **Q7** | `LAG()` Window Function | 22 | 16 | **1.4x** | Correlated self-join vs `LAG()` |
| **Q8** | Multi-fact + Filter | 15 | 15 | **1.0x** | Identical join structure |
| **Q9** | `GROUPING SETS` | 31 | 13 | **2.4x** | 4 `UNION ALL` blocks vs `GROUPING SETS` |
| **Q10**| Arithmetic Ratio | 13 | 13 | **1.0x** | Identical formula structure |
| **Q11**| 3-Fact Join (Core Test) | 21 | 21 | **1.0x** | Identical 3-fact join structure |
| **Total**| **Overall SQL Lines** | **211** | **148** | **1.43x** | **RDBMS requires 43% more code** |

### 5.1 Key Takeaway on Verbosity

For queries using standard SQL operators (Q2, Q3, Q8, Q10, Q11), both paradigms require identical code length. However, when multi-dimensional OLAP syntax (`CUBE`, `GROUPING SETS`, `ROLLUP`) or window functions are required, **the RDBMS requires up to 3.4x more SQL code**. Writing manual `UNION ALL` blocks increases the risk of copy-paste logic errors, while concise OLAP queries improve readability and maintainability. -->

---

## 6. Architectural Trade-offs & Discussion

| Aspect | Relational RDBMS | Data Warehouse (Star Schema) |
|---|---|---|
| **Data Redundancy** | **Zero redundancy**. Fully normalized according to 3NF rules. | **Controlled redundancy**. Dimension tables store denormalized temporal/geographic attributes. |
| **Query Performance** | Slower on multi-dimensional aggregations and window rankings (**33.48 ms** total). | **Faster overall** (**24.47 ms** total, up to **3.43x speedup** on complex queries). |
| **Query Complexity** | **Higher**. Lacks native OLAP operators; requires verbose `UNION ALL` blocks and self-joins. | **Lower**. Native `CUBE`, `ROLLUP`, `GROUPING SETS`, and window functions keep SQL concise. |
| **ETL Pipeline** | **Simpler initial load**. Row-by-row mapping of surrogate keys in Python ([load_db.py](load_db.py)). | **Dedicated ETL Pipeline**. Requires extraction, transformation, dimension key mapping, and multi-fact staging ([etl.py](../DW/etl.py)). |
| **Primary Use Case** | Transactional processing (OLTP), single-record inserts, updates, and delete operations. | Analytical reporting (OLAP), trend analysis, and business intelligence dashboards. |

---

## 7. Conclusions

This benchmark confirms the theoretical foundations of Data Warehousing vs. Relational Database design:

1. **Superior Analytical Performance**: For analytical workloads involving multi-dimensional aggregations and ranking, the Data Warehouse Star Schema is clearly superior. It executed faster on 9 out of 11 queries, achieving a cumulative speedup of **1.37x** and peak speedups of **3.43x** (Q4), **1.95x** (Q9), and **1.84x** (Q5).
2. **Impact of Native OLAP Operators**: The performance gap is directly proportional to the use of OLAP-specific operators. While relational databases must emulate these features via `UNION ALL` passes and self-joins, the Data Warehouse computes multiple aggregation levels in a single scan of the fact table using `CUBE`, `GROUPING SETS` or window functions.
3. **Developer Productivity & Code Clarity**: The Data Warehouse reduces SQL code verbosity significantly for complex queries. The RDBMS required more SQL code than the DW. Concise queries lower the risk of logical errors.

In the context of this project, the DW approach proved better suited to answering the core research question, whether EV adoption correlates with lower $CO_2$ emissions, because the answer requires joining multiple fact tables, computing aggregations across multiple dimensions, and performing trend analysis across years and countries.
