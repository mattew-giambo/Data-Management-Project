import utility.extract as extract
import utility.transform as transform
import utility.load as load
import utility.db_loader as db_loader


def run_etl(skip_db: bool = False):
    """
    Main function to run the full ETL pipeline: Extract, Transform, Load, and
    Insert into the PostgreSQL database.

    Parameters
    ----------
    db_host     : PostgreSQL server hostname.
    db_port     : PostgreSQL server port.
    db_name     : Target database name (must exist and be initialised via init.sql).
    db_user     : PostgreSQL username.
    db_password : PostgreSQL password.
    skip_db     : If True, skips the database insertion step (CSV-only mode).
    """
    print("Starting the EV and Energy ETL Pipeline")

    ev, co2, energy, continent_mapping, gdp_pop, ember = extract.extract_data()

    ev_clean, co2_clean, energy_clean = transform.transform_data(
        ev, co2, energy, continent_mapping, gdp_pop, ember
    )

    load.load_data(ev_clean, co2_clean, energy_clean)

    if not skip_db:
        db_loader.insert_to_db(
            ev_df=ev_clean,
            co2_df=co2_clean,
            energy_df=energy_clean
        )

    print("ETL Pipeline completed successfully!")


if __name__ == "__main__":
    run_etl()
