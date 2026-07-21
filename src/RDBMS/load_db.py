"""
populate_relazionale.py
=======================
Standalone script that reads from the pre-cleaned CSVs in clean_datasets/
and inserts all data into the GREEN_MOBILITY_RDBMS PostgreSQL database.

Prerequisites
-------------
1. PostgreSQL running on localhost:5432
2. The schema has been initialised:
       psql -U postgres -f src/RDBMS/schema_relazionale.sql
3. The clean_datasets/ directory contains:
       clean_iea_ev_sales.csv
       clean_iea_ev_infrastructure.csv
       clean_owid_co2.csv
       clean_owid_energy.csv

Usage
-----
    python src/RDBMS/populate_relazionale.py

    # Override connection details:
    python src/RDBMS/populate_relazionale.py \
        --host localhost --port 5432 \
        --dbname green_mobility_rdbms \
        --user postgres --password postgres
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nan_to_none(value):
    """Convert NaN / Inf to None for PostgreSQL NULL compatibility."""
    if value is None:
        return None
    try:
        if np.isnan(value) or np.isinf(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def get_connection(host, port, dbname, user, password):
    return psycopg2.connect(
        host=host, port=port, dbname=dbname, user=user, password=password
    )


# ---------------------------------------------------------------------------
# Lookup-table loaders  (return name → id dicts)
# ---------------------------------------------------------------------------

def load_countries(cur, ev_df: pd.DataFrame, co2_df: pd.DataFrame) -> dict:
    """Insert distinct countries and return {iso_code: country_id}."""
    print("  Loading Country table...")

    # Collect from both sources
    cols = ["iso_code", "country", "continent", "continent_code"]
    rename_ev  = {"isoCode": "iso_code", "country": "country",
                  "continent": "continent", "continentCode": "continent_code"}
    rename_co2 = {"isoCode": "iso_code", "country": "country",
                  "continent": "continent", "continentCode": "continent_code"}

    ev_c  = ev_df.rename(columns=rename_ev)[cols].drop_duplicates("iso_code")
    co2_c = co2_df.rename(columns=rename_co2)[cols].drop_duplicates("iso_code")
    all_c = (
        pd.concat([ev_c, co2_c], ignore_index=True)
        .drop_duplicates("iso_code")
        .dropna(subset=["iso_code"])
    )

    sql = """
        INSERT INTO Country (iso_code, country_name, continent, continent_code)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (iso_code) DO NOTHING;
    """
    for _, row in all_c.iterrows():
        cur.execute(sql, (
            row["iso_code"],
            row["country"],
            _nan_to_none(row.get("continent")),
            _nan_to_none(row.get("continent_code")),
        ))

    cur.execute("SELECT country_id, iso_code FROM Country;")
    mapping = {iso: cid for cid, iso in cur.fetchall()}
    print(f"    → {len(mapping)} countries loaded.")
    return mapping


def load_years(cur, ev_df: pd.DataFrame, co2_df: pd.DataFrame) -> dict:
    """Insert distinct years and return {year: year_id}."""
    print("  Loading Year table...")

    rename_ev  = {"year": "year", "halfDecade": "half_decade",
                  "pandemicPeriod": "pandemic_period"}
    rename_co2 = rename_ev.copy()

    ev_y  = ev_df.rename(columns=rename_ev)[["year", "half_decade", "pandemic_period"]].drop_duplicates("year")
    co2_y = co2_df.rename(columns=rename_co2)[["year", "half_decade", "pandemic_period"]].drop_duplicates("year")
    all_y = (
        pd.concat([ev_y, co2_y], ignore_index=True)
        .drop_duplicates("year")
        .sort_values("year")
    )

    sql = """
        INSERT INTO Year (year, half_decade, pandemic_period)
        VALUES (%s, %s, %s)
        ON CONFLICT (year) DO NOTHING;
    """
    for _, row in all_y.iterrows():
        cur.execute(sql, (int(row["year"]), row["half_decade"], row["pandemic_period"]))

    cur.execute("SELECT year_id, year FROM Year;")
    mapping = {yr: yid for yid, yr in cur.fetchall()}
    print(f"    → {len(mapping)} years loaded.")
    return mapping


def load_vehicle_types(cur, ev_df: pd.DataFrame) -> dict:
    """Insert distinct vehicle types and return {type_name: vehicle_type_id}."""
    print("  Loading VehicleType table...")
    types = ev_df["vehicleType"].dropna().unique()
    sql = """
        INSERT INTO VehicleType (type_name)
        VALUES (%s)
        ON CONFLICT (type_name) DO NOTHING;
    """
    for t in types:
        cur.execute(sql, (t,))
    cur.execute("SELECT vehicle_type_id, type_name FROM VehicleType;")
    mapping = {name: vid for vid, name in cur.fetchall()}
    print(f"    → {len(mapping)} vehicle types loaded.")
    return mapping


def load_powertrains(cur, ev_df: pd.DataFrame) -> dict:
    """Insert distinct powertrains and return {powertrain_name: powertrain_id}."""
    print("  Loading Powertrain table...")
    pts = ev_df["powertrain"].dropna().unique()
    sql = """
        INSERT INTO Powertrain (powertrain_name)
        VALUES (%s)
        ON CONFLICT (powertrain_name) DO NOTHING;
    """
    for p in pts:
        cur.execute(sql, (p,))
    cur.execute("SELECT powertrain_id, powertrain_name FROM Powertrain;")
    mapping = {name: pid for pid, name in cur.fetchall()}
    print(f"    → {len(mapping)} powertrains loaded.")
    return mapping


# ---------------------------------------------------------------------------
# Data table loaders
# ---------------------------------------------------------------------------

def load_ev_sales(cur, ev_df, iso_map, year_map, vt_map, pt_map):
    """Populate EVSales table."""
    print("  Loading EVSales table...")
    sql = """
        INSERT INTO EVSales
            (country_id, year_id, vehicle_type_id, powertrain_id,
             ev_sales, ev_sales_share, ev_stock, ev_stock_share, ev_electricity_demand)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (country_id, year_id, vehicle_type_id, powertrain_id) DO UPDATE SET
            ev_sales              = EXCLUDED.ev_sales,
            ev_sales_share        = EXCLUDED.ev_sales_share,
            ev_stock              = EXCLUDED.ev_stock,
            ev_stock_share        = EXCLUDED.ev_stock_share,
            ev_electricity_demand = EXCLUDED.ev_electricity_demand;
    """
    rows, skipped = [], 0
    for _, row in ev_df.iterrows():
        cid = iso_map.get(row["isoCode"])
        yid = year_map.get(int(row["year"]))
        vid = vt_map.get(row["vehicleType"])
        pid = pt_map.get(row["powertrain"])
        if None in (cid, yid, vid, pid):
            skipped += 1
            continue
        rows.append((
            cid, yid, vid, pid,
            _nan_to_none(row.get("evSales")),
            _nan_to_none(row.get("evSalesShare")),
            _nan_to_none(row.get("evStock")),
            _nan_to_none(row.get("evStockShare")),
            _nan_to_none(row.get("evElectricityDemand")),
        ))
    psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    print(f"    → {len(rows)} rows inserted (skipped: {skipped}).")


def load_ev_infrastructure(cur, infra_df, iso_map, year_map):
    """Populate EVInfrastructure table."""
    print("  Loading EVInfrastructure table...")
    sql = """
        INSERT INTO EVInfrastructure
            (country_id, year_id,
             ev_charging_points, fast_charging_points, slow_charging_points, charging_points_per_ev)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (country_id, year_id) DO UPDATE SET
            ev_charging_points     = EXCLUDED.ev_charging_points,
            fast_charging_points   = EXCLUDED.fast_charging_points,
            slow_charging_points   = EXCLUDED.slow_charging_points,
            charging_points_per_ev = EXCLUDED.charging_points_per_ev;
    """
    rows, skipped = [], 0
    for _, row in infra_df.iterrows():
        cid = iso_map.get(row["isoCode"])
        yid = year_map.get(int(row["year"]))
        if None in (cid, yid):
            skipped += 1
            continue
        rows.append((
            cid, yid,
            _nan_to_none(row.get("evChargingPoints")),
            _nan_to_none(row.get("fastChargingPoints")),
            _nan_to_none(row.get("slowChargingPoints")),
            _nan_to_none(row.get("chargingPointsPerEv")),
        ))
    psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    print(f"    → {len(rows)} rows inserted (skipped: {skipped}).")


def load_energy_data(cur, energy_df, iso_map, year_map):
    """Populate EnergyData table."""
    print("  Loading EnergyData table...")
    sql = """
        INSERT INTO CountryEnergy (
            country_id, year_id,
            energy_consumption, electricity_generation, electricity_demand,
            fossil_electricity_generation, coal_electricity_generation,
            oil_electricity_generation, gas_electricity_generation,
            renewable_electricity_generation, low_carbon_electricity_generation,
            wind_electricity_generation, hydro_electricity_generation,
            nuclear_electricity_generation, other_electricity_generation,
            solar_electricity_generation, net_electricity_imports
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (country_id, year_id) DO UPDATE SET
            energy_consumption                = EXCLUDED.energy_consumption,
            electricity_generation            = EXCLUDED.electricity_generation,
            electricity_demand                = EXCLUDED.electricity_demand,
            fossil_electricity_generation     = EXCLUDED.fossil_electricity_generation,
            coal_electricity_generation       = EXCLUDED.coal_electricity_generation,
            oil_electricity_generation        = EXCLUDED.oil_electricity_generation,
            gas_electricity_generation        = EXCLUDED.gas_electricity_generation,
            renewable_electricity_generation  = EXCLUDED.renewable_electricity_generation,
            low_carbon_electricity_generation = EXCLUDED.low_carbon_electricity_generation,
            wind_electricity_generation       = EXCLUDED.wind_electricity_generation,
            hydro_electricity_generation      = EXCLUDED.hydro_electricity_generation,
            nuclear_electricity_generation    = EXCLUDED.nuclear_electricity_generation,
            other_electricity_generation      = EXCLUDED.other_electricity_generation,
            solar_electricity_generation      = EXCLUDED.solar_electricity_generation,
            net_electricity_imports           = EXCLUDED.net_electricity_imports;
    """
    metric_cols = [
        "energyConsumption", "electricityGeneration", "electricityDemand",
        "fossilElectricityGeneration", "coalElectricityGeneration",
        "oilElectricityGeneration", "gasElectricityGeneration",
        "renewableElectricityGeneration", "lowCarbonElectricityGeneration",
        "windElectricityGeneration", "hydroElectricityGeneration",
        "nuclearElectricityGeneration", "otherElectricityGeneration",
        "solarElectricityGeneration", "netElectricityImports",
    ]
    rows, skipped = [], 0
    for _, row in energy_df.iterrows():
        cid = iso_map.get(row["isoCode"])
        yid = year_map.get(int(row["year"]))
        if None in (cid, yid):
            skipped += 1
            continue
        metrics = tuple(_nan_to_none(row.get(c)) for c in metric_cols)
        rows.append((cid, yid) + metrics)
    psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    print(f"    → {len(rows)} rows inserted (skipped: {skipped}).")


def load_macroeconomic_data(cur, co2_df, iso_map, year_map):
    """Populate MacroeconomicData table."""
    print("  Loading MacroeconomicData table...")
    sql = """
        INSERT INTO CountryMacroeconomics (
            country_id, year_id,
            population, gdp,
            co2_emissions, co2_per_capita, co2_per_gdp,
            co2_emissions_oil, co2_emissions_oil_per_capita,
            co2_emissions_coal, co2_emissions_coal_per_capita,
            co2_per_unit_energy
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (country_id, year_id) DO UPDATE SET
            population                    = EXCLUDED.population,
            gdp                           = EXCLUDED.gdp,
            co2_emissions                 = EXCLUDED.co2_emissions,
            co2_per_capita                = EXCLUDED.co2_per_capita,
            co2_per_gdp                   = EXCLUDED.co2_per_gdp,
            co2_emissions_oil             = EXCLUDED.co2_emissions_oil,
            co2_emissions_oil_per_capita  = EXCLUDED.co2_emissions_oil_per_capita,
            co2_emissions_coal            = EXCLUDED.co2_emissions_coal,
            co2_emissions_coal_per_capita = EXCLUDED.co2_emissions_coal_per_capita,
            co2_per_unit_energy           = EXCLUDED.co2_per_unit_energy;
    """
    metric_cols = [
        "population", "GDP",
        "co2Emissions", "co2PerCapita", "co2PerGDP",
        "co2EmissionsOil", "co2EmissionsOilPerCapita",
        "co2EmissionsCoal", "co2EmissionsCoalPerCapita",
        "co2EmissionsPerUnitEnergy",
    ]
    rows, skipped = [], 0
    for _, row in co2_df.iterrows():
        cid = iso_map.get(row["isoCode"])
        yid = year_map.get(int(row["year"]))
        if None in (cid, yid):
            skipped += 1
            continue
        metrics = tuple(_nan_to_none(row.get(c)) for c in metric_cols)
        rows.append((cid, yid) + metrics)
    psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    print(f"    → {len(rows)} rows inserted (skipped: {skipped}).")


# ---------------------------------------------------------------------------
# Data reading
# ---------------------------------------------------------------------------

def read_clean_datasets(base_path: Path):
    """
    Read the pre-cleaned CSVs from clean_datasets/.
    These files were produced by the main ETL pipeline (src/etl.py).
    """
    clean_dir = base_path / "clean_datasets"

    print("Reading clean_iea_ev_sales.csv ...")
    ev_df = pd.read_csv(clean_dir / "clean_iea_ev_sales.csv", low_memory=False)
    print(f"  → {len(ev_df)} rows")

    print("Reading clean_iea_ev_infrastructure.csv ...")
    infra_df = pd.read_csv(clean_dir / "clean_iea_ev_infrastructure.csv", low_memory=False)
    print(f"  → {len(infra_df)} rows")

    print("Reading clean_owid_co2.csv ...")
    co2_df = pd.read_csv(clean_dir / "clean_owid_co2.csv", low_memory=False)
    print(f"  → {len(co2_df)} rows")

    print("Reading clean_owid_energy.csv ...")
    energy_df = pd.read_csv(clean_dir / "clean_owid_energy.csv", low_memory=False)
    print(f"  → {len(energy_df)} rows")

    return ev_df, infra_df, co2_df, energy_df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_populate(host, port, dbname, user, password):
    base_path = Path(__file__).resolve().parents[2]

    print("\n=== Reading Clean Datasets ===")
    ev_df, infra_df, co2_df, energy_df = read_clean_datasets(base_path)

    print(f"\n=== Connecting to {user}@{host}:{port}/{dbname} ===")
    conn = get_connection(host, port, dbname, user, password)

    try:
        with conn:
            with conn.cursor() as cur:
                print("\n--- Entity / Lookup Tables ---")
                iso_map  = load_countries(cur, ev_df, co2_df)
                year_map = load_years(cur, ev_df, co2_df)
                vt_map   = load_vehicle_types(cur, ev_df)
                pt_map   = load_powertrains(cur, ev_df)

                print("\n--- Data Tables ---")
                load_ev_sales(cur, ev_df, iso_map, year_map, vt_map, pt_map)
                load_ev_infrastructure(cur, infra_df, iso_map, year_map)
                load_energy_data(cur, energy_df, iso_map, year_map)
                load_macroeconomic_data(cur, co2_df, iso_map, year_map)

        print("\n=== Population completed successfully! ===\n")

    except Exception as exc:
        print(f"\nERROR: {exc}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Populate the GREEN_MOBILITY_RDBMS PostgreSQL database."
    )
    parser.add_argument("--host",     default="localhost")
    parser.add_argument("--port",     type=int, default=5432)
    parser.add_argument("--dbname",   default="green_mobility_rdbms")
    parser.add_argument("--user",     default="postgres")
    parser.add_argument("--password", default="postgres")
    args = parser.parse_args()

    run_populate(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=args.password,
    )
