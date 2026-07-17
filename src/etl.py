import utility.extract as extract
import utility.transform as transform
import utility.load as load

def run_etl():
    """
    Main function to run the full ETL pipeline: Extract, Transform, and Load.
    """
    print("Starting the EV and Energy ETL Pipeline")

    ev, co2, energy, continent_mapping, gdp_pop, ember = extract.extract_data()
    
    ev_clean, co2_clean, energy_clean = transform.transform_data(
        ev, co2, energy, continent_mapping, gdp_pop, ember
    )
    
    load.load_data(ev_clean, co2_clean, energy_clean)
    
    print("ETL Pipeline completed successfully!")

if __name__ == "__main__":
    run_etl()
