import pandas as pd
from pathlib import Path

def extract_data():
    """
    This function extracts raw data from the datasets folder.
    It reads all the CSV files and returns them as pandas DataFrames.
    """
    print("=== Extracting Raw Data ===")
    
    base_path = Path(__file__).resolve().parents[2] 
    
    ev_path = base_path / "raw_datasets" / "iea-global-ev-sales.csv"
    co2_path = base_path / "raw_datasets" / "owid-co2-data.csv"
    energy_path = base_path / "raw_datasets" / "owid-energy-data.csv"
    continent_path = base_path / "raw_datasets" / "continent_country.csv"
    gdp_pop_path = base_path / "raw_datasets" / "gdp_population_countries.csv"
    ember_path = base_path / "raw_datasets" / "release_generation_yearly_global.csv"
            
    print("Loading IEA Global EV Sales dataset...")
    ev = pd.read_csv(ev_path, low_memory=False)
    print(f"> EV data loaded. Found {len(ev)} rows.")
    
    print("Loading OWID CO2 dataset...")
    co2 = pd.read_csv(co2_path, low_memory=False)
    print(f"> CO2 data loaded. Found {len(co2)} rows.")
    
    print("Loading OWID Energy dataset...")
    energy = pd.read_csv(energy_path, low_memory=False)
    print(f"> Energy data loaded. Found {len(energy)} rows.")
    
    print("Loading continent country mapping...")
    continent_mapping = pd.read_csv(continent_path, keep_default_na=False)
    print(f"> Continent mapping loaded. Found {len(continent_mapping)} rows.")
    
    print("Loading GDP and Population World Bank dataset...")
    gdp_pop = pd.read_csv(gdp_pop_path, low_memory=False)
    print(f"> GDP and Population data loaded. Found {len(gdp_pop)} rows.")
    
    print("Loading Ember global electricity generation dataset...")
    ember = pd.read_csv(ember_path, low_memory=False)
    print(f"> Ember data loaded. Found {len(ember)} rows.")
    
    print("Extraction phase completed successfully!\n")
    return ev, co2, energy, continent_mapping, gdp_pop, ember

if __name__ == "__main__":
    try:
        extract_data()
    except Exception as e:
        print(f"Error during extraction: {e}")
