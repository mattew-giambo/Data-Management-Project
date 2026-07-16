import pandas as pd

print("Loading the raw CSV data...")
ev = pd.read_csv("src/datasets/iea-global-ev-sales.csv", low_memory=False)
co2 = pd.read_csv("src/datasets/owid-co2-data.csv", low_memory=False)
energy = pd.read_csv("src/datasets/owid-energy-data.csv", low_memory=False)
continent_mapping = pd.read_csv("src/datasets/continent_country.csv", keep_default_na=False)

print("\n--- Data Profiling ---")
print("EV dataset categories:")
print(ev["category"].value_counts())
print(f"CO2 years: {co2['year'].min()} to {co2['year'].max()}")
print(f"Energy years: {energy['year'].min()} to {energy['year'].max()}")
print(f"Energy rows in 2025: {len(energy[energy['year'] == 2025])}")

def get_half_decade(year):
    if year <= 2014:
        return "2010-2014"
    elif year <= 2019:
        return "2015-2019"
    else:
        return "2020-2023"

def get_pandemic_period(year):
    if year < 2020:
        return "Pre-Pandemia"
    elif year <= 2021:
        return "Pandemia"
    else:
        return "Post-Pandemia"

# Map countries to continents using continent_country.csv
cc_unique = continent_mapping.drop_duplicates(subset=["Three_Letter_Country_Code"]).copy()
continent_name_map = cc_unique.set_index("Three_Letter_Country_Code")["Continent_Name"].to_dict()
continent_code_map = cc_unique.set_index("Three_Letter_Country_Code")["Continent_Code"].to_dict()

# 1. CLEANING THE IEA EV SALES DATASET
print("\nCleaning the EV dataset...")
# Only historical data between 2010 and 2023 are needed
ev_clean = ev[(ev["category"] == "Historical") & (ev["year"] >= 2010) & (ev["year"] <= 2023)].copy()
ev_clean = ev_clean.rename(columns={"region": "country"})

# Remove aggregates like 'World' or 'Europe' to keep only real countries
aggregates = ["World", "Europe", "EU27", "Rest of the world"]
ev_clean = ev_clean[~ev_clean["country"].isin(aggregates)]

# Get country-to-ISO mappings from the OWID datasets
co2_map = co2[["country", "iso_code"]].dropna().drop_duplicates().set_index("country")["iso_code"].to_dict()
energy_map = energy[["country", "iso_code"]].dropna().drop_duplicates().set_index("country")["iso_code"].to_dict()
country_to_iso = {**co2_map, **energy_map}

manual_map = {"USA": "USA", "Korea": "KOR", "Turkiye": "TUR", "Czech Republic": "CZE"}
for k, v in manual_map.items():
    country_to_iso[k] = v

# Rename countries to match the OWID standard names
corrections = {"USA": "United States", "Korea": "South Korea", "Turkiye": "Turkey", "Czech Republic": "Czechia"}
ev_clean["country"] = ev_clean["country"].replace(corrections)
ev_clean["iso_code"] = ev_clean["country"].map(country_to_iso)

# Remove any row where we couldn't map the ISO code
ev_clean = ev_clean.dropna(subset=["iso_code"])

# Filter out parameters we do not need for the analysis
unwanted_params = ["Oil displacement Mbd", "Oil displacement, million lge"]
ev_clean = ev_clean[~ev_clean["parameter"].isin(unwanted_params)]

# Pivot the dataset from long format to wide format
ev_wide = ev_clean.pivot_table(
    index=["country", "iso_code", "year", "mode", "powertrain"],
    columns="parameter",
    values="value",
    aggfunc="first"
).reset_index()

# Make column names lowercase and replace spaces with underscores
ev_wide.columns.name = None
ev_wide = ev_wide.rename(columns=lambda x: x.strip().lower().replace(" ", "_"))

# Replace NaN with 0 for EV metrics (if there is no record, sales/stock are 0)
ev_cols = ["ev_sales", "ev_stock", "ev_sales_share", "ev_stock_share", "electricity_demand", "ev_charging_points"]
for col in ev_cols:
    if col in ev_wide.columns:
        ev_wide[col] = ev_wide[col].fillna(0.0).astype(float)
ev_wide["year"] = ev_wide["year"].astype(int)

# Add the temporal and geographic attributes
ev_wide["halfDecade"] = ev_wide["year"].apply(get_half_decade)
ev_wide["pandemicPeriod"] = ev_wide["year"].apply(get_pandemic_period)
ev_wide["continent"] = ev_wide["iso_code"].map(continent_name_map)
ev_wide["continentCode"] = ev_wide["iso_code"].map(continent_code_map)

# Rename EV columns to match the names in the DFM/Star Schema
rename_ev = {
    "iso_code": "isoCode",
    "mode": "vehicleType",
    "ev_sales": "evSales",
    "ev_sales_share": "evSalesShare",
    "ev_stock": "evStock",
    "ev_stock_share": "evStockShare",
    "electricity_demand": "evElectricityDemand",
    "ev_charging_points": "evChargingPoints"
}
ev_wide = ev_wide.rename(columns=rename_ev)

ev_cols_order = [
    "country", "isoCode", "continent", "continentCode", 
    "year", "halfDecade", "pandemicPeriod", 
    "vehicleType", "powertrain", 
    "evSales", "evSalesShare", "evStock", "evStockShare", "evElectricityDemand", "evChargingPoints"
]
ev_wide = ev_wide[ev_cols_order]

# 2. CLEANING THE OWID CO2 DATASET
print("Cleaning the CO2 dataset...")
co2_cols = [
    "country", "year", "iso_code", "population", "gdp", 
    "co2", "co2_per_capita", "co2_per_gdp", 
    "oil_co2", "oil_co2_per_capita", "coal_co2", "coal_co2_per_capita", 
    "co2_per_unit_energy", "primary_energy_consumption"
]

co2_clean = co2[co2_cols].dropna(subset=["iso_code"]).copy()
co2_clean = co2_clean[(co2_clean["year"] >= 2010) & (co2_clean["year"] <= 2023)]
co2_clean["year"] = co2_clean["year"].astype(int)
for col in co2_cols:
    if col not in ["country", "iso_code", "year"]:
        co2_clean[col] = co2_clean[col].astype(float)

co2_clean["halfDecade"] = co2_clean["year"].apply(get_half_decade)
co2_clean["pandemicPeriod"] = co2_clean["year"].apply(get_pandemic_period)
co2_clean["continent"] = co2_clean["iso_code"].map(continent_name_map)
co2_clean["continentCode"] = co2_clean["iso_code"].map(continent_code_map)

rename_co2 = {
    "iso_code": "isoCode",
    "gdp": "GDP",
    "co2": "co2Emissions",
    "co2_per_capita": "co2PerCapita",
    "co2_per_gdp": "co2PerGDP",
    "oil_co2": "co2EmissionsOil",
    "oil_co2_per_capita": "co2EmissionsOilPerCapita",
    "coal_co2": "co2EmissionsCoal",
    "coal_co2_per_capita": "co2EmissionsCoalPerCapita",
    "co2_per_unit_energy": "co2EmissionsPerUnitEnergy",
    "primary_energy_consumption": "energyConsumption"
}
co2_clean = co2_clean.rename(columns=rename_co2)

co2_cols_order = [
    "country", "isoCode", "continent", "continentCode", 
    "year", "halfDecade", "pandemicPeriod", 
    "population", "GDP", "co2Emissions", "co2PerCapita", "co2PerGDP", 
    "co2EmissionsOil", "co2EmissionsOilPerCapita", "co2EmissionsCoal", "co2EmissionsCoalPerCapita", 
    "co2EmissionsPerUnitEnergy", "energyConsumption"
]
co2_clean = co2_clean[co2_cols_order]

# 3. CLEANING THE OWID ENERGY DATASET
print("Cleaning the Energy dataset...")
energy_cols = [
    "country", "year", "iso_code", "population", "gdp", 
    "electricity_generation", "electricity_demand", "primary_energy_consumption", 
    "low_carbon_electricity", "fossil_electricity", "renewables_electricity", 
    "coal_electricity", "gas_electricity", "oil_electricity", 
    "nuclear_electricity", "hydro_electricity", "solar_electricity", 
    "wind_electricity", "other_renewable_electricity", "net_elec_imports"
]

energy_clean = energy[energy_cols].dropna(subset=["iso_code"]).copy()
energy_clean = energy_clean[(energy_clean["year"] >= 2010) & (energy_clean["year"] <= 2023)]
energy_clean["year"] = energy_clean["year"].astype(int)
for col in energy_cols:
    if col not in ["country", "iso_code", "year"]:
        energy_clean[col] = energy_clean[col].astype(float)

energy_clean["halfDecade"] = energy_clean["year"].apply(get_half_decade)
energy_clean["pandemicPeriod"] = energy_clean["year"].apply(get_pandemic_period)
energy_clean["continent"] = energy_clean["iso_code"].map(continent_name_map)
energy_clean["continentCode"] = energy_clean["iso_code"].map(continent_code_map)

rename_energy = {
    "iso_code": "isoCode",
    "gdp": "GDP",
    "primary_energy_consumption": "energyConsumption",
    "electricity_generation": "electricityGeneration",
    "electricity_demand": "electricityDemand",
    "fossil_electricity": "fossilElectricityGeneration",
    "coal_electricity": "coalElectricityGeneration",
    "oil_electricity": "oilElectricityGeneration",
    "gas_electricity": "gasElectricityGeneration",
    "renewables_electricity": "renewableElectricityGeneration",
    "low_carbon_electricity": "lowCarbonElectricityGeneration",
    "wind_electricity": "windElectricityGeneration",
    "hydro_electricity": "hydroElectricityGeneration",
    "nuclear_electricity": "nuclearElectricityGeneration",
    "other_renewable_electricity": "otherElectricityGeneration",
    "solar_electricity": "solarElectricityGeneration",
    "net_elec_imports": "netElectricityImports"
}
energy_clean = energy_clean.rename(columns=rename_energy)

energy_cols_order = [
    "country", "isoCode", "continent", "continentCode", 
    "year", "halfDecade", "pandemicPeriod", 
    "population", "GDP", "energyConsumption", 
    "electricityGeneration", "electricityDemand", 
    "fossilElectricityGeneration", "coalElectricityGeneration", "oilElectricityGeneration", "gasElectricityGeneration", 
    "renewableElectricityGeneration", "lowCarbonElectricityGeneration", 
    "windElectricityGeneration", "hydroElectricityGeneration", "nuclearElectricityGeneration", 
    "otherElectricityGeneration", "solarElectricityGeneration", "netElectricityImports"
]
energy_clean = energy_clean[energy_cols_order]

print("Saving cleaned datasets to staging_area/...")
ev_wide.to_csv("staging_area/clean_iea_ev_sales.csv", index=False)
co2_clean.to_csv("staging_area/clean_owid_co2.csv", index=False)
energy_clean.to_csv("staging_area/clean_owid_energy.csv", index=False)

print("\n=== Data Validation Stage ===")

# Checking row counts and making sure there are no missing country codes (ISOs)
print(f"EV Clean dataset: {len(ev_wide)} rows. Missing ISOs: {ev_wide['isoCode'].isnull().sum()}")
print(f"CO2 Clean dataset: {len(co2_clean)} rows. Missing ISOs: {co2_clean['isoCode'].isnull().sum()}")
print(f"Energy Clean dataset: {len(energy_clean)} rows. Missing ISOs: {energy_clean['isoCode'].isnull().sum()}")

# Checking year ranges to verify that the temporal alignment (2010 to 2023)
print(f"EV year range: {ev_wide['year'].min()} to {ev_wide['year'].max()}")
print(f"CO2 year range: {co2_clean['year'].min()} to {co2_clean['year'].max()}")
print(f"Energy year range: {energy_clean['year'].min()} to {energy_clean['year'].max()}")

# Checking geographic overlap to verify that all EV countries also exist in CO2/Energy datasets
ev_isos = set(ev_wide["isoCode"].unique())
co2_isos = set(co2_clean["isoCode"].unique())
energy_isos = set(energy_clean["isoCode"].unique())

print(f"Total EV country codes mapped: {len(ev_isos)}")

missing_in_co2 = ev_isos.difference(co2_isos)
missing_in_energy = ev_isos.difference(energy_isos)

if len(missing_in_co2) == 0:
    print("Success: All EV countries exist in the CO2 dataset.")
else:
    print(f"Warning: These EV countries are missing in CO2: {missing_in_co2}")

if len(missing_in_energy) == 0:
    print("Success: All EV countries exist in the Energy dataset.")
else:
    print(f"Warning: These EV countries are missing in Energy: {missing_in_energy}")

print("Data cleaning and validation completed successfully!")
