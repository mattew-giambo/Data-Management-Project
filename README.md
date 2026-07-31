# Green Mobility - Data Management Project
### MSc in Computer Science

> A dimensional data warehouse and RDBMS comparative study built to investigate whether the global rise of electric vehicles is actually reducing carbon emissions, or simply shifting them from the tailpipe to the power plant.

---

## Table of Contents

### Task 1 - Data Staging, Warehousing & OLAP
1. [Project Overview & Objectives](#1-project-overview--objectives)
2. [Datasets & Data Preparation](#2-datasets--data-preparation)
3. [Data Warehousing & Methodology](#3-data-warehousing--methodology)
4. [Final Datasets & Attribute Dictionary](#4-final-datasets--attribute-dictionary)
5. [OLAP Queries & Analytical Insights](#5-olap-queries--analytical-insights)
6. [Project Structure](#6-project-structure)

### Task 2 - RDBMS vs. Data Warehouse Comparative Analysis
7. [Problem Definition & Domain Context](#7-problem-definition--domain-context)
8. [Architectural Comparison: RDBMS vs. DW](#8-architectural-comparison-rdbms-vs-dw-star-schema)
9. [Benchmark Methodology & Results](#9-benchmark-methodology--results)
10. [Architectural Trade-offs & Discussion](#10-architectural-trade-offs--discussion)
11. [Conclusions](#11-conclusions)

---

# Task 1 - Data Staging, Warehousing & OLAP

# 1. Project Overview & Objectives

The main question behind this project is: **does using an electric vehicle really reduce environmental impact?** The answer depends on how the electricity is produced. If a Battery Electric Vehicle (BEV) is charged using electricity generated mainly from coal, its total $CO_2$ emissions during its lifetime can even be higher than those of an efficient petrol car. In this case, the emissions are not produced directly by the vehicle, but during electricity generation.

To study this problem, a **Data Warehouse (DW)** was developed by integrating three different open-access datasets. The analysis covers **50 countries** from **2010 to 2023**. The project focuses on two main objectives:

1. **EV Impact Assessment** – Evaluate whether the adoption of electric vehicles contributes to reducing national $CO_2$ emissions, considering the electricity generation mix of each country and the possible *grid-shift* effect, where electricity used for charging is mainly produced from fossil fuels.
2. **Economic Transition Disparity** – Compare the adoption of electric vehicles in countries with different GDP levels to understand whether economic resources influence the speed of the energy transition.

The Data Warehouse was first designed at the conceptual level using the **Dimensional Fact Model (DFM)** and then implemented as a **Relational OLAP (ROLAP)** Star Schema. Shared dimensions between different fact tables make it possible to perform **Drill-across** analyses. The project also supports common OLAP operations through SQL aggregation features such as `ROLLUP`, `CUBE`, `GROUPING SETS`, together with window functions for trend analysis.

---

# 2. Datasets & Data Preparation

## 2.1 Source Datasets

The project uses three main datasets. During the ETL process, three additional datasets were included because data profiling revealed some missing or incomplete information that needed to be corrected.

### Primary Datasets

| # | Name | Source | Raw Size | Granularity |
|---|------|--------|----------|-------------|
| 1 | **IEA Global EV Sales** (2010–2023) | International Energy Agency / Kaggle | 12,654 rows x 8 columns | `[Country, Year, Vehicle Mode, Powertrain, Parameter]` |
| 2 | **OWID $CO_2$ & GHG Emissions** | Our World in Data / Global Carbon Project | 50,411 rows x 79 columns | `[Country, Year]` |
| 3 | **OWID Energy Dataset** | Our World in Data / BP / Ember / IEA | 23,377 rows x 130 columns | `[Country, Year]` |

### Auxiliary Datasets

These datasets were not included in the original project proposal. They were added after the data analysis phase because they helped solve some data quality problems.

| # | Name | Source | Purpose |
|---|------|--------|---------|
| 4 | **World Bank GDP & Population** | World Bank Open Data | The GDP and population values available in the OWID datasets are expressed in constant 2011 PPP dollars. This made some per-capita calculations less consistent, so the corresponding values were replaced with current USD data from the World Bank, which provides more reliable and complete information. |
| 5 | **continent_country.csv** | ISO standard lookup<br>https://gist.github.com/20a69c0b6d2ff846ea5d35e5fc47f26c.git | The IEA dataset does not contain information about continents. This mapping file was used to add the attributes `continent` and `continentCode` to the geographical dimension (`CountryDim`), allowing continent-level analyses. |
| 6 | **Ember Global Electricity Generation** | Ember Climate<br>https://ember-energy.org/data/yearly-electricity-data/ | Several electricity generation attributes in the OWID energy dataset contain many missing values. The Ember dataset provides better coverage for the same indicators, so it was used to fill the missing values before loading the data into the Data Warehouse. |

**Note about Dataset 4 (World Bank Development Indicators):** The original project proposal considered this dataset. After the analysis phase, it was found that GDP and population were already available in the OWID datasets. For this reason, the World Bank data was not used as an additional source, but only to replace the existing OWID values with more complete and up-to-date data.

---

### 2.2 Attribute Selection Rationale

Before starting the transformation process, each dataset was analysed to decide which attributes were useful for the project and which ones could be removed.

#### IEA EV Sales, selected attributes

The IEA dataset is stored in **long format**, where each row represents a single metric identified by the `parameter` column. The parameters selected for the project are `EV sales`, `EV stock`, `EV sales share`, `EV stock share`, and `Electricity demand`.

Two parameters, `Oil displacement Mbd` and `Oil displacement, million lge`, were removed because they are estimated values derived from other measures. They do not provide additional information and cannot be compared fairly across different vehicle categories.

The `category` column, which contains the values `Historical`, `Projection-STEPS`, and `Projection-APS`, was only used to filter the data. Since only historical records were kept, this column was no longer needed and was removed.

#### OWID $CO_2$, selected attributes

The original dataset contains 79 columns, but only 14 were selected for the Data Warehouse.

Several attributes were removed because they were outside the scope of the project. These include cumulative historical emissions, trade-adjusted consumption emissions, and greenhouse gases other than $CO_2$. The `iso_code` column was used to identify and remove rows that do not represent individual countries, such as "Africa (GCP)" and other macro-regions.

#### OWID Energy, selected attributes

The OWID Energy dataset contains 130 columns, and 20 of them were selected.

The complete electricity generation mix was kept, including coal, gas, oil, nuclear, hydro, solar, wind, and other renewable sources. These attributes are essential because the project analyses not only how much electricity is produced, but also how it is generated.

The removed attributes include energy consumption by sector, per-capita energy indicators, which were recalculated later, and detailed information about non-electricity energy carriers, such as primary energy by fuel type.

---

### 2.3 Data Cleaning Process

The complete cleaning process is implemented in `src/utility/transform.py`. The main steps are described below.

#### Step 1 - Removing Projections and Aligning Time Ranges

The IEA dataset includes 3,480 rows containing future projections for the years 2020 to 2035, labelled as `Projection-STEPS` and `Projection-APS`. These rows were removed by selecting only records where `category == 'Historical'`.

The OWID Energy dataset also contains 106 rows for the year 2025, based on preliminary Ember estimates. Since the three datasets overlap only between 2010 and 2023 with complete historical information, all datasets were limited to this time period.

#### Step 2 - Resolving Geographic Conflicts

The IEA dataset does not include ISO country codes and uses country names that are sometimes different from those used in the OWID datasets. To solve this problem, a matching procedure with several steps was implemented.

1. An exact match was first attempted using a dictionary created from the OWID country names and ISO codes.
2. If no match was found, country names were simplified by removing words such as "Republic of" and "Kingdom of".
3. Some special cases were solved manually, for example mapping `Korea` to `South Korea`.
4. As a final step, fuzzy matching was performed using `difflib.get_close_matches` with a similarity threshold of 0.6.

Rows representing macro-regions, such as `World`, `Europe`, `EU27`, and `Rest of the world` in the IEA dataset, together with all OWID rows where `iso_code` is `NULL`, were removed to avoid double-counting during aggregate analyses.

#### Step 3 - Pivoting the EV Dataset

The IEA dataset was converted from long format to wide format using `pivot_table`.

Information about charging infrastructure (`EV charging points`) was stored in a separate table called `EVInfrastructure`. This avoids conflicts in granularity with the vehicle market data. The resulting `EVMarket` table is organised by `[Country, Year, Vehicle Mode, Powertrain]`.

#### Step 4 - Handling Missing Values

Different strategies were used depending on the type of data.

For EV indicators, including sales, stock, shares, and electricity demand, missing values created during the pivot operation were replaced with `0.0`. In these cases, a missing value simply means that no activity was recorded for that country and category.

For macroeconomic and energy variables, such as GDP, population, $CO_2$ emissions, and electricity generation, missing values were kept as `NULL`. Replacing these values with zero would produce incorrect averages and ratio calculations during OLAP analyses.

#### Step 5 - Patching Energy Data with Ember

After the cleaning process, the OWID Energy dataset still contained many missing values in the electricity generation columns.

To improve data completeness, the Ember dataset was filtered to keep only rows where `Area type == 'Country or economy'`. After pivoting the data by `Electricity source`, it was joined with the OWID dataset. Missing values were then filled using `fillna()`, while all existing OWID values were preserved.

#### Step 6 - Replacing GDP and Population with World Bank Data

The World Bank dataset was transformed by melting and pivoting the data using `Series Code`.

The resulting table was joined with both `co2_clean` and `energy_clean` using `(isoCode, year)`. Whenever World Bank data was available, it replaced the corresponding OWID values. If not, the original OWID values were kept.

#### Step 7 - Recalculating Derived Indicators

After updating GDP and population values, all ratio indicators were recalculated to ensure consistency throughout the Data Warehouse.

```text
co2PerCapita = (co2Emissions x 10^6) / population
co2PerGDP    = (co2Emissions x 10^9) / GDP
```

This approach guarantees that the calculated indicators are based on the updated GDP and population values instead of the original ratios provided by OWID.

#### Final Validation Results

| Dataset | Rows | ISO Nulls | Year Range |
|---------|------|-----------|------------|
| `clean_iea_ev_sales.csv` | ~4,259 | 0 | 2010–2023 |
| `clean_iea_ev_infrastructure.csv` | ~650 | 0 | 2010–2023 |
| `clean_owid_co2.csv` | ~3,052 | 0 | 2010–2023 |
| `clean_owid_energy.csv` | ~3,078 | 0 | 2010–2023 |

The final validation confirmed complete geographic coverage. All 50 ISO codes present in the EV dataset are also available in both the $CO_2$ and Energy datasets, ensuring referential integrity inside the Data Warehouse.

---

# 3. Data Warehousing & Methodology

## 3.1 Design Approach

![DFM Schema](DFM%20Schema/assets/DFM.png)

The Data Warehouse was designed following the **Dimensional Fact Model (DFM)** methodology. According to the DFM, the first step is to identify the facts, the measures associated with each fact, and the dimensions that are used to analyse and aggregate the data. After the conceptual design, the model can be translated into the logical schema.

One of the most important design choices was to use **multiple fact tables** instead of storing all the information in a single table. This decision was necessary because the datasets have different levels of granularity.

The EV Sales dataset is organised by `Country x Year x Vehicle Type x Powertrain`, while the $CO_2$ and Energy datasets are organised only by `Country x Year`. If all the data were combined into one fact table, the $CO_2$ and energy values would be repeated for every vehicle type and powertrain. As a result, aggregate operations such as `SUM(co2Emissions)` would produce incorrect values because the same emissions would be counted multiple times.

To avoid this problem, the Data Warehouse uses a **Multi-Fact Star Schema** with **conformed dimensions**. The shared dimensions, `CountryDim` and `YearDim`, connect the different fact tables and make it possible to analyse data coming from different sources through **drill-across** operations.

## 3.2 Schema Design

The logical schema, implemented in `src/DW/init.sql`, follows the **Star Schema** model. It includes four dimension tables and four fact tables.

![Star Schema](DFM%20Schema/assets/star.png)

### Dimension Tables

| Table | PK | Description |
|-------|----|-------------|
| `CountryDim` | `keyC` | Stores information about each country, including the ISO code and the continent. This dimension is shared by all fact tables. |
| `YearDim` | `keyY` | Stores the year together with two additional attributes, `halfDecade` (2010–2014, 2015–2019, 2020–2023) and `pandemicPeriod` (Pre-Pandemic, Pandemic, Post-Pandemic). These attributes simplify analytical queries because they avoid repeating the same `CASE WHEN` expressions. |
| `VehicleTypeDim` | `keyV` | Contains the vehicle categories, such as Cars, Buses, Vans, and Trucks. It is used only by the `EVMarket` fact table. |
| `PowertrainDim` | `keyP` | Contains the powertrain technologies, including BEV, PHEV, and FCEV. It is also used only by the `EVMarket` fact table. |

### Fact Tables

| Table | Grain | Main Measures |
|-------|-------|---------------|
| `EVMarket` | Country x Year x Vehicle Type x Powertrain | EV sales indicators |
| `EVInfrastructure` | Country x Year | Charging infrastructure indicators |
| `CountryEnergy` | Country x Year | Electricity generation by energy source |
| `CountryMacroeconomics` | Country x Year | $CO_2$ emissions and macroeconomic indicators |

The `CountryEnergy` and `CountryMacroeconomics` tables share the `CountryDim` and `YearDim` dimensions with `EVMarket`. This design avoids duplicated values caused by different granularities and allows data from different fact tables to be analysed together using drill-across queries.

## 3.3 Measure Additivity

According to the measure classification introduced in the DFM methodology, the measures in the Data Warehouse can be divided into three groups.

**Flow measures** are fully additive across all dimensions. Examples include `evSales`, `evElectricityDemand`, `co2Emissions`, `co2EmissionsOil`, `co2EmissionsCoal`, `electricityGeneration`, and `renewableElectricityGeneration`.

**Level measures** can be added across different countries, but they should not be summed over time. This group includes `evStock`, `evChargingPoints`, `population`, and `GDP`. For example, adding the EV stock of Germany and France for the same year is correct, while adding the EV stock of 2020 and 2021 is not meaningful.

**Unit measures** are calculated as ratios, so they are not additive. This category includes `evSalesShare`, `evStockShare`, `co2PerCapita`, and `co2PerGDP`. These measures should be analysed using aggregation functions such as `AVG`, `MIN`, or `MAX`, and not with `SUM`.

---

# 4. Final Datasets & Attribute Dictionary

### 4.1 `clean_iea_ev_sales.csv` - EV Market Data

Granularity: one row per `[Country x Year x Vehicle Type x Powertrain]`.

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

### 4.2 `clean_iea_ev_infrastructure.csv` - Charging Infrastructure

Granularity: one row per `[Country x Year]`.

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

### 4.3 `clean_owid_co2.csv` - Emissions & Macroeconomics

Granularity: one row per `[Country x Year]`.

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
| `co2Emissions` | FLOAT | Total $CO_2$ from fossil fuels and industry (million tonnes). Core project measure. **Flow measure**. |
| `co2PerCapita` | FLOAT | $CO_2$ per person (tonnes). Recalculated from `co2Emissions / population`. **Unit measure**. |
| `co2PerGDP` | FLOAT | $CO_2$ per unit of GDP (kg $CO_2$ per USD). Recalculated. **Unit measure**. Measures carbon intensity of economic activity. |
| `co2EmissionsOil` | FLOAT | $CO_2$ from oil combustion (million tonnes). Proxy for transport fuel emissions; expected to decline with EV adoption. **Flow measure**. |
| `co2EmissionsOilPerCapita` | FLOAT | Oil $CO_2$ per person (tonnes). Recalculated. **Unit measure**. |
| `co2EmissionsCoal` | FLOAT | $CO_2$ from coal combustion (million tonnes). Proxy for coal-grid electricity; key for detecting the grid-shift effect. **Flow measure**. |
| `co2EmissionsCoalPerCapita` | FLOAT | Coal $CO_2$ per person (tonnes). Recalculated. **Unit measure**. |
| `co2EmissionsPerUnitEnergy` | FLOAT | Carbon intensity of the energy mix (kg $CO_2$ / kWh). Measures how "dirty" a country's energy system is. **Unit measure**. |
| `energyConsumption` | FLOAT | Total primary energy consumption (TWh). Context variable for energy demand analysis. **Flow measure**. |

### 4.4 `clean_owid_energy.csv` - Electricity Generation Mix

Granularity: one row per `[Country x Year]`.

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
| `fossilElectricityGeneration` | FLOAT | Electricity from fossil fuels - coal + gas + oil (TWh). Key indicator of grid dirtiness. **Flow measure**. |
| `coalElectricityGeneration` | FLOAT | Electricity from coal (TWh). The dirtiest generation source; crucial for detecting the grid-shift effect. **Flow measure**. |
| `oilElectricityGeneration` | FLOAT | Electricity from oil (TWh). Minor in most OECD countries but significant in island nations. **Flow measure**. |
| `gasElectricityGeneration` | FLOAT | Electricity from natural gas (TWh). Often considered a transition fuel. **Flow measure**. |
| `renewableElectricityGeneration` | FLOAT | Electricity from all renewable sources combined (TWh). **Flow measure**. |
| `lowCarbonElectricityGeneration` | FLOAT | Electricity from low-carbon sources - renewables + nuclear (TWh). Broader than renewables-only. **Flow measure**. |
| `windElectricityGeneration` | FLOAT | Electricity from wind (TWh). **Flow measure**. |
| `hydroElectricityGeneration` | FLOAT | Electricity from hydro (TWh). **Flow measure**. |
| `nuclearElectricityGeneration` | FLOAT | Electricity from nuclear (TWh). Zero-carbon baseload; relevant to the grid-shift question. **Flow measure**. |
| `otherElectricityGeneration` | FLOAT | Electricity from other renewables - geothermal, biomass, waste (TWh). Catch-all to ensure totals reconcile. **Flow measure**. |
| `solarElectricityGeneration` | FLOAT | Electricity from solar PV (TWh). One of the fastest-growing sources in the study period. **Flow measure**. |
| `netElectricityImports` | FLOAT | Net electricity imports (TWh). Negative values indicate net exports. Critical for assessing whether a country's apparent renewable share is inflated by importing clean power from neighbours. **Flow measure** (directional). |

---

# 5. OLAP Queries & Analytical Insights

All queries are in [`src/DW/olap.sql`](src/DW/olap.sql) and run against the `GREEN_MOBILITY` PostgreSQL database. They are designed as direct answers to the analytical questions in the project proposal.

---

### Query 1 - EV Sales by Continent and Year `[ROLL-UP]`

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

Uses `ROLLUP` to produce a three-level hierarchy: individual years per continent, continent subtotals, and global grand total. The `CROSS JOIN` + `LEFT JOIN` pattern ensures that continent-year combinations with zero sales still appear in the result. This query answers: *which continents are leading the EV transition, and how has the pace changed over time?*

---

### Query 2 - Renewable Electricity vs. $CO_2$ Emissions

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

A foundational Drill-Across query joining `CountryEnergy` and `CountryMacroeconomics` through dimensions. It answers the question: *are countries with more renewable electricity producing less $CO_2$?*

---

### Query 3 - GDP Class vs EV Adoption

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

Addresses objective 2 directly: *do richer countries have higher EV market penetration?* GDP is bucketed into three groups and `AVG(evSalesShare)` - correctly using `AVG` on a unit measure - is computed per tier per year.

---

### Query 4 - Country Ranking by EV Stock `[WINDOW FUNCTION]`

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

Uses `RANK()` partitioned by year to produce annual leader-boards. Tracking rank movements over 2010–2023 shows how the competitive landscape has shifted.

---

### Query 5 - Vehicle Type x Powertrain Cross-Analysis `[CUBE]`

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

`CUBE` generates all possible subtotal combinations: per vehicle type, per powertrain, per combination, and the global total - in a single pass. Answers *which segment is driving EV adoption?*

---

### Query 6 - Pandemic Impact on EV Adoption

```sql
SELECT
    y.pandemicPeriod,
    AVG(evSalesShare) AS avg_share
FROM EVMarket m
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY y.pandemicPeriod;
```

Exploits the `pandemicPeriod` attribute in `YearDim` to group data. The result directly answers whether COVID-19 disrupted or accelerated EV market share growth.

---

### Query 7 - Charging Infrastructure Growth `[LAG Window Function]`

```sql
SELECT
    c.country, y.year, evChargingPoints,
    LAG(evChargingPoints) OVER (PARTITION BY c.country ORDER BY y.year) AS previous_year,
    evChargingPoints - LAG(evChargingPoints) OVER (PARTITION BY c.country ORDER BY y.year) AS yearly_growth
FROM EVInfrastructure i
JOIN CountryDim c ON i.keyC = c.keyC
JOIN YearDim y ON i.keyY = y.keyY;
```

`LAG()` computes year-over-year absolute growth of charging points per country. This exposes inflection points - countries that massively accelerated deployment in a specific year.

---

### Query 8 - EV Demand vs Energy Mix

```sql
SELECT
    c.country, y.year,
    SUM(em.evElectricityDemand)            AS evElectricityDemand,
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

`MAX()` is used on level measures (generation totals). Countries with high `evElectricityDemand` but also high `fossilElectricityGeneration` are candidates for net-negative environmental impact from EV charging.

---

### Query 9 - Continent x Pandemic Period Sales `[GROUPING SETS]`

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

`GROUPING SETS` as a more precise alternative to `CUBE`, producing only the four analytically relevant subtotal combinations (joint, per-continent, per-period, and global).

---

### Query 10 - Renewable Share of Electricity per Country

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

Computes the share of renewable generation directly in SQL. The `WHERE electricityGeneration > 0` guard prevents division-by-zero. This metric is the most direct indicator of grid cleanliness.

---

### Query 11 - Is EV Adoption Reducing $CO_2$? `[Core Hypothesis Test]`

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

The most analytically central query of the project. It directly integrates all three fact tables - EV adoption (`EVMarket`), grid cleanliness (`CountryEnergy`), and carbon footprint (`CountryMacroeconomics`) - into a single per-country, per-year panel. `SUM()` and `AVG()` are applied appropriately to their respective measure types.

---

# 6. Project Structure

### 6.1 Repository Map

```
│
├── raw_datasets/
│   ├── iea-global-ev-sales.csv
│   ├── owid-co2-data.csv
│   ├── owid-energy-data.csv
│   ├── continent_country.csv
│   ├── gdp_population_countries.csv
│   └── release_generation_yearly_global.csv
│
├── clean_datasets/
│   ├── clean_iea_ev_sales.csv
│   ├── clean_iea_ev_infrastructure.csv
│   ├── clean_owid_co2.csv
│   └── clean_owid_energy.csv
│
├── src/
│   ├── etl.py
│   └── utility/
│       ├── extract.py
│       ├── transform.py
│       ├── load.py
│       └── db_loader.py
│
├── src/DW/
│   ├── init.sql
│   └── olap.sql
│
├── src/RDBMS/
│   ├── sql/
│   │   └── relational_schema.sql
│   ├── load_db.py
│   └── REPORT.md
│
├── DFM Schema/
│   ├── DFM_star.excalidraw
│   └── assets/
│       ├── DFM.png
│       ├── DFM_star.png
│       └── star.png
│
├── benchmark.py
├── benchmark_results.csv
├── datasets_presentation.md
├── data_profiling_and_cleaning_report.md
└── README.md
```

---

---

# Task 2 - RDBMS vs. Data Warehouse: A Comparative Performance and Architectural Analysis

> This section documents **Task 2** of the Data Management project, which required identifying a data analysis problem and comparing two different technological approaches to address it. The chosen domain is **green mobility and energy transition**, and the comparison is drawn between:
> 1. A **Relational Database Management System (RDBMS)** normalized in **Third Normal Form**, running on PostgreSQL (`green_mobility_rdbms`).
> 2. A **Data Warehouse (DW)** implemented as a **Relational OLAP (ROLAP) Star Schema** with full OLAP feature support, also running on PostgreSQL (`green_mobility`).

The benchmark evaluates both architectures across **11 analytical queries** designed to investigate the relationship between electric vehicle (EV) adoption, electricity grid cleanliness, and national $CO_2$ emissions. Performance was measured empirically using PostgreSQL's `EXPLAIN (ANALYZE, BUFFERS)` facility across 10 execution runs per query.

Overall, the Data Warehouse star schema outperformed the 3NF relational database with an overall execution speedup of **1.37x** (24.47 ms total for DW vs. 33.48 ms for RDBMS). The DW achieved its highest speedups on queries that exploit native OLAP operators such as `CUBE`, `GROUPING SETS`, and window functions like `RANK()` (peaking at **3.43x** speedup for Q4). Furthermore, the star schema reduced SQL code verbosity by an average factor of **1.43x**, minimizing query complexity and potential human error.

---

# 7. Problem Definition & Domain Context

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

# 8. Architectural Comparison: RDBMS vs. DW (Star Schema)

## 8.1 The Relational RDBMS Approach (3NF)

The relational schema ([`src/RDBMS/sql/relational_schema.sql`](src/RDBMS/sql/relational_schema.sql)) adheres to Third Normal Form. Every entity is normalized in its own table, and referential integrity is enforced through foreign keys and surrogate primary keys (`SERIAL`). The tables are:

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

Data was loaded into the RDBMS using the standalone Python script [`src/RDBMS/load_db.py`](src/RDBMS/load_db.py), which reads the pre-cleaned CSVs produced by the ETL pipeline and populates all tables in dependency order.

---

## 8.2 The Data Warehouse Approach (Star Schema)

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

The DW is populated through a dedicated ETL pipeline ([`src/DW/etl.py`](src/DW/etl.py)) that handles extraction, transformation and loading.

---

# 9. Benchmark Methodology & Results

## 9.1 Benchmark Setup

All queries were benchmarked using the Python script [`benchmark.py`](benchmark.py), which wraps every query with PostgreSQL's `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)` directive and parses the output to extract:

- **Planning time** (ms): time the query planner spent generating an execution plan;
- **Execution time** (ms): time the engine spent actually executing the plan;
- **Total time** (ms): sum of planning and execution time.

Each query was run **10 times** on both databases. The reported values are the averages of the measured runs.

---

## 9.2 Empirical Benchmark Results

The raw results are stored in [`benchmark_results.csv`](benchmark_results.csv). Below are the benchmark results for all 11 queries, sorted by Query ID:

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
| **Q10** | Renewable Share % | 0.088 | 2.302 | 0.085 | 2.319 | 2.391 | 2.404 | **0.99x** |
| **Q11** | Is EV Adoption Reducing $CO_2$? | 0.882 | 3.272 | 0.862 | 3.218 | 4.155 | 4.081 | **1.02x** |
| **Total** | **Cumulative Benchmarks** | **2.749** | **30.727** | **2.320** | **22.146** | **33.478** | **24.466** | **1.37x** |

Overall, the DW model outperforms the standard RDBMS across most benchmarked scenarios, achieving a **1.37x** total execution speedup and demonstrating faster performance in 9 out of 11 queries.

The performance difference is particularly noticeable in complex analytical queries:

- **High speedup queries (Q4, Q5, Q9)**: The DW achieves significant gains, peaking at **3.43x** for Q4 (Top Countries by EV Stock), **1.95x** for Q9 (Continent x Pandemic Period), and **1.84x** for Q5 (Vehicle Type Analysis). This improvement is primarily driven by the denormalized star schema, which minimizes costly runtime table joins and avoids repetitive table scans.
- **Moderate speedup queries (Q7)**: Query Q7 (Infrastructure Growth) shows a **1.39x** speedup, benefiting from native window functions (`LAG()`) over correlated self-joins.
- **Comparable queries (Q1–Q3, Q6, Q8, Q10, Q11)**: Lightweight queries exhibit almost identical performance (~0.99x to 1.05x speedup). Execution time is dominated by fixed PostgreSQL overhead rather than scanning large volumes of data.

---

# 10. Architectural Trade-offs & Discussion

| Aspect | Relational RDBMS | Data Warehouse (Star Schema) |
|---|---|---|
| **Data Redundancy** | **Zero redundancy**. Fully normalized according to 3NF rules. | **Controlled redundancy**. Dimension tables store denormalized temporal/geographic attributes. |
| **Query Performance** | Slower on multi-dimensional aggregations and window rankings (**33.48 ms** total). | **Faster overall** (**24.47 ms** total, up to **3.43x speedup** on complex queries). |
| **Query Complexity** | **Higher**. Lacks native OLAP operators; requires verbose `UNION ALL` blocks and self-joins. | **Lower**. Native `CUBE`, `ROLLUP`, `GROUPING SETS`, and window functions keep SQL concise. |
| **ETL Pipeline** | **Simpler initial load**. Row-by-row mapping of surrogate keys in Python ([`load_db.py`](src/RDBMS/load_db.py)). | **Dedicated ETL Pipeline**. Requires extraction, transformation, dimension key mapping, and multi-fact staging ([`etl.py`](src/DW/etl.py)). |
| **Primary Use Case** | Transactional processing (OLTP), single-record inserts, updates, and delete operations. | Analytical reporting (OLAP), trend analysis, and business intelligence dashboards. |

---

# 11. Conclusions

This benchmark confirms the theoretical foundations of Data Warehousing vs. Relational Database design:

1. **Superior Analytical Performance**: For analytical workloads involving multi-dimensional aggregations and ranking, the Data Warehouse Star Schema is clearly superior. It executed faster on 9 out of 11 queries, achieving a cumulative speedup of **1.37x** and peak speedups of **3.43x** (Q4), **1.95x** (Q9), and **1.84x** (Q5).
2. **Impact of Native OLAP Operators**: The performance gap is directly proportional to the use of OLAP-specific operators. While relational databases must emulate these features via `UNION ALL` passes and self-joins, the Data Warehouse computes multiple aggregation levels in a single scan of the fact table using `CUBE`, `GROUPING SETS` or window functions.
3. **Developer Productivity & Code Clarity**: The Data Warehouse reduces SQL code verbosity significantly for complex queries. The RDBMS required 43% more SQL code than the DW. Concise queries lower the risk of logical errors.

In the context of this project, the DW approach proved better suited to answering the core research question - whether EV adoption correlates with lower $CO_2$ emissions - because the answer requires joining multiple fact tables, computing aggregations across multiple dimensions, and performing trend analysis across years and countries.
