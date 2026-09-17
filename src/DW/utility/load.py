from pathlib import Path

def load_data(ev_wide, infra_clean, co2_clean, energy_clean):
    """
    Saves the cleaned DataFrames as CSV files in the clean_datasets folder
    and performs basic validation checks.
    """
    print("=== Loading Cleaned Data ===")
    
    base_path = Path(__file__).resolve().parents[3] 
    
    ev_path = base_path / "clean_datasets" / "clean_iea_ev_sales.csv"
    infra_path = base_path / "clean_datasets" / "clean_iea_ev_infrastructure.csv"
    co2_path = base_path / "clean_datasets" / "clean_owid_co2.csv"
    energy_path = base_path / "clean_datasets" / "clean_owid_energy.csv"

    print("Saving cleaned datasets to clean_datasets/...")
    ev_wide.to_csv(ev_path, index=False)
    infra_clean.to_csv(infra_path, index=False)
    co2_clean.to_csv(co2_path, index=False)
    energy_clean.to_csv(energy_path, index=False)
    print("Clean CSV files successfully saved!\n")
    
    print("=== Data Validation Stage ===")
    
    # Check row counts and missing country codes
    print(f"EV Market dataset: {len(ev_wide)} rows. Missing ISOs: {ev_wide['isoCode'].isnull().sum()}")
    print(f"EV Infrastructure dataset: {len(infra_clean)} rows. Missing ISOs: {infra_clean['isoCode'].isnull().sum()}")
    print(f"CO2 Clean dataset: {len(co2_clean)} rows. Missing ISOs: {co2_clean['isoCode'].isnull().sum()}")
    print(f"Energy Clean dataset: {len(energy_clean)} rows. Missing ISOs: {energy_clean['isoCode'].isnull().sum()}")
    
    # Check temporal range alignment
    print(f"EV year range: {ev_wide['year'].min()} to {ev_wide['year'].max()}")
    print(f"Infra year range: {infra_clean['year'].min()} to {infra_clean['year'].max()}")
    print(f"CO2 year range: {co2_clean['year'].min()} to {co2_clean['year'].max()}")
    print(f"Energy year range: {energy_clean['year'].min()} to {energy_clean['year'].max()}")
    
    # Check geographic coverage
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
        
    print("Data loading and validation completed successfully!")
