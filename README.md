# Data Management Project: EV Transition and Energy Sustainability Analysis

This project integrates datasets on global Electric Vehicle (EV) sales, carbon emissions, energy consumption, and socioeconomic indicators. The main goals are:
1. **EV Impact Assessment**: Analyze whether electric vehicle adoption leads to a net reduction in carbon emissions, or if it shifts the pollution source onto the electricity grid (fossil-fueled power plants).
2. **Economic Transition Disparity**: Contrast the EV transition between wealthy and developing nations, analyzing how Gross Domestic Product (GDP) relates to the transition towards clean energy.

---

## Dataset 1: Our World in Data (OWID) CO₂ & Greenhouse Gas Emissions

The selected subset of the OWID CO₂ dataset is filtered temporally to cover the period **2010–2024** to match the EV sales dataset. Below are the selected attributes, grouped by their analytical purpose:

### 1. Identifiers & Context
* **`country`**: The name of the geographic region or country. Used as a primary join key with EV and energy datasets.
* **`year`**: The observation year, filtered from **2010 to 2024** to align with the historical range of EV adoption.
* **`iso_code`**: Standardized ISO 3166-1 alpha-3 code. Essential for ensuring reliable joins across different datasets, avoiding naming discrepancies.
* **`population`**: Country population. Used as a normalization factor to compute custom per-capita metrics during aggregation.
* **`gdp`**: Gross Domestic Product (adjusted for inflation/PPP). Used to analyze the financial capacity of countries and contrast transition pathways between rich and developing nations.

### 2. General Emissions
* **`co2`**: Annual territorial $CO_2$ emissions from fossil fuels and industry (in million tonnes). Represents the core baseline metric to measure total national emission trends.
* **`co2_per_capita`**: Annual $CO_2$ emissions per person. Crucial for comparing carbon footprints across nations of different sizes.
* **`co2_per_gdp`**: $CO_2$ emissions relative to GDP. Measures the carbon intensity of a country's economic activity.

### 3. Source-Specific Emissions (Transition & Electricity Focus)
* **`oil_co2`**: Annual $CO_2$ emissions from oil combustion. Strongly linked to transport fuels (gasoline/diesel), indicating if EV growth is reducing transport-related emissions.
* **`oil_co2_per_capita`**: Oil emissions per person, offering a normalized view of transport-related fuel transition progress.
* **`coal_co2`**: Annual $CO_2$ emissions from coal. Represents the most carbon-intensive grid electricity source, helping to detect if EVs shift pollution to coal power.
* **`coal_co2_per_capita`**: Coal emissions per person, allowing normalized comparison of coal-dependence across countries.
* **`co2_per_unit_energy`**: Carbon intensity of the primary energy mix (grams of $CO_2$ per kilowatt-hour). Evaluates whether the overall energy infrastructure is becoming cleaner.
* **`primary_energy_consumption`**: Total primary energy consumption (in terawatt-hours). Used to measure total energy demand and contextualize electricity grid expansion.

### 4. Consumption-Based Emissions (Trade & Outsourcing Focus)
* **`consumption_co2`**: Consumption-based $CO_2$ emissions (adjusted for imports and exports). Avoids bias by tracking the true environmental footprint of a nation's demand.
* **`consumption_co2_per_capita`**: Consumption-based emissions per person, standardizing consumer-driven footprints.
* **`consumption_co2_per_gdp`**: Consumption-based emissions relative to GDP, indicating how cleanly a nation sustains its economic consumption.

---

## Dataset 2: Our World in Data (OWID) Energy Dataset

The selected subset of the OWID Energy dataset is filtered temporally to cover the period **2010–2024** to match the EV sales dataset. It focuses heavily on the electricity mix and grid cleanliness. 

*(Note: 'country', 'year', 'iso_code', 'population', 'gdp', and 'primary_energy_consumption' are dropped from this dataset in the final integrated output to avoid redundancy, as they are already provided by Dataset 1).*

Below are the selected attributes, grouped by their analytical purpose:

### 1. General Electricity Grid & Energy Metrics
* **`electricity_generation`**: Total electricity generated domestically (in terawatt-hours). Tracks the overall size of the domestic power grid.
* **`electricity_demand_tot`**: Total electricity demand (in terawatt-hours, renamed from `electricity_demand` in the ETL process). Used to evaluate if grid capacity and generation are growing sufficiently to meet the additional loads from EV adoption.

### 2. Clean vs. Fossil Electricity Breakdown (Mix of Generation)
* **`low_carbon_electricity`**: Electricity generated from low-carbon sources (nuclear and renewables combined) in terawatt-hours. Represents the total clean energy footprint of the grid.
* **`fossil_electricity`**: Electricity generated from fossil fuel sources (coal, oil, gas) in terawatt-hours.
* **`renewables_electricity`**: Electricity generated from renewable sources (wind, solar, hydro, biomass, etc.) in terawatt-hours.
* **`coal_electricity`**: Electricity generated from coal (in terawatt-hours). Essential for measuring coal-grid shift, the dirtiest generation source.
* **`gas_electricity`**: Electricity generated from natural gas (in terawatt-hours). Evaluates gas as a transitional fuel in the grid.
* **`oil_electricity`**: Electricity generated from oil (in terawatt-hours). Included for completeness of fossil fuel generation sources, although typically minor.
* **`nuclear_electricity`**: Electricity generated from nuclear power (in terawatt-hours). Tracks zero-carbon base-load capacity.
* **`hydro_electricity`**: Electricity generated from hydropower (in terawatt-hours). Tracks renewable base-load capacity.
* **`solar_electricity`**: Electricity generated from solar power (in terawatt-hours). Highlights solar energy transition.
* **`wind_electricity`**: Electricity generated from wind power (in terawatt-hours). Highlights wind energy transition.
* **`other_renewable_electricity`**: Electricity generated from other renewable sources (geothermal, biomass, waste-to-energy, etc.) in terawatt-hours. Crucial as a catch-all category to ensure the total renewable generation adds up perfectly.

### 3. Trade / Grid Interconnection
* **`net_elec_imports`**: Net electricity imports (imports minus exports) in terawatt-hours. Crucial for assessing if a country is importing clean or dirty power from its neighbors, which affects the true carbon footprint of EV charging.

---

## Dataset 3: Global EV Sales (IEA 2010–2024)

This dataset, sourced from the International Energy Agency (IEA), tracks annual electric vehicle sales, fleet stocks, charging infrastructure, and related energy and displacement metrics.

Unlike the OWID datasets, which are in "wide" format, this dataset is structured in a **"long" (key-value) format** in the raw files. In the ETL process, it is **pivoted** to transform the `parameter` column values into distinct fact columns (measures).

### 1. Identifiers & Context (Dimensions)
* **`country`**: The name of the country (renamed from `region` in the ETL process). Used as a primary join key.
* **`year`**: The observation year, filtered from **2010 to 2024**.
* **`mode`**: Vehicle segment (e.g., `Cars`, `Buses`, `Vans`, `Trucks`). Allows analyzing which road transport sectors are transitioning fastest.
* **`powertrain`**: Vehicle powertrain technology (`BEV` for battery electric, `PHEV` for plug-in hybrid, `FCEV` for hydrogen fuel cell) or charger types (`Publicly available fast`/`slow`).

### 2. Pivoted Metrics & Measures (Values)
* **`ev_sales`**: Number of new electric vehicles sold (pivoted from `EV sales`). Measures transition speed.
* **`ev_stock`**: Total active fleet of electric vehicles (pivoted from `EV stock`). Crucial to estimate total grid electricity demand.
* **`ev_sales_share`**: Percentage of EV sales relative to total new vehicle sales (pivoted from `EV sales share`). Perfect for cross-country market adoption comparisons.
* **`ev_stock_share`**: Percentage of EV stock relative to all vehicles on the road (pivoted from `EV stock share`).
* **`ev_charging_points`**: Number of charging stations (pivoted from `EV charging points`). Indicates supporting infrastructure readiness.
* **`electricity_demand_ev`**: Total electricity consumed by EVs in gigawatt-hours (pivoted and renamed from `Electricity demand` in the ETL process).
* **`oil_displacement_mbd`**: Estimated volume of oil displaced by EV usage in million barrels per day (pivoted from `Oil displacement Mbd`).
* **`oil_displacement,_million_lge`**: Estimated volume of oil displaced by EV usage in million liters of gasoline equivalent (pivoted from `Oil displacement, million lge`).