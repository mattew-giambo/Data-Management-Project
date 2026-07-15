import pandas as pd

print("Loading raw CSV files...")
ev = pd.read_csv("src/datasets/iea-global-ev-sales.csv", low_memory=False)
co2 = pd.read_csv("src/datasets/owid-co2-data.csv", low_memory=False)
energy = pd.read_csv("src/datasets/owid-energy-data.csv", low_memory=False)

print("\n--- Raw Data Profiling ---")
# Show ranges and categories to identify projections and inconsistencies
print("EV Categories:")
print(ev["category"].value_counts())
print(f"CO2 Years: {co2['year'].min()} to {co2['year'].max()}")
print(f"Energy Years: {energy['year'].min()} to {energy['year'].max()}")
print(f"Energy rows in 2025: {len(energy[energy['year'] == 2025])}")

# 1. Clean IEA EV Sales
print("\nCleaning EV dataset...")
# Keep only historical data from 2010 to 2023
ev_clean = ev[(ev["category"] == "Historical") & (ev["year"] >= 2010) & (ev["year"] <= 2023)].copy()
ev_clean = ev_clean.rename(columns={"region": "country"})

# Filter out regional aggregates
aggregates = ["World", "Europe", "EU27", "Rest of the world"]
ev_clean = ev_clean[~ev_clean["country"].isin(aggregates)]

# Build country -> ISO mapping from OWID datasets
co2_map = co2[["country", "iso_code"]].dropna().drop_duplicates().set_index("country")["iso_code"].to_dict()
energy_map = energy[["country", "iso_code"]].dropna().drop_duplicates().set_index("country")["iso_code"].to_dict()
country_to_iso = {**co2_map, **energy_map}

# Manual overrides for IEA country name mismatches
manual_map = {"USA": "USA", "Korea": "KOR", "Turkiye": "TUR", "Czech Republic": "CZE"}
for k, v in manual_map.items():
    country_to_iso[k] = v

# Standardize names to match OWID standard
corrections = {"USA": "United States", "Korea": "South Korea", "Turkiye": "Turkey", "Czech Republic": "Czechia"}
ev_clean["country"] = ev_clean["country"].replace(corrections)
ev_clean["iso_code"] = ev_clean["country"].map(country_to_iso)

# Drop any unmapped ISO rows (safety check)
ev_clean = ev_clean.dropna(subset=["iso_code"])

# Remove unwanted parameters
unwanted_params = ["Oil displacement Mbd", "Oil displacement, million lge"]
ev_clean = ev_clean[~ev_clean["parameter"].isin(unwanted_params)]

# Pivot to wide format
ev_wide = ev_clean.pivot_table(
    index=["country", "iso_code", "year", "mode", "powertrain"],
    columns="parameter",
    values="value",
    aggfunc="first"
).reset_index()

# Format column names for SQL compliance
ev_wide.columns.name = None
ev_wide = ev_wide.rename(columns=lambda x: x.strip().lower().replace(" ", "_"))

# Fill EV metrics NaNs with 0 (absence of record indicates 0 sales/stock)
ev_cols = ["ev_sales", "ev_stock", "ev_sales_share", "ev_stock_share", "electricity_demand", "ev_charging_points"]
for col in ev_cols:
    if col in ev_wide.columns:
        ev_wide[col] = ev_wide[col].fillna(0.0).astype(float)
ev_wide["year"] = ev_wide["year"].astype(int)

# 2. Clean OWID CO2 Data
print("Cleaning CO2 dataset...")
co2_cols = [
    "country", "year", "iso_code", "population", "gdp", 
    "co2", "co2_per_capita", "co2_per_gdp", 
    "oil_co2", "oil_co2_per_capita", "coal_co2", "coal_co2_per_capita", 
    "co2_per_unit_energy", "primary_energy_consumption"
]
# Filter out regional aggregates (null iso_code) and align years to 2010-2023
co2_clean = co2[co2_cols].dropna(subset=["iso_code"]).copy()
co2_clean = co2_clean[(co2_clean["year"] >= 2010) & (co2_clean["year"] <= 2023)]
co2_clean["year"] = co2_clean["year"].astype(int)
for col in co2_cols:
    if col not in ["country", "iso_code", "year"]:
        co2_clean[col] = co2_clean[col].astype(float)

# 3. Clean OWID Energy Data
print("Cleaning Energy dataset...")
energy_cols = [
    "country", "year", "iso_code", "population", "gdp", 
    "electricity_generation", "electricity_demand", "primary_energy_consumption", 
    "low_carbon_electricity", "fossil_electricity", "renewables_electricity", 
    "coal_electricity", "gas_electricity", "oil_electricity", 
    "nuclear_electricity", "hydro_electricity", "solar_electricity", 
    "wind_electricity", "other_renewable_electricity", "net_elec_imports"
]
# Filter out regional aggregates and align years to 2010-2023
energy_clean = energy[energy_cols].dropna(subset=["iso_code"]).copy()
energy_clean = energy_clean[(energy_clean["year"] >= 2010) & (energy_clean["year"] <= 2023)]
energy_clean["year"] = energy_clean["year"].astype(int)
for col in energy_cols:
    if col not in ["country", "iso_code", "year"]:
        energy_clean[col] = energy_clean[col].astype(float)

# Save staging datasets (assuming staging_area already exists)
print("Saving cleaned datasets to staging_area/...")
ev_wide.to_csv("staging_area/clean_iea_ev_sales.csv", index=False)
co2_clean.to_csv("staging_area/clean_owid_co2.csv", index=False)
energy_clean.to_csv("staging_area/clean_owid_energy.csv", index=False)

print("\n--- Validation Checks ---")
print(f"EV clean rows: {len(ev_wide)} (Null ISOs: {ev_wide['iso_code'].isnull().sum()})")
print(f"CO2 clean rows: {len(co2_clean)} (Null ISOs: {co2_clean['iso_code'].isnull().sum()})")
print(f"Energy clean rows: {len(energy_clean)} (Null ISOs: {energy_clean['iso_code'].isnull().sum()})")
print(f"EV Year range: {ev_wide['year'].min()} to {ev_wide['year'].max()}")
print(f"CO2 Year range: {co2_clean['year'].min()} to {co2_clean['year'].max()}")
print(f"Energy Year range: {energy_clean['year'].min()} to {energy_clean['year'].max()}")

# Verify ISO overlaps
ev_isos = set(ev_wide["iso_code"].unique())
co2_isos = set(co2_clean["iso_code"].unique())
energy_isos = set(energy_clean["iso_code"].unique())
print(f"EV countries mapped: {len(ev_isos)}")
print(f"EV ISOs missing in CO2: {ev_isos.difference(co2_isos)}")
print(f"EV ISOs missing in Energy: {ev_isos.difference(energy_isos)}")
print("Staging preparation finished successfully!")
