import psycopg2
import psycopg2.extras
import pandas as pd
import numpy as np
from typing import Optional


# Connection

def get_connection(
    host: str = "localhost",
    port: int = 5432,
    dbname: str = "green_mobility",
    user: str = "postgres",
    password: str = "postgres",
) -> psycopg2.extensions.connection:
    """
    Opens and returns a psycopg2 connection to the GREEN_MOBILITY database.
    """
    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )
    return conn


def nan_to_none(value):
    """Converts NaN / Inf values to None for PostgreSQL NULL compatibility."""
    if value is None:
        return None
    try:
        if np.isnan(value) or np.isinf(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


# Dimension loaders

def load_country_dim(cur, ev_df: pd.DataFrame, co2_df: pd.DataFrame) -> dict:
    """
    Populates CountryDim and returns a dictionary mapping isoCode to keyC.
    """
    print("  Loading CountryDim...")

    ev_countries = ev_df[["country", "isoCode", "continent", "continentCode"]].drop_duplicates(subset=["isoCode"])
    co2_countries = co2_df[["country", "isoCode", "continent", "continentCode"]].drop_duplicates(subset=["isoCode"])
    all_countries = (
        pd.concat([ev_countries, co2_countries], ignore_index=True)
        .drop_duplicates(subset=["isoCode"])
        .dropna(subset=["isoCode"])
    )

    sql = """
        INSERT INTO CountryDim (country, isoCode, continent, continentCode)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (isoCode) DO NOTHING
        RETURNING keyC, isoCode;
    """

    iso_to_key: dict = {}

    for _, row in all_countries.iterrows():
        cur.execute(sql, (
            row["country"],
            row["isoCode"],
            nan_to_none(row.get("continent")),
            nan_to_none(row.get("continentCode")),
        ))

    cur.execute("SELECT keyC, isoCode FROM CountryDim;")
    for key_c, iso in cur.fetchall():
        iso_to_key[iso] = key_c

    print(f"    -> {len(iso_to_key)} countries in CountryDim.")
    return iso_to_key


def load_year_dim(cur, ev_df: pd.DataFrame, co2_df: pd.DataFrame) -> dict:
    """
    Populates YearDim and returns a dictionary mapping year to keyY.
    """
    print("  Loading YearDim...")

    ev_years = ev_df[["year", "halfDecade", "pandemicPeriod"]].drop_duplicates(subset=["year"])
    co2_years = co2_df[["year", "halfDecade", "pandemicPeriod"]].drop_duplicates(subset=["year"])
    all_years = (
        pd.concat([ev_years, co2_years], ignore_index=True)
        .drop_duplicates(subset=["year"])
        .sort_values("year")
    )

    sql = """
        INSERT INTO YearDim (year, halfDecade, pandemicPeriod)
        VALUES (%s, %s, %s)
        ON CONFLICT (year) DO NOTHING;
    """

    for _, row in all_years.iterrows():
        cur.execute(sql, (int(row["year"]), row["halfDecade"], row["pandemicPeriod"]))

    cur.execute("SELECT keyY, year FROM YearDim;")
    year_to_key = {year: key_y for key_y, year in cur.fetchall()}

    print(f"    -> {len(year_to_key)} years in YearDim.")
    return year_to_key


def load_vehicle_type_dim(cur, ev_df: pd.DataFrame) -> dict:
    """
    Populates VehicleTypeDim and returns a dictionary mapping vehicleType to keyV.
    """
    print("  Loading VehicleTypeDim...")

    vehicle_types = ev_df["vehicleType"].dropna().unique()

    sql = """
        INSERT INTO VehicleTypeDim (vehicleType)
        VALUES (%s)
        ON CONFLICT (vehicleType) DO NOTHING;
    """

    for vt in vehicle_types:
        cur.execute(sql, (vt,))

    cur.execute("SELECT keyV, vehicleType FROM VehicleTypeDim;")
    vt_to_key = {vt: key_v for key_v, vt in cur.fetchall()}

    print(f"    -> {len(vt_to_key)} vehicle types in VehicleTypeDim.")
    return vt_to_key


def load_powertrain_dim(cur, ev_df: pd.DataFrame) -> dict:
    """
    Populates PowertrainDim and returns a dictionary mapping powertrain to keyP.
    """
    print("  Loading PowertrainDim...")

    powertrains = ev_df["powertrain"].dropna().unique()

    sql = """
        INSERT INTO PowertrainDim (powertrain)
        VALUES (%s)
        ON CONFLICT (powertrain) DO NOTHING;
    """

    for pt in powertrains:
        cur.execute(sql, (pt,))

    cur.execute("SELECT keyP, powertrain FROM PowertrainDim;")
    pt_to_key = {pt: key_p for key_p, pt in cur.fetchall()}

    print(f"    -> {len(pt_to_key)} powertrains in PowertrainDim.")
    return pt_to_key


# Fact table loaders

def load_ev_market(
    cur,
    ev_df: pd.DataFrame,
    iso_to_key: dict,
    year_to_key: dict,
    vt_to_key: dict,
    pt_to_key: dict,
) -> None:
    """
    Populates the EVMarket fact table.
    """
    print("  Loading EVMarket...")

    sql = """
        INSERT INTO EVMarket
            (keyC, keyY, keyV, keyP, evSales, evSalesShare, evStock, evStockShare, evElectricityDemand)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (keyC, keyY, keyV, keyP) DO UPDATE SET
            evSales              = EXCLUDED.evSales,
            evSalesShare         = EXCLUDED.evSalesShare,
            evStock              = EXCLUDED.evStock,
            evStockShare         = EXCLUDED.evStockShare,
            evElectricityDemand  = EXCLUDED.evElectricityDemand;
    """

    rows = []
    skipped = 0

    for _, row in ev_df.iterrows():
        key_c = iso_to_key.get(row["isoCode"])
        key_y = year_to_key.get(int(row["year"]))
        key_v = vt_to_key.get(row["vehicleType"])
        key_p = pt_to_key.get(row["powertrain"])

        if None in (key_c, key_y, key_v, key_p):
            skipped += 1
            continue

        rows.append((
            key_c, key_y, key_v, key_p,
            nan_to_none(row.get("evSales")),
            nan_to_none(row.get("evSalesShare")),
            nan_to_none(row.get("evStock")),
            nan_to_none(row.get("evStockShare")),
            nan_to_none(row.get("evElectricityDemand")),
        ))

    psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    print(f"    -> {len(rows)} rows inserted into EVMarket (skipped: {skipped}).")


def load_ev_infrastructure(
    cur,
    infra_df: pd.DataFrame,
    iso_to_key: dict,
    year_to_key: dict,
) -> None:
    """
    Populates the EVInfrastructure fact table.
    """
    print("  Loading EVInfrastructure...")

    sql = """
        INSERT INTO EVInfrastructure
            (keyC, keyY, evChargingPoints, fastChargingPoints, slowChargingPoints, chargingPointsPerEv)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (keyC, keyY) DO UPDATE SET
            evChargingPoints    = EXCLUDED.evChargingPoints,
            fastChargingPoints  = EXCLUDED.fastChargingPoints,
            slowChargingPoints  = EXCLUDED.slowChargingPoints,
            chargingPointsPerEv = EXCLUDED.chargingPointsPerEv;
    """

    rows = []
    skipped = 0

    for _, row in infra_df.iterrows():
        key_c = iso_to_key.get(row["isoCode"])
        key_y = year_to_key.get(int(row["year"]))

        if None in (key_c, key_y):
            skipped += 1
            continue

        rows.append((
            key_c, key_y,
            nan_to_none(row.get("evChargingPoints")),
            nan_to_none(row.get("fastChargingPoints")),
            nan_to_none(row.get("slowChargingPoints")),
            nan_to_none(row.get("chargingPointsPerEv")),
        ))

    psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    print(f"    -> {len(rows)} rows inserted into EVInfrastructure (skipped: {skipped}).")


def load_country_energy(
    cur,
    energy_df: pd.DataFrame,
    iso_to_key: dict,
    year_to_key: dict,
) -> None:
    """
    Populates the CountryEnergy fact table.
    """
    print("  Loading CountryEnergy...")

    sql = """
        INSERT INTO CountryEnergy (
            keyC, keyY,
            energyConsumption, electricityGeneration, electricityDemand,
            fossilElectricityGeneration, coalElectricityGeneration,
            oilElectricityGeneration, gasElectricityGeneration,
            renewableElectricityGeneration, lowCarbonElectricityGeneration,
            windElectricityGeneration, hydroElectricityGeneration,
            nuclearElectricityGeneration, otherElectricityGeneration,
            solarElectricityGeneration, netElectricityImports
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (keyC, keyY) DO UPDATE SET
            energyConsumption              = EXCLUDED.energyConsumption,
            electricityGeneration          = EXCLUDED.electricityGeneration,
            electricityDemand              = EXCLUDED.electricityDemand,
            fossilElectricityGeneration    = EXCLUDED.fossilElectricityGeneration,
            coalElectricityGeneration      = EXCLUDED.coalElectricityGeneration,
            oilElectricityGeneration       = EXCLUDED.oilElectricityGeneration,
            gasElectricityGeneration       = EXCLUDED.gasElectricityGeneration,
            renewableElectricityGeneration = EXCLUDED.renewableElectricityGeneration,
            lowCarbonElectricityGeneration = EXCLUDED.lowCarbonElectricityGeneration,
            windElectricityGeneration      = EXCLUDED.windElectricityGeneration,
            hydroElectricityGeneration     = EXCLUDED.hydroElectricityGeneration,
            nuclearElectricityGeneration   = EXCLUDED.nuclearElectricityGeneration,
            otherElectricityGeneration     = EXCLUDED.otherElectricityGeneration,
            solarElectricityGeneration     = EXCLUDED.solarElectricityGeneration,
            netElectricityImports          = EXCLUDED.netElectricityImports;
    """

    energy_metric_cols = [
        "energyConsumption", "electricityGeneration", "electricityDemand",
        "fossilElectricityGeneration", "coalElectricityGeneration",
        "oilElectricityGeneration", "gasElectricityGeneration",
        "renewableElectricityGeneration", "lowCarbonElectricityGeneration",
        "windElectricityGeneration", "hydroElectricityGeneration",
        "nuclearElectricityGeneration", "otherElectricityGeneration",
        "solarElectricityGeneration", "netElectricityImports",
    ]

    rows = []
    skipped = 0

    for _, row in energy_df.iterrows():
        key_c = iso_to_key.get(row["isoCode"])
        key_y = year_to_key.get(int(row["year"]))

        if None in (key_c, key_y):
            skipped += 1
            continue

        metric_values = tuple(nan_to_none(row.get(col)) for col in energy_metric_cols)
        rows.append((key_c, key_y) + metric_values)

    psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    print(f"    -> {len(rows)} rows inserted into CountryEnergy (skipped: {skipped}).")


def load_country_macroeconomics(
    cur,
    co2_df: pd.DataFrame,
    iso_to_key: dict,
    year_to_key: dict,
) -> None:
    """
    Populates the CountryMacroeconomics fact table.
    """
    print("  Loading CountryMacroeconomics...")

    sql = """
        INSERT INTO CountryMacroeconomics (
            keyC, keyY,
            population, GDP,
            co2Emissions, co2PerCapita, co2PerGDP,
            co2EmissionsOil, co2EmissionsOilPerCapita,
            co2EmissionsCoal, co2EmissionsCoalPerCapita,
            co2EmissionsPerUnitEnergy
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (keyC, keyY) DO UPDATE SET
            population                = EXCLUDED.population,
            GDP                       = EXCLUDED.GDP,
            co2Emissions              = EXCLUDED.co2Emissions,
            co2PerCapita              = EXCLUDED.co2PerCapita,
            co2PerGDP                 = EXCLUDED.co2PerGDP,
            co2EmissionsOil           = EXCLUDED.co2EmissionsOil,
            co2EmissionsOilPerCapita  = EXCLUDED.co2EmissionsOilPerCapita,
            co2EmissionsCoal          = EXCLUDED.co2EmissionsCoal,
            co2EmissionsCoalPerCapita = EXCLUDED.co2EmissionsCoalPerCapita,
            co2EmissionsPerUnitEnergy = EXCLUDED.co2EmissionsPerUnitEnergy;
    """

    macro_metric_cols = [
        "population", "GDP",
        "co2Emissions", "co2PerCapita", "co2PerGDP",
        "co2EmissionsOil", "co2EmissionsOilPerCapita",
        "co2EmissionsCoal", "co2EmissionsCoalPerCapita",
        "co2EmissionsPerUnitEnergy",
    ]

    rows = []
    skipped = 0

    for _, row in co2_df.iterrows():
        key_c = iso_to_key.get(row["isoCode"])
        key_y = year_to_key.get(int(row["year"]))

        if None in (key_c, key_y):
            skipped += 1
            continue

        metric_values = tuple(nan_to_none(row.get(col)) for col in macro_metric_cols)
        rows.append((key_c, key_y) + metric_values)

    psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    print(f"    -> {len(rows)} rows inserted into CountryMacroeconomics (skipped: {skipped}).")


# Main function

def insert_to_db(
    ev_df: pd.DataFrame,
    infra_df: pd.DataFrame,
    co2_df: pd.DataFrame,
    energy_df: pd.DataFrame,
    host: str = "localhost",
    port: int = 5432,
    dbname: str = "green_mobility",
    user: str = "postgres",
    password: str = "postgres",
) -> None:
    """
    Inserts transformed ETL data into the GREEN_MOBILITY PostgreSQL database.
    """
    print("\n=== Inserting Data into PostgreSQL Database ===")
    print(f"  Connecting to {user}@{host}:{port}/{dbname} ...")

    conn = get_connection(host=host, port=port, dbname=dbname, user=user, password=password)

    try:
        with conn:
            with conn.cursor() as cur:

                # Dimension tables
                iso_to_key  = load_country_dim(cur, ev_df, co2_df)
                year_to_key = load_year_dim(cur, ev_df, co2_df)
                vt_to_key   = load_vehicle_type_dim(cur, ev_df)
                pt_to_key   = load_powertrain_dim(cur, ev_df)

                # Fact tables
                load_ev_market(cur, ev_df, iso_to_key, year_to_key, vt_to_key, pt_to_key)
                load_ev_infrastructure(cur, infra_df, iso_to_key, year_to_key)
                load_country_energy(cur, energy_df, iso_to_key, year_to_key)
                load_country_macroeconomics(cur, co2_df, iso_to_key, year_to_key)

        print("=== Database insertion completed successfully! ===\n")

    except Exception as exc:
        print(f"ERROR: Database insertion failed. Transaction rolled back.\n  Reason: {exc}")
        raise

    finally:
        conn.close()
