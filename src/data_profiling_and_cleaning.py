import os
import pandas as pd
import numpy as np

# Define path locations relative to the script location
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
datasets_dir = os.path.join(script_dir, "datasets")
staging_dir = os.path.join(project_dir, "staging_area")

os.makedirs(staging_dir, exist_ok=True)

def run_profiling(df_ev, df_co2, df_energy):
    """
    Performs data profiling to identify projections, range overlaps, country mismatches,
    and missing values in the raw datasets.
    """
    print("\n" + "="*50)
    # 1. Projections and Scenarios Detection
    print("\n[PROFILING] 1. PROJECTIONS AND SCENARIOS DETECTION")
    print("IEA EV Sales categories:")
    for cat in df_ev['category'].unique():
        sub = df_ev[df_ev['category'] == cat]
        print(f"  - Category '{cat}': {sub['year'].min()} to {sub['year'].max()} (Rows: {len(sub)})")

    print(f"\nOWID CO2 Year range: {df_co2['year'].min()} to {df_co2['year'].max()}")
    print(f"OWID Energy Year range: {df_energy['year'].min()} to {df_energy['year'].max()}")
    future_energy = df_energy[df_energy['year'] > 2024]
    print(f"  - Rows with year > 2024 in Energy dataset: {len(future_energy)}")

    # 2. Country and ISO Code Alignment
    print("\n[PROFILING] 2. COUNTRY AND ISO CODE ALIGNMENT")
    co2_map = df_co2[['country', 'iso_code']].dropna().drop_duplicates().set_index('country')['iso_code'].to_dict()
    energy_map = df_energy[['country', 'iso_code']].dropna().drop_duplicates().set_index('country')['iso_code'].to_dict()
    country_to_iso = {**co2_map, **energy_map}

    # Manual overrides for known country names in IEA EV Sales
    manual_mappings = {"USA": "USA", "Korea": "KOR", "Turkiye": "TUR", "Czech Republic": "CZE"}
    for k, v in manual_mappings.items():
        country_to_iso[k] = v

    ev_regions = df_ev['region'].unique()
    mapped_count = sum(1 for r in ev_regions if r in country_to_iso)
    unmapped = [r for r in ev_regions if r not in country_to_iso]

    print(f"IEA Regions: {len(ev_regions)} total. Mapped to ISO: {mapped_count}. Unmapped: {len(unmapped)}")
    print(f"  - Unmapped regions (regional/economic aggregates): {unmapped}")

    # 3. Anomalies and Negative Values Check
    print("\n[PROFILING] 3. ANOMALIES AND NEGATIVE VALUES")
    print(f"  - Negative values in IEA EV Sales: {len(df_ev[df_ev['value'] < 0])}")
    print(f"  - Negative values in OWID CO2 (co2): {len(df_co2[df_co2['co2'] < 0])}")
    print(f"  - Negative values in OWID Energy (electricity_generation): {len(df_energy[df_energy['electricity_generation'] < 0])}")
    print(f"  - Negative values in OWID Energy (net_elec_imports): {len(df_energy[df_energy['net_elec_imports'] < 0])} (Expected, net export balance)")
    print("="*50 + "\n")

def run_cleaning(df_ev, df_co2, df_energy):
    """
    Cleans the datasets: filters out projections, aligns years to 2010-2023, standardizes country names,
    generates ISO codes for IEA EV sales, handles null values appropriately, pivots the EV dataset,
    and saves clean staging CSV files.
    """
    print("Starting Data Cleaning Process...")

    # 1. CLEANING IEA EV SALES
    print("  - Cleaning IEA EV Sales...")
    # Keep only historical data
    df_ev_clean = df_ev[df_ev['category'] == 'Historical'].copy()
    
    # Filter years (2010 - 2023)
    df_ev_clean = df_ev_clean[(df_ev_clean['year'] >= 2010) & (df_ev_clean['year'] <= 2023)]
    
    # Standardize region column name
    df_ev_clean = df_ev_clean.rename(columns={'region': 'country'})
    
    # Filter out regional aggregates
    aggregates_to_remove = ['World', 'Europe', 'EU27', 'Rest of the world']
    df_ev_clean = df_ev_clean[~df_ev_clean['country'].isin(aggregates_to_remove)]
    
    # Build country to ISO code mapping
    co2_map = df_co2[['country', 'iso_code']].dropna().drop_duplicates().set_index('country')['iso_code'].to_dict()
    energy_map = df_energy[['country', 'iso_code']].dropna().drop_duplicates().set_index('country')['iso_code'].to_dict()
    country_to_iso = {**co2_map, **energy_map}
    
    # Manual mappings
    manual_mappings = {"USA": "USA", "Korea": "KOR", "Turkiye": "TUR", "Czech Republic": "CZE"}
    for k, v in manual_mappings.items():
        country_to_iso[k] = v
        
    # Standardize country names to match OWID standard
    country_name_corrections = {
        "USA": "United States",
        "Korea": "South Korea",
        "Turkiye": "Turkey",
        "Czech Republic": "Czechia"
    }
    df_ev_clean['country'] = df_ev_clean['country'].replace(country_name_corrections)
    
    # Map country to standard ISO-3 codes
    df_ev_clean['iso_code'] = df_ev_clean['country'].map(country_to_iso)
    df_ev_clean = df_ev_clean.dropna(subset=['iso_code'])

    # Exclude non-EV parameters
    df_ev_clean = df_ev_clean[~df_ev_clean['parameter'].isin(['Oil displacement Mbd', 'Oil displacement, million lge'])]

    # Pivot EV Sales from Long to Wide format
    df_ev_wide = df_ev_clean.pivot_table(
        index=['country', 'iso_code', 'year', 'mode', 'powertrain'],
        columns='parameter',
        values='value',
        aggfunc='first'
    ).reset_index()

    # Clean pivoted column names for SQL compliance
    df_ev_wide.columns.name = None
    df_ev_wide = df_ev_wide.rename(columns=lambda x: x.strip().lower().replace(" ", "_"))

    # Impute missing pivoted EV measures with 0.0 (absence of record indicates no sales/stock)
    ev_measures = ['ev_sales', 'ev_stock', 'ev_sales_share', 'ev_stock_share', 'electricity_demand', 'ev_charging_points']
    for col in ev_measures:
        if col in df_ev_wide.columns:
            df_ev_wide[col] = df_ev_wide[col].fillna(0.0).astype(float)
            
    df_ev_wide['year'] = df_ev_wide['year'].astype(int)

    # 2. CLEANING OWID CO2 DATA
    print("  - Cleaning OWID CO2 emissions...")
    co2_cols = [
        'country', 'year', 'iso_code', 'population', 'gdp', 
        'co2', 'co2_per_capita', 'co2_per_gdp', 
        'oil_co2', 'oil_co2_per_capita', 'coal_co2', 'coal_co2_per_capita', 
        'co2_per_unit_energy', 'primary_energy_consumption'
    ]
    df_co2_clean = df_co2[co2_cols].copy()
    
    # Remove regional aggregates (which have null iso_code)
    df_co2_clean = df_co2_clean.dropna(subset=['iso_code'])
    
    # Align temporal range (2010 - 2023)
    df_co2_clean = df_co2_clean[(df_co2_clean['year'] >= 2010) & (df_co2_clean['year'] <= 2023)]
    
    df_co2_clean['year'] = df_co2_clean['year'].astype(int)
    for col in co2_cols:
        if col not in ['country', 'iso_code', 'year']:
            df_co2_clean[col] = df_co2_clean[col].astype(float)

    # 3. CLEANING OWID ENERGY DATA
    print("  - Cleaning OWID Energy consumption...")
    energy_cols = [
        'country', 'year', 'iso_code', 'population', 'gdp', 
        'electricity_generation', 'electricity_demand', 'primary_energy_consumption', 
        'low_carbon_electricity', 'fossil_electricity', 'renewables_electricity', 
        'coal_electricity', 'gas_electricity', 'oil_electricity', 
        'nuclear_electricity', 'hydro_electricity', 'solar_electricity', 
        'wind_electricity', 'other_renewable_electricity', 'net_elec_imports'
    ]
    df_energy_clean = df_energy[energy_cols].copy()
    
    # Remove regional aggregates
    df_energy_clean = df_energy_clean.dropna(subset=['iso_code'])
    
    # Align temporal range (2010 - 2023)
    df_energy_clean = df_energy_clean[(df_energy_clean['year'] >= 2010) & (df_energy_clean['year'] <= 2023)]
    
    df_energy_clean['year'] = df_energy_clean['year'].astype(int)
    for col in energy_cols:
        if col not in ['country', 'iso_code', 'year']:
            df_energy_clean[col] = df_energy_clean[col].astype(float)

    # SAVE TO STAGING AREA
    print(f"Saving cleaned files to: {staging_dir}")
    df_ev_wide.to_csv(os.path.join(staging_dir, "clean_iea_ev_sales.csv"), index=False)
    df_co2_clean.to_csv(os.path.join(staging_dir, "clean_owid_co2.csv"), index=False)
    df_energy_clean.to_csv(os.path.join(staging_dir, "clean_owid_energy.csv"), index=False)
    print("Data Cleaning Process Complete!")
    return df_ev_wide, df_co2_clean, df_energy_clean

def run_validation(df_ev, df_co2, df_energy):
    """
    Validates output datasets to ensure no nulls in conformed keys, 
    perfect temporal alignment, and country overlap.
    """
    print("\n" + "="*50)
    print("[VALIDATION] VERIFYING CLEANED DATASETS IN STAGING AREA")
    
    # Check nulls in PKs
    ev_null_iso = df_ev['iso_code'].isnull().sum()
    ev_null_year = df_ev['year'].isnull().sum()
    co2_null_iso = df_co2['iso_code'].isnull().sum()
    co2_null_year = df_co2['year'].isnull().sum()
    energy_null_iso = df_energy['iso_code'].isnull().sum()
    energy_null_year = df_energy['year'].isnull().sum()
    
    print("1. Null Primary Keys Check:")
    print(f"  - EV Sales: Null ISOs = {ev_null_iso}, Null Years = {ev_null_year}")
    print(f"  - CO2: Null ISOs = {co2_null_iso}, Null Years = {co2_null_year}")
    print(f"  - Energy: Null ISOs = {energy_null_iso}, Null Years = {energy_null_year}")

    # Check temporal bounds
    print("2. Temporal Bounds Check:")
    print(f"  - EV Sales: Year range {df_ev['year'].min()} to {df_ev['year'].max()}")
    print(f"  - CO2: Year range {df_co2['year'].min()} to {df_co2['year'].max()}")
    print(f"  - Energy: Year range {df_energy['year'].min()} to {df_energy['year'].max()}")

    # Check geographical intersection
    ev_isos = set(df_ev['iso_code'].unique())
    co2_isos = set(df_co2['iso_code'].unique())
    energy_isos = set(df_energy['iso_code'].unique())
    
    missing_in_co2 = ev_isos.difference(co2_isos)
    missing_in_energy = ev_isos.difference(energy_isos)
    
    print("3. Geographical Intersection Check:")
    print(f"  - Unique ISO codes in EV Sales: {len(ev_isos)}")
    print(f"  - EV ISO codes missing in CO2 dataset: {missing_in_co2}")
    print(f"  - EV ISO codes missing in Energy dataset: {missing_in_energy}")
    
    if len(missing_in_co2) == 0 and len(missing_in_energy) == 0:
        print("  - [SUCCESS] 100% geographical overlap. Staging datasets are clean and conformed!")
    else:
        print("  - [WARNING] Found unmatched countries between datasets.")
    print("="*50 + "\n")

if __name__ == "__main__":
    try:
        # Load raw CSV datasets
        print("Loading raw datasets...")
        raw_ev = pd.read_csv(os.path.join(datasets_dir, "iea-global-ev-sales.csv"), low_memory=False)
        raw_co2 = pd.read_csv(os.path.join(datasets_dir, "owid-co2-data.csv"), low_memory=False)
        raw_energy = pd.read_csv(os.path.join(datasets_dir, "owid-energy-data.csv"), low_memory=False)

        # 1. Run Data Profiling
        run_profiling(raw_ev, raw_co2, raw_energy)
        
        # 2. Run Data Cleaning
        clean_ev, clean_co2, clean_energy = run_cleaning(raw_ev, raw_co2, raw_energy)
        
        # 3. Run Validation
        run_validation(clean_ev, clean_co2, clean_energy)
        
    except Exception as e:
        print(f"Error in data staging pipeline: {e}")
