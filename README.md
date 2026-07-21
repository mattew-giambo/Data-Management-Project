# Green Mobility Data Warehouse
### Data Management Project — MSc in Computer Science

> **Task 1 — Data Staging, Warehousing & OLAP**  
> A dimensional data warehouse built to study whether the global rise of electric vehicles is actually reducing carbon emissions, or simply shifting them from the tailpipe to the power plant.

---

## Table of Contents

1. [Project Overview & Objectives](#1-project-overview--objectives)
2. [Datasets & Data Preparation](#2-datasets--data-preparation)
3. [Data Warehousing & Methodology](#3-data-warehousing--methodology)
4. [Final Datasets & Attribute Dictionary](#4-final-datasets--attribute-dictionary)
5. [OLAP Queries & Analytical Insights](#5-olap-queries--analytical-insights)
6. [Project Structure & How to Run](#6-project-structure--how-to-run)

---

## 1. Project Overview & Objectives

The central question driving this project is deceptively simple: **does buying an electric car actually help the planet?** The answer depends entirely on where the electricity comes from. A BEV charged on a coal-dominated grid may emit more CO₂ over its lifetime than an efficient petrol car — the emission is just invisible at the point of consumption.

This project builds a **Data Warehouse** (DW) that integrates three heterogeneous open-access datasets to investigate this question at a national level, for **50 countries** over the period **2010–2023**. The two core analytical goals defined in the project proposal are:

1. **EV Impact Assessment** — Analyse whether EV adoption leads to a net reduction in national CO₂ emissions, cross-referencing the electricity generation mix to detect the *grid-shift* effect (fossil-fuelled charging).
2. **Economic Transition Disparity** — Compare the pace and depth of the EV transition between high-GDP and low-GDP countries, exploring whether financial capacity is a bottleneck for the energy transition.

The DW is designed following the **Kimball dimensional modelling methodology** (Star Schema with Conformed Dimensions), enabling OLAP-style queries with `ROLLUP`, `CUBE`, and `GROUPING SETS`, as well as window functions for trend analysis.

---

## 2. Datasets & Data Preparation

### 2.1 Source Datasets

Three primary datasets were used, plus three auxiliary datasets added during the ETL phase to address data quality gaps discovered during profiling.

#### Primary Datasets

| # | Name | Source | Raw Size | Granularity |
|---|------|--------|----------|-------------|
| 1 | **IEA Global EV Sales** (2010–2023) | International Energy Agency / Kaggle | 12,654 rows × 8 cols | `[Country, Year, Vehicle Mode, Powertrain, Parameter]` |
| 2 | **OWID CO₂ & GHG Emissions** | Our World in Data / Global Carbon Project | 50,411 rows × 79 cols | `[Country, Year]` |
| 3 | **OWID Energy Dataset** | Our World in Data / BP / Ember / IEA | 23,377 rows × 130 cols | `[Country, Year]` |

#### Auxiliary Datasets (added post-proposal)

These three datasets were not part of the original project proposal but became necessary to address gaps found during data profiling:

| # | Name | Source | Purpose |
|---|------|--------|---------|
| 4 | **World Bank GDP & Population** | World Bank Open Data | The GDP and population figures in OWID use constant 2011 PPP dollars, which made per-capita derivations inconsistent. World Bank current-USD figures were used to patch and override OWID's macroeconomic columns with a more authoritative and uniform source. |
| 5 | **continent\_country.csv** | ISO standard lookup | The IEA dataset has no continent field. This ISO-based mapping was used to enrich the geographical dimension (`CountryDim`) with `continent` and `continentCode`, enabling continent-level roll-ups in OLAP queries. |
| 6 | **Ember Global Electricity Generation** | Ember Climate | OWID's energy dataset has significant null rates on electricity generation metrics (up to ~70%). The Ember dataset — which covers the same metrics with broader country coverage — was used to patch those missing values before loading into the DW. |

**Note on Dataset 4 (World Bank Development Indicators):** The original project proposal listed this dataset as optional. After profiling, we confirmed that GDP and population are already present in the OWID datasets — the World Bank dataset was therefore used only to *replace* those columns with higher-quality figures (current USD, broader coverage), not as a separate analytical source. The OWID columns themselves were sufficient as fallback.

---

### 2.2 Attribute Selection Rationale

Each raw dataset was profiled before any transformation. Here is the reasoning behind what was kept and what was dropped.

#### IEA EV Sales — kept attributes

The raw file is in **long format** (one metric per row, stored in a `parameter` column). The relevant parameters were: `EV sales`, `EV stock`, `EV sales share`, `EV stock share`, `Electricity demand`. Two parameters — `Oil displacement Mbd` and `Oil displacement, million lge` — were **dropped**: they represent derived oil-equivalent estimates that add no independent analytical value and are not comparable across different vehicle categories.

The `category` column (Historical / Projection-STEPS / Projection-APS) was used exclusively as a **filter** and then discarded: only `Historical` rows were retained, so the column itself is meaningless in the output.

#### OWID CO₂ — kept attributes

Out of 79 columns, 14 were selected. Dropped columns include: cumulative historical emissions (not relevant for year-by-year analysis), trade-adjusted consumption emissions (interesting but not needed for Task 1), and all GHG gases other than CO₂ (out of scope). The `iso_code` column — null for macro-regions like "Africa (GCP)" — was used as the primary filter to remove non-national rows.

#### OWID Energy — kept attributes

Out of 130 columns, 20 were selected. The full energy generation mix by source was kept (coal, gas, oil, nuclear, hydro, solar, wind, other renewables) because the project's core question requires knowing *how* electricity is produced, not just how much. Dropped: energy *consumption* by sector (residential, industrial, etc.), per-capita energy metrics (recalculated from scratch), and all non-electricity energy carrier details (e.g., primary energy by fuel type in EJ).

---

### 2.3 Data Cleaning Process

The full cleaning logic is implemented in [`src/utility/transform.py`](src/utility/transform.py). Below is a step-by-step account.

#### Step 1 — Removing Projections and Aligning Time Ranges

The IEA dataset contains 3,480 rows of future projections (2020–2035, labelled `Projection-STEPS` and `Projection-APS`). These were removed by filtering `category == 'Historical'`. The OWID Energy dataset contains 106 rows for 2025 (preliminary Ember estimates). All three datasets were then clipped to `2010 ≤ year ≤ 2023`, the only range where all sources overlap with complete historical coverage.

#### Step 2 — Resolving Geographic Conflicts

The IEA dataset does not use ISO codes and contains non-standard country names. A multi-stage matching strategy was implemented:
1. **Exact match** against a dictionary built from OWID's `(country, iso_code)` pairs.
2. **Cleaned match** — stripping words like "Republic of", "Kingdom of", etc. — to catch formal names.
3. **Hardcoded special cases** (e.g., `Korea` → `South Korea`).
4. **Fuzzy match** using `difflib.get_close_matches` with a 0.6 similarity cutoff as a last resort.

Macro-regional rows (`World`, `Europe`, `EU27`, `Rest of the world` in IEA; all rows with `iso_code IS NULL` in OWID) were removed entirely to avoid **double-counting** in aggregate queries.

#### Step 3 — Pivoting the EV Dataset (Long → Wide)

The IEA data was pivoted from long to wide format using `pivot_table`, separating charging infrastructure (`EV charging points`) into a dedicated table (`EVInfrastructure`) to avoid granularity conflicts with vehicle market data. The resulting `EVMarket` table is indexed at `[Country, Year, Vehicle Mode, Powertrain]`.

#### Step 4 — Handling Missing Values

A deliberate asymmetry was applied:
- **EV measures** (sales, stock, shares, electricity demand): `NaN` values generated by the pivot — meaning a country simply had no activity for that combination — were **imputed to `0.0`**. Zero is the semantically correct value here.
- **Macroeconomic and energy measures** (GDP, population, CO₂, electricity generation): `NaN` values were **kept as `NULL`**. Replacing a missing GDP with zero would completely distort `AVG()` and ratio calculations in OLAP queries.

#### Step 5 — Patching Energy Data with Ember

After cleaning, OWID's electricity generation columns still had significant null rates. A left join with the Ember dataset (filtered to `Area type == 'Country or economy'`, pivoted on `Electricity source`) was performed, and `fillna()` was applied column-by-column to patch only the missing values without overwriting existing OWID data.

#### Step 6 — Replacing GDP and Population with World Bank Data

For both `co2_clean` and `energy_clean`, the World Bank dataset (after melting and pivoting by `Series Code`) was joined on `(isoCode, year)`. The World Bank values were preferred where available; OWID values served as fallback.

#### Step 7 — Recalculating Derived Indicators

After replacing the population and GDP bases, ratio indicators were recalculated from scratch to ensure internal consistency:

```
co2PerCapita = (co2Emissions × 10⁶) / population
co2PerGDP    = (co2Emissions × 10⁹) / GDP
```

This avoids inheriting stale ratios from the OWID source that were computed against different base figures.

#### Final Validation Results

| Dataset | Rows | ISO Nulls | Year Range |
|---------|------|-----------|------------|
| `clean_iea_ev_sales.csv` | ~4,259 | 0 | 2010–2023 |
| `clean_iea_ev_infrastructure.csv` | ~650 | 0 | 2010–2023 |
| `clean_owid_co2.csv` | ~3,052 | 0 | 2010–2023 |
| `clean_owid_energy.csv` | ~3,078 | 0 | 2010–2023 |

100% geographic coverage: all 50 ISO codes in the EV dataset exist in both CO₂ and Energy datasets, guaranteeing referential integrity in the DW.

---

## 3. Data Warehousing & Methodology

### 3.1 Design Approach

The DW was designed following the **Dimensional Fact Model (DFM)** methodology, as introduced in the course lectures. The DFM prescribes identifying fact events, their measures, and the analytical dimensions along which measures should be aggregated before committing to a physical schema.

The key modelling decision was splitting the data across **multiple fact tables** rather than forcing everything into a single one. The reason is a well-known dimensional modelling pitfall: **fan-out** (also called the *chasm trap*). The EV Sales data has a finer granularity (`Country × Year × Vehicle Mode × Powertrain`) than the CO₂ and Energy data (`Country × Year`). A naive join would replicate each country's CO₂ value once per vehicle/powertrain combination, making any `SUM(co2)` query return inflated results by a factor equal to the number of active EV categories per country-year.

The solution is the **Multi-Fact Star Schema** with **Conformed Dimensions**, the standard Kimball pattern for this problem: shared dimension tables (`CountryDim`, `YearDim`) act as the integration bridge between fact tables, and cross-fact queries are expressed as **Drill-Across** operations (separate queries joined on conformed keys).

### 3.2 Schema Design

The physical schema (`src/DW/init.sql`) implements a **Star Schema** with 4 dimension tables and 4 fact tables.

![DFM Schema](DFM%20Schema/assets/DFM_star.png)

#### Dimension Tables

| Table | PK | Description |
|-------|----|-------------|
| `CountryDim` | `keyC` | Countries enriched with ISO code and continent. Acts as a conformed dimension shared by all fact tables. |
| `YearDim` | `keyY` | Years enriched with two analytical groupings: `halfDecade` (2010–2014 / 2015–2019 / 2020–2023) and `pandemicPeriod` (Pre-Pandemic / Pandemic / Post-Pandemic). These pre-baked groupings avoid redundant `CASE WHEN` logic in every query. |
| `VehicleTypeDim` | `keyV` | Vehicle segment: Cars, Buses, Vans, Trucks. Used only by `EVMarket`. |
| `PowertrainDim` | `keyP` | Powertrain technology: BEV, PHEV, FCEV. Used only by `EVMarket`. |

#### Fact Tables

| Table | Grain | Measure Type |
|-------|-------|--------------|
| `EVMarket` | Country × Year × Vehicle Type × Powertrain | EV sales KPIs |
| `EVInfrastructure` | Country × Year | Charging point counts |
| `CountryEnergy` | Country × Year | Electricity generation by source |
| `CountryMacroeconomics` | Country × Year | CO₂ emissions + macroeconomic indicators |

The two infrastructure-side fact tables (`CountryEnergy`, `CountryMacroeconomics`) share only `CountryDim` and `YearDim` with `EVMarket`, avoiding any fan-out while enabling drill-across queries that connect EV adoption data with emissions and grid mix data.

### 3.3 Measure Additivity

Following the DFM classification discussed in class:

- **Flow Measures** (fully additive over all dimensions): `evSales`, `evElectricityDemand`, `co2Emissions`, `co2EmissionsOil`, `co2EmissionsCoal`, `electricityGeneration`, `renewableElectricityGeneration`, etc.
- **Level Measures** (additive across space, non-additive over time): `evStock`, `evChargingPoints`, `population`, `GDP`. Summing the stock of EVs in 2020 and 2021 makes no sense; summing the stocks of Germany and France does.
- **Unit Measures** (non-additive, ratio-based): `evSalesShare`, `evStockShare`, `co2PerCapita`, `co2PerGDP`. These must be aggregated with `AVG`, `MIN`, or `MAX` — never `SUM`.

---

## 4. Final Datasets & Attribute Dictionary

### 4.1 `clean_iea_ev_sales.csv` — EV Market Data

Granularity: one row per `[Country × Year × Vehicle Type × Powertrain]`.

| Column | Type | Description |
|--------|------|-------------|
| `country` | VARCHAR | Full country name (standardised to OWID conventions). |
| `isoCode` | CHAR(3) | ISO 3166-1 alpha-3 code. Primary geographic key. |
| `continent` | VARCHAR | Continent name derived from the ISO country mapping. |
| `continentCode` | CHAR(2) | Two-letter continent code (e.g., `EU`, `AS`, `NA`). |
| `year` | INT | Reference year (2010–2023). |
| `halfDecade` | VARCHAR | Pre-baked time grouping: `2010-2014`, `2015-2019`, `2020-2023`. |
| `pandemicPeriod` | VARCHAR | Pre-baked pandemic grouping: `Pre-Pandemic`, `Pandemic`, `Post-Pandemic`. |
| `vehicleType` | VARCHAR | Vehicle segment: `Cars`, `Buses`, `Vans`, `Trucks`. |
| `powertrain` | VARCHAR | Propulsion technology: `BEV`, `PHEV`, `FCEV`. |
| `evSales` | FLOAT | Number of new EVs sold in the reference year. **Flow measure**, fully additive. |
| `evSalesShare` | FLOAT | EV sales as a percentage of total new vehicle sales. **Unit measure**, use AVG only. |
| `evStock` | FLOAT | Total active EV fleet on the road at year-end. **Level measure**, non-additive over time. |
| `evStockShare` | FLOAT | EV stock as a percentage of all registered vehicles. **Unit measure**. |
| `evElectricityDemand` | FLOAT | Electricity consumed by the EV fleet in GWh. **Flow measure**, fully additive. |
| `population` | FLOAT | Country population (patched with World Bank data). Used as a normalization denominator. |
| `GDP` | FLOAT | GDP in current USD (World Bank). Used for economic stratification queries. |

### 4.2 `clean_iea_ev_infrastructure.csv` — Charging Infrastructure

Granularity: one row per `[Country × Year]`.

| Column | Type | Description |
|--------|------|-------------|
| `country` | VARCHAR | Full country name. |
| `isoCode` | CHAR(3) | ISO code. Geographic key for joins with dimension tables. |
| `continent` | VARCHAR | Continent name. |
| `continentCode` | CHAR(2) | Continent code. |
| `year` | INT | Reference year (2010–2023). |
| `halfDecade` | VARCHAR | Pre-baked time grouping. |
| `pandemicPeriod` | VARCHAR | Pre-baked pandemic grouping. |
| `evChargingPoints` | FLOAT | Total publicly available EV charging points (fast + slow). **Level measure**. |
| `fastChargingPoints` | FLOAT | Publicly available fast-charging stations only. **Level measure**. |
| `slowChargingPoints` | FLOAT | Publicly available slow-charging stations only. **Level measure**. |
| `chargingPointsPerEv` | FLOAT | Ratio of total charging points to total EV stock. Derived measure for infrastructure readiness analysis. Non-additive; use AVG. |

### 4.3 `clean_owid_co2.csv` — Emissions & Macroeconomics

Granularity: one row per `[Country × Year]`.

| Column | Type | Description |
|--------|------|-------------|
| `country` | VARCHAR | Full country name. |
| `isoCode` | CHAR(3) | ISO code. Conformed dimension key. |
| `continent` | VARCHAR | Continent name. |
| `continentCode` | CHAR(2) | Continent code. |
| `year` | INT | Reference year (2010–2023). |
| `halfDecade` | VARCHAR | Pre-baked time grouping. |
| `pandemicPeriod` | VARCHAR | Pre-baked pandemic grouping. |
| `population` | FLOAT | Country population (World Bank primary, OWID fallback). |
| `GDP` | FLOAT | GDP in current USD (World Bank primary, OWID PPP fallback). |
| `co2Emissions` | FLOAT | Total CO₂ from fossil fuels and industry (million tonnes). Core project measure. **Flow measure**. |
| `co2PerCapita` | FLOAT | CO₂ per person (tonnes). Recalculated from `co2Emissions / population`. **Unit measure**. |
| `co2PerGDP` | FLOAT | CO₂ per unit of GDP (kg CO₂ per USD). Recalculated. **Unit measure**. Measures carbon intensity of economic activity. |
| `co2EmissionsOil` | FLOAT | CO₂ from oil combustion (million tonnes). Proxy for transport fuel emissions; expected to decline with EV adoption. **Flow measure**. |
| `co2EmissionsOilPerCapita` | FLOAT | Oil CO₂ per person (tonnes). Recalculated. **Unit measure**. |
| `co2EmissionsCoal` | FLOAT | CO₂ from coal combustion (million tonnes). Proxy for coal-grid electricity; key for detecting the grid-shift effect. **Flow measure**. |
| `co2EmissionsCoalPerCapita` | FLOAT | Coal CO₂ per person (tonnes). Recalculated. **Unit measure**. |
| `co2EmissionsPerUnitEnergy` | FLOAT | Carbon intensity of the energy mix (kg CO₂ / kWh). Measures how "dirty" a country's energy system is. **Unit measure**. |
| `energyConsumption` | FLOAT | Total primary energy consumption (TWh). Context variable for energy demand analysis. **Flow measure**. |

### 4.4 `clean_owid_energy.csv` — Electricity Generation Mix

Granularity: one row per `[Country × Year]`.

| Column | Type | Description |
|--------|------|-------------|
| `country` | VARCHAR | Full country name. |
| `isoCode` | CHAR(3) | ISO code. Conformed dimension key. |
| `continent` | VARCHAR | Continent name. |
| `continentCode` | CHAR(2) | Continent code. |
| `year` | INT | Reference year (2010–2023). |
| `halfDecade` | VARCHAR | Pre-baked time grouping. |
| `pandemicPeriod` | VARCHAR | Pre-baked pandemic grouping. |
| `population` | FLOAT | Country population. |
| `GDP` | FLOAT | GDP in current USD. |
| `energyConsumption` | FLOAT | Total primary energy consumption (TWh). **Flow measure**. |
| `electricityGeneration` | FLOAT | Total domestic electricity generation (TWh). OWID primary, Ember-patched. **Flow measure**. |
| `electricityDemand` | FLOAT | Total electricity demand (TWh). Includes net imports. **Flow measure**. |
| `fossilElectricityGeneration` | FLOAT | Electricity from fossil fuels — coal + gas + oil (TWh). Key indicator of grid dirtiness. **Flow measure**. |
| `coalElectricityGeneration` | FLOAT | Electricity from coal (TWh). The dirtiest generation source; crucial for detecting the grid-shift effect. **Flow measure**. |
| `oilElectricityGeneration` | FLOAT | Electricity from oil (TWh). Minor in most OECD countries but significant in island nations. **Flow measure**. |
| `gasElectricityGeneration` | FLOAT | Electricity from natural gas (TWh). Often considered a transition fuel. **Flow measure**. |
| `renewableElectricityGeneration` | FLOAT | Electricity from all renewable sources combined (TWh). **Flow measure**. |
| `lowCarbonElectricityGeneration` | FLOAT | Electricity from low-carbon sources — renewables + nuclear (TWh). Broader than renewables-only. **Flow measure**. |
| `windElectricityGeneration` | FLOAT | Electricity from wind (TWh). **Flow measure**. |
| `hydroElectricityGeneration` | FLOAT | Electricity from hydro (TWh). **Flow measure**. |
| `nuclearElectricityGeneration` | FLOAT | Electricity from nuclear (TWh). Zero-carbon baseload; relevant to the grid-shift question. **Flow measure**. |
| `otherElectricityGeneration` | FLOAT | Electricity from other renewables — geothermal, biomass, waste (TWh). Catch-all to ensure totals reconcile. **Flow measure**. |
| `solarElectricityGeneration` | FLOAT | Electricity from solar PV (TWh). One of the fastest-growing sources in the study period. **Flow measure**. |
| `netElectricityImports` | FLOAT | Net electricity imports (TWh). Negative values indicate net exports. Critical for assessing whether a country's apparent renewable share is inflated by importing clean power from neighbours. **Flow measure** (directional). |

---

## 5. OLAP Queries & Analytical Insights

All queries are in [`src/DW/olap.sql`](src/DW/olap.sql) and run against the `GREEN_MOBILITY` PostgreSQL database. They are designed as direct answers to the analytical questions in the project proposal.

---

### Query 1 — EV Sales by Continent and Year `[ROLL-UP]`

```sql
SELECT
    cont.continent,
    y.year,
    COALESCE(SUM(m.evSales), 0) AS total_ev_sales
FROM (SELECT DISTINCT continent FROM CountryDim) cont
CROSS JOIN YearDim y
LEFT JOIN CountryDim c ON c.continent = cont.continent
LEFT JOIN EVMarket m ON m.keyC = c.keyC AND m.keyY = y.keyY
GROUP BY ROLLUP(cont.continent, y.year)
ORDER BY cont.continent, y.year;
```

**Analytical value:** Uses `ROLLUP` to produce a three-level hierarchy: individual years per continent → continent subtotals → global grand total. The `CROSS JOIN` + `LEFT JOIN` pattern ensures that continent-year combinations with zero sales still appear in the result (no silent data gaps). This query answers: *which continents are leading the EV transition, and how has the pace changed over time?*

---

### Query 2 — Renewable Electricity vs. CO₂ Emissions

```sql
SELECT
    c.country, y.year,
    ce.renewableElectricityGeneration,
    cm.co2Emissions
FROM CountryEnergy ce
JOIN CountryMacroeconomics cm ON ce.keyC = cm.keyC AND ce.keyY = cm.keyY
JOIN CountryDim c ON ce.keyC = c.keyC
JOIN YearDim y ON ce.keyY = y.keyY
ORDER BY y.year, ce.renewableElectricityGeneration DESC;
```

**Analytical value:** A foundational Drill-Across query joining `CountryEnergy` and `CountryMacroeconomics` through conformed dimensions. Produces the raw data for a scatter plot or correlation analysis: *are countries with more renewable electricity producing less CO₂?* This is the direct empirical test of the project's core hypothesis.

---

### Query 3 — GDP Class vs. EV Adoption

```sql
SELECT
    y.year,
    CASE
        WHEN cm.GDP >= 1000000000000 THEN 'High GDP'
        WHEN cm.GDP >= 100000000000  THEN 'Medium GDP'
        ELSE 'Low GDP'
    END AS GDP_class,
    AVG(em.evSalesShare) AS avg_ev_share
FROM CountryMacroeconomics cm
JOIN EVMarket em ON cm.keyC = em.keyC AND cm.keyY = em.keyY
JOIN YearDim y ON cm.keyY = y.keyY
GROUP BY y.year, GDP_class
ORDER BY y.year, GDP_class;
```

**Analytical value:** Addresses objective 2 directly: *do richer countries have higher EV market penetration?* GDP is bucketed into three tiers and `AVG(evSalesShare)` — correctly using `AVG` on a unit measure — is computed per tier per year. The trend in the gap between tiers over time reveals whether the economic disparity is narrowing or widening.

---

### Query 4 — Country Ranking by EV Stock `[WINDOW FUNCTION]`

```sql
SELECT
    y.year, c.country,
    SUM(evStock) AS stock,
    RANK() OVER (PARTITION BY y.year ORDER BY SUM(evStock) DESC) AS ranking
FROM EVMarket m
JOIN CountryDim c ON m.keyC = c.keyC
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY y.year, c.country;
```

**Analytical value:** Uses `RANK()` partitioned by year to produce annual leader-boards. Tracking rank movements over 2010–2023 shows how the competitive landscape has shifted — China's rise, Norway's early dominance, and the recent surge of Central European nations all become immediately visible.

---

### Query 5 — Vehicle Type × Powertrain Cross-Analysis `[CUBE]`

```sql
SELECT
    v.vehicleType, p.powertrain,
    SUM(evSales) AS total_sales
FROM EVMarket m
JOIN VehicleTypeDim v ON m.keyV = v.keyV
JOIN PowertrainDim p ON m.keyP = p.keyP
GROUP BY CUBE(v.vehicleType, p.powertrain)
ORDER BY v.vehicleType, p.powertrain;
```

**Analytical value:** `CUBE` generates all possible subtotal combinations: per vehicle type, per powertrain, per combination, and the global total — in a single pass. Answers *which segment is driving EV adoption?* (passenger BEVs dominate, but the truck and bus segments are analytically interesting for fleet electrification policy discussions).

---

### Query 6 — Pandemic Impact on EV Adoption

```sql
SELECT
    y.pandemicPeriod,
    AVG(evSalesShare) AS avg_share
FROM EVMarket m
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY y.pandemicPeriod;
```

**Analytical value:** Exploits the pre-baked `pandemicPeriod` attribute in `YearDim` to group data without any `CASE WHEN` logic. The result directly answers whether COVID-19 disrupted or accelerated EV market share growth — a clean, reproducible benchmark of the pandemic's net effect on the energy transition.

---

### Query 7 — Charging Infrastructure Growth `[LAG Window Function]`

```sql
SELECT
    c.country, y.year, evChargingPoints,
    LAG(evChargingPoints) OVER (PARTITION BY c.country ORDER BY y.year) AS previous_year,
    evChargingPoints - LAG(evChargingPoints) OVER (PARTITION BY c.country ORDER BY y.year) AS yearly_growth
FROM EVInfrastructure i
JOIN CountryDim c ON i.keyC = c.keyC
JOIN YearDim y ON i.keyY = y.keyY;
```

**Analytical value:** `LAG()` computes year-over-year absolute growth of charging points per country. This is more informative than raw totals because it exposes inflection points — countries that massively accelerated deployment in a specific year (often correlated with government incentive programmes).

---

### Query 8 — EV Demand vs. Grid Mix

```sql
SELECT
    c.country, y.year,
    SUM(em.evElectricityDemand)        AS evElectricityDemand,
    MAX(ce.renewableElectricityGeneration) AS renewableElectricityGeneration,
    MAX(ce.fossilElectricityGeneration)    AS fossilElectricityGeneration
FROM EVMarket em
JOIN CountryEnergy ce ON em.keyC = ce.keyC AND em.keyY = ce.keyY
JOIN CountryDim c ON em.keyC = c.keyC
JOIN YearDim y ON em.keyY = y.keyY
WHERE em.evElectricityDemand > 0
GROUP BY c.country, y.year
ORDER BY c.country, y.year;
```

**Analytical value:** `MAX()` is used on level measures (generation totals) to avoid inflating them via the many-to-one join with `EVMarket`. This query produces the core dataset for the grid-shift analysis: countries with high `evElectricityDemand` but also high `fossilElectricityGeneration` are candidates for net-negative environmental impact from EV charging.

---

### Query 9 — Continent × Pandemic Period Sales `[GROUPING SETS]`

```sql
SELECT
    c.continent, y.pandemicPeriod, SUM(evSales) AS sales
FROM EVMarket m
JOIN CountryDim c ON m.keyC = c.keyC
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY GROUPING SETS (
    (c.continent, y.pandemicPeriod),
    (c.continent),
    (y.pandemicPeriod),
    ()
);
```

**Analytical value:** Demonstrates `GROUPING SETS` as a more surgical alternative to `CUBE` — producing only the four subtotal combinations that are analytically relevant (joint, per-continent, per-period, global) rather than all possible combinations.

---

### Query 10 — Renewable Share of Electricity per Country

```sql
SELECT
    c.country, y.year,
    ROUND(100 * renewableElectricityGeneration / electricityGeneration, 2) AS renewable_percentage
FROM CountryEnergy ce
JOIN CountryDim c ON ce.keyC = c.keyC
JOIN YearDim y ON ce.keyY = y.keyY
WHERE electricityGeneration > 0
ORDER BY c.country, y.year;
```

**Analytical value:** Computes the share of renewable generation directly in SQL. The `WHERE electricityGeneration > 0` guard prevents division-by-zero. This metric is the most direct indicator of grid cleanliness and can be paired with Query 12 to assess whether EV growth correlates with grid improvement.

---

### Query 12 — Is EV Adoption Reducing CO₂? `[Core Hypothesis Test]`

```sql
SELECT
    c.country, y.year,
    SUM(em.evSalesShare)                     AS evSalesShare,
    AVG(ce.renewableElectricityGeneration)   AS renewableElectricityGeneration,
    AVG(cm.co2PerCapita)                     AS co2PerCapita
FROM EVMarket em
JOIN CountryEnergy ce         ON em.keyC = ce.keyC AND em.keyY = ce.keyY
JOIN CountryMacroeconomics cm ON em.keyC = cm.keyC AND em.keyY = cm.keyY
JOIN CountryDim c ON em.keyC = c.keyC
JOIN YearDim y ON em.keyY = y.keyY
GROUP BY c.country, y.year
ORDER BY c.country, y.year;
```

**Analytical value:** This is the most analytically central query of the project. It directly integrates all three fact tables — EV adoption (`EVMarket`), grid cleanliness (`CountryEnergy`), and carbon footprint (`CountryMacroeconomics`) — into a single per-country, per-year panel. The result is a ready-made dataset for scatter plots, regression, or correlation analysis to test whether higher `evSalesShare` + higher `renewableElectricityGeneration` actually translates into lower `co2PerCapita`. `SUM()` and `AVG()` are applied appropriately to their respective measure types.

---

## 6. Project Structure & How to Run

### 6.1 Repository Map

```
Data-Management-Project/
│
├── raw_datasets/                   # Original, unmodified source files
│   ├── iea-global-ev-sales.csv
│   ├── owid-co2-data.csv
│   ├── owid-energy-data.csv
│   ├── continent_country.csv       # ISO continent mapping (auxiliary)
│   ├── gdp_population_countries.csv  # World Bank GDP + pop (auxiliary)
│   └── release_generation_yearly_global.csv  # Ember electricity data (auxiliary)
│
├── clean_datasets/                 # ETL output — ready for DW import
│   ├── clean_iea_ev_sales.csv
│   ├── clean_iea_ev_infrastructure.csv
│   ├── clean_owid_co2.csv
│   └── clean_owid_energy.csv
│
├── src/
│   ├── etl.py                      # Main entry point: orchestrates Extract → Transform → Load → DB Insert
│   └── utility/
│       ├── extract.py              # Reads all raw CSVs from raw_datasets/
│       ├── transform.py            # All cleaning, pivoting, patching, renaming logic
│       ├── load.py                 # Saves clean CSVs + prints validation summary
│       └── db_loader.py            # Inserts data into PostgreSQL (dimension + fact tables)
│
├── src/DW/
│   ├── init.sql                    # Creates the GREEN_MOBILITY database schema
│   └── olap.sql                    # All 12 OLAP queries
│
├── DFM Schema/
│   ├── DFM_star.excalidraw         # Editable DFM diagram source (Excalidraw)
│   └── assets/
│       ├── DFM.png                 # Conceptual DFM diagram
│       ├── DFM_star.png            # Final Star Schema diagram
│       └── star.png                # Simplified star schema overview
│
├── datasets_presentation.md        # Detailed data profiling report (Italian)
├── data_profiling_and_cleaning_report.md  # Data cleaning log (Italian)
└── README.md                       # This file
```

> **Note:** The `src/RDBMS/` directory is not part of Task 1 and is not documented here.

---

### 6.2 Prerequisites

- Python ≥ 3.9
- PostgreSQL ≥ 14 (running locally or via Docker)
- Python packages: `pandas`, `psycopg2-binary`, `numpy`

```bash
pip install pandas psycopg2-binary numpy
```

### 6.3 Running the ETL Pipeline

**Step 1 — Initialise the database schema**

Connect to your PostgreSQL instance and run the schema creation script:

```bash
psql -U postgres -f src/DW/init.sql
```

This creates the `GREEN_MOBILITY` database with all dimension and fact tables.

**Step 2 — Run the full ETL pipeline**

From the project root:

```bash
cd src
python etl.py
```

This will:
1. Extract all raw datasets from `raw_datasets/`
2. Clean, transform, and pivot the data
3. Save the four clean CSVs to `clean_datasets/`
4. Insert all data into the PostgreSQL database

**Step 3 — CSV-only mode** (skip database insertion)

If you only need the clean CSV files without a running PostgreSQL instance:

```python
from utility import extract, transform, load

ev, co2, energy, cont, gdp_pop, ember = extract.extract_data()
ev_c, infra_c, co2_c, energy_c = transform.transform_data(ev, co2, energy, cont, gdp_pop, ember)
load.load_data(ev_c, infra_c, co2_c, energy_c)
```

Or equivalently, call `run_etl(skip_db=True)` from `etl.py`.

**Step 4 — Run OLAP queries**

```bash
psql -U postgres -d green_mobility -f src/DW/olap.sql
```

### 6.4 Database Connection Defaults

The ETL uses the following defaults (configurable via `run_etl()` parameters):

| Parameter | Default |
|-----------|---------|
| Host | `localhost` |
| Port | `5432` |
| Database | `green_mobility` |
| User | `postgres` |
| Password | `postgres` |

---

*Project developed for the Data Management course — MSc in Computer Science.*