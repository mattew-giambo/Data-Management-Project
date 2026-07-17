import extract
import transform
import load

def run_etl():
    """
    Main function to run the full ETL pipeline: Extract, Transform, and Load.
    """
    print("Starting the EV and Energy ETL Pipeline")

    ev, co2, energy, continent_mapping = extract.extract_data()
    
    ev_clean, co2_clean, energy_clean = transform.transform_data(
        ev, co2, energy, continent_mapping
    )
    
    load.load_data(ev_clean, co2_clean, energy_clean)
    
    print("ETL Pipeline completed successfully!")

if __name__ == "__main__":
    run_etl()
