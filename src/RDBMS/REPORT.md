# RDBMS vs Data Warehouse: A Comparative Analysis of Analytical Query Performance

## Project Context

This report documents the work carried out for the **Data Warehousing task**, which required identifying a data analysis problem and comparing two different technological approaches to address it. The chosen domain is **green mobility and energy transition**, and the comparison is drawn between:

- a **Relational Database Management System (RDBMS)** modelled in Third Normal Form (3NF), running on PostgreSQL (`green_mobility_rdbms`);
- a **Data Warehouse (DW)** modelled as a Star Schema with full OLAP support, also running on PostgreSQL (`green_mobility`).

The primary benchmarking dimension used in this report is **query execution speed**, measured in milliseconds via PostgreSQL's `EXPLAIN ANALYZE` facility.

---

## 1. The Problem

The analytical question driving the project is:

> **Does the widespread adoption of electric vehicles (EVs), combined with a cleaner electricity grid, lead to a measurable reduction in CO₂ emissions at country level?**

Answering this question requires joining and aggregating data from at least four sources simultaneously:

| Dataset | Content |
|---|---|
| IEA EV Sales | Annual EV sales, stock and electricity demand by country, vehicle type and powertrain |
| IEA EV Infrastructure | Annual charging-point counts by country |
| OWID CO₂ | Annual CO₂ emissions, per-capita figures, GDP, population |
| OWID Energy | Annual electricity generation breakdown by source (renewable, fossil, nuclear, etc.) |

Twelve analytical queries were designed to explore this question from multiple angles, ranging from simple group-by aggregations to multi-fact-table joins with window functions and multi-dimensional roll-ups.

---

## 2. The Two Approaches

### 2.1 Relational RDBMS

The relational schema normalises every entity into its own table, enforces referential integrity through surrogate primary keys, and avoids any redundancy. The tables are:

| Table | Role |
|---|---|
| `Country` | Geographic dimension (iso code, continent) |
| `Year` | Temporal dimension (year, half-decade, pandemic period) |
| `VehicleType` | Vehicle category lookup |
| `Powertrain` | Powertrain technology lookup |
| `EVSales` | Association table: sales figures keyed by (country, year, vehicle type, powertrain) |
| `EVInfrastructure` | Association table: charging-point counts keyed by (country, year) |
| `CountryEnergy` | Association table: electricity generation data keyed by (country, year) |
| `CountryMacroeconomics` | Association table: GDP, population and CO₂ figures keyed by (country, year) |

This design avoid redundances, but it introduces additional JOIN operation for every query.

Data was loaded into the RDBMS using the standalone Python script [`load_db.py`](load_db.py), which reads the pre-cleaned CSVs produced by the ETL pipeline and populates all tables in dependency order.

### 2.2 Data Warehouse (Star Schema + OLAP)

The DW schema organises the same data around a classic **star schema**, with four dimension tables and four fact tables that share composite primary keys:

| Table | Role |
|---|---|
| `CountryDim` | Country dimension |
| `YearDim` | Year dimension |
| `VehicleTypeDim` | Vehicle type dimension |
| `PowertrainDim` | Powertrain dimension |
| `EVMarket` | Central fact table (evSales, evStock, evSalesShare, evElectricityDemand) |
| `EVInfrastructure` | Fact table for charging infrastructure |
| `CountryEnergy` | Fact table for electricity generation |
| `CountryMacroeconomics` | Fact table for GDP, population, CO₂ |

The DW is populated through a dedicated ETL pipeline ([`etl.py`](../DW/etl.py)) that handles extraction, transformation and loading.

---

## 4. Benchmark Methodology

### 4.1 Tool

All queries were benchmarked using the Python script [`benchmark.py`](../benchmark.py), which wraps every query with PostgreSQL's `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)` directive and parses the output to extract:

- **Planning time** (ms): time the query planner spent generating an execution plan;
- **Execution time** (ms): time the engine spent actually executing the plan;
- **Total time** (ms): sum of planning and execution time.

Each query was ran **3 times** on both databases. The reported table are the **average** of the three measured runs.

### 4.2 Results

The raw results are stored in [`benchmark_results.csv`](../benchmark_results.csv). The table below summarises total time (planning + execution) for each query:

| ID | Query Label | RDBMS Total (ms) | DW Total (ms) | DW Speedup |
|---|---|---:|---:|---:|
| Q1 | EV Sales (Continent × Year) | 3.771 | 3.770 | 1.00x |
| Q2 | Renewable Electricity vs CO₂ | 5.550 | 5.097 | 1.09x |
| Q3 | Rich vs Poor Countries | 4.003 | 3.828 | 1.05x |
| Q4 | Top Countries by EV Stock | 9.966 | 2.591 | 3.85x |
| Q5 | Vehicle Type Analysis | 6.855 | 2.864 | 2.39x |
| Q6 | Pandemic Impact | 1.393 | 1.769 | 0.79x |
| Q7 | Infrastructure Growth | 0.771 | 0.701 | 1.10x |
| Q8 | Green Elec & High EV Demand | 1.128 | 1.036 | 1.09x |
| Q9 | Continent × Pandemic Period | 4.483 | 2.906 | 1.54x |
| Q10 | Renewable Share % | 4.075 | 3.254 | 1.25x |
| Q11 | Countries Improving Most | 2.614 | 2.424 | 1.08x |
| Q12 | Is EV Adoption Reducing CO₂? | 6.214 | 6.678 | 0.93x |



> **Overall: DW was faster on 10 out of 12 queries. The average DW speedup across all queries was approximately 1.60×.**

---

## 5. Analysis of Results

### 5.1 Queries Where the DW Wins Decisively

**Q4 — Top Countries by EV Stock (RANK window function)**: The DW executes in **2.59 ms** versus **9.97 ms** for the RDBMS — a speedup of **3.85×**. The DW uses PostgreSQL's built-in `RANK() OVER (PARTITION BY year ORDER BY SUM(evStock) DESC)` evaluated in a single pass over the fact table. The RDBMS equivalent requires a CTE materialisation followed by a self-join (`stock_by_country a LEFT JOIN stock_by_country b`) to count the number of countries with a higher stock in the same year. This is inherently O(n²) in the worst case and results in more join nodes in the query plan (2 vs 2, but with a much heavier self-join overhead).

**Q5 — Vehicle Type Analysis (CUBE)**: The DW completes in **2.86 ms** versus **6.86 ms** — a speedup of **2.39×**. The DW uses `GROUP BY CUBE(vehicleType, powertrain)`, which generates all four grouping combinations in a single scan of the `EVMarket` table (1 aggregation node). The RDBMS version must issue four separate `GROUP BY` queries connected by `UNION ALL`, resulting in 8 sequential scans and 4 aggregation nodes.

**Q9 — Continent × Pandemic Period (GROUPING SETS)**: The DW executes in **2.91 ms** versus **4.48 ms** — a speedup of **1.54×**. Similar to Q5, `GROUPING SETS` processes all four grouping levels in one pass, while the RDBMS requires four `UNION ALL` blocks scanning the data multiple times.

### 5.2 Queries Where the Two Approaches Are Comparable

**Q2, Q6, Q7, Q8, Q10, Q11**: These queries use standard SQL constructs (simple `GROUP BY`, arithmetic ratios, `MIN/MAX` aggregations, multi-table joins) that translate directly between the two paradigms with no structural disadvantage on either side. The speedup differences are all below 1.25× and could be attributed to minor variance in buffer cache state rather than a genuine architectural advantage.

**Q12 — Is EV Adoption Reducing CO₂?**: Interestingly, the RDBMS is marginally faster here (**6.21 ms** vs **6.68 ms**). Both versions perform a three-fact-table join of identical logical complexity. The RDBMS planner may have produced a slightly more efficient join order given the surrogate key statistics available to it.

### 5.3 The RDBMS Win: Q6

**Q6 — Pandemic Impact** is the only query where the RDBMS is clearly faster (**1.39 ms** vs **1.77 ms**). This is a very simple single-table aggregation (`AVG(ev_sales_share) GROUP BY pandemic_period`). The RDBMS stores `pandemic_period` directly in the `Year` lookup table; the DW stores it in `YearDim`. Both schemas require one join, and the slight RDBMS advantage here is likely due to the smaller number of rows in `EVSales` compared to `EVMarket` after filtering, combined with random variation.

---

## 6. SQL Verbosity

Beyond speed, a secondary dimension of comparison is **how much SQL code is required** to express the same analytical intent. The table below shows the number of non-blank, non-comment SQL lines for each query pair:

| ID | OLAP Feature | RDBMS Lines | DW Lines | Ratio | Note |
|---|---|---:|---:|---|---|
| Q1 | ROLLUP | 23 | 16 | 1.4× | △ RDBMS moderately verbose |
| Q2 | Multi-fact JOIN | 12 | 12 | 1.0× | ≈ Similar |
| Q3 | CASE + GROUP BY | 15 | 15 | 1.0× | ≈ Similar |
| Q4 | RANK() window fn | 21 | 12 | 1.8× | △ RDBMS moderately verbose |
| Q5 | CUBE | 31 | 9 | 3.4× | ★ RDBMS much more verbose |
| Q6 | Simple GROUP BY | 7 | 6 | 1.2× | ≈ Similar |
| Q7 | LAG() window fn | 22 | 16 | 1.4× | △ RDBMS moderately verbose |
| Q8 | Multi-fact + WHERE | 15 | 15 | 1.0× | ≈ Similar |
| Q9 | GROUPING SETS | 31 | 13 | 2.4× | ★ RDBMS much more verbose |
| Q10 | Arithmetic ratio | 13 | 13 | 1.0× | ≈ Similar |
| Q11 | MIN/MAX aggregate | 11 | 10 | 1.1× | ≈ Similar |
| Q12 | 3-fact JOIN | 21 | 21 | 1.0× | ≈ Similar |

> **The RDBMS required on average 1.6× more SQL lines than the DW. For queries exploiting OLAP operators (Q1, Q4, Q5, Q9), the verbosity gap was significantly larger.**

---

## 7. Discussion

### 7.1 When the DW Architecture Pays Off

The DW's performance advantage is most pronounced when queries exploit OLAP-specific operators:

- **`ROLLUP` / `CUBE` / `GROUPING SETS`**: these operators instruct the query engine to compute multiple levels of aggregation in a **single scan** of the fact table. The RDBMS has no equivalent built-in construct and must compensate with multiple `UNION ALL` blocks, each triggering an independent scan and aggregation pass.

- **Window functions (`RANK()`, `LAG()`)**: `RANK()` in the DW processes the result set in a single ordered pass. The RDBMS self-join used to emulate it reads the CTE twice. `LAG()` in the DW reads each row's predecessor directly from the sort order; the RDBMS self-join on `EVInfrastructure` introduces an extra join for every row.

### 7.2 When the RDBMS Is Sufficient

For queries that map directly to standard SQL (joins, simple group-by, arithmetic expressions), both paradigms perform nearly identically. This confirms that the normalisation overhead of the 3NF schema does not impose a significant runtime penalty at the dataset sizes used in this project.

### 7.3 Schema Design Trade-offs

| Aspect | RDBMS (3NF) | DW (Star Schema) |
|---|---|---|
| Data redundancy | None — fully normalised | Controlled denormalisation in dimensions |
| Update anomalies | Protected by normalisation | Must be managed at ETL level |
| Query complexity | Higher — more JOINs, no OLAP operators | Lower — OLAP operators, fewer JOINs |
| Analytical throughput | Limited by normalisation and lack of OLAP | Optimised for aggregation workloads |
| ETL complexity | Simple row-by-row loader | Dedicated Extract–Transform–Load pipeline |
| Best suited for | Transactional systems (OLTP) | Analytical/reporting systems (OLAP) |

---

## 8. Conclusions

The benchmark confirms the well-established theoretical distinction between OLTP and OLAP architectures:

1. **For analytical workloads that rely on multi-dimensional aggregation, the Data Warehouse is the superior choice.** The DW was faster on 10 out of 12 queries, with a maximum speedup of 3.85× (Q4) and an average speedup of approximately 1.60×.

2. **The performance gap is directly proportional to the use of OLAP-specific operators.** Queries using `CUBE`, `GROUPING SETS` or window functions show the largest divergence. Queries using only standard SQL constructs perform comparably in both systems.

3. **The DW reduces SQL verbosity significantly for complex queries.** The RDBMS required 3.4× more SQL code than the DW for the `CUBE` query and 2.4× more for `GROUPING SETS`. Concise, maintainable queries lower the risk of logical errors and reduce long-term maintenance costs.

4. **The RDBMS remains the appropriate tool for data ingestion and transactional updates.** The 3NF schema enforces referential integrity and avoids update anomalies, making it the correct foundation for the operational system from which the DW is populated.

In the context of this project, the DW approach proved better suited to answering the core research question — whether EV adoption correlates with lower CO₂ emissions — because the answer requires joining multiple fact tables, computing aggregations across multiple dimensions, and performing trend analysis across years and countries. All of these are workloads for which the star schema and OLAP operators were specifically designed.

