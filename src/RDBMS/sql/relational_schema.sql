DROP DATABASE IF EXISTS GREEN_MOBILITY_RDBMS;
CREATE DATABASE GREEN_MOBILITY_RDBMS;

-- TABLE: Country

CREATE TABLE Country (
    country_id SERIAL PRIMARY KEY,
    iso_code CHAR(3) NOT NULL UNIQUE,
    country_name VARCHAR(100) NOT NULL,
    continent VARCHAR(50),
    continent_code CHAR(2)
);

-- TABLE: Year

CREATE TABLE Year (
    year_id SERIAL PRIMARY KEY,
    year INT NOT NULL UNIQUE,
    half_decade VARCHAR(15) NOT NULL,
    pandemic_period VARCHAR(20) NOT NULL
);

-- TABLE: VehicleType

CREATE TABLE VehicleType (
    vehicle_type_id SERIAL PRIMARY KEY,
    type_name VARCHAR(50) NOT NULL UNIQUE
);

-- TABLE: Powertrain

CREATE TABLE Powertrain (
    powertrain_id SERIAL PRIMARY KEY,
    powertrain_name VARCHAR(50) NOT NULL UNIQUE
);

-- ASSOCIATION TABLE: EVSales

CREATE TABLE EVSales (
    ev_sale_id SERIAL PRIMARY KEY,
    country_id INT NOT NULL,
    year_id INT NOT NULL,
    vehicle_type_id INT NOT NULL,
    powertrain_id INT NOT NULL,

    ev_sales INT,
    ev_sales_share NUMERIC(10, 6),
    ev_stock NUMERIC(15, 1),
    ev_stock_share NUMERIC(10, 6),
    ev_electricity_demand NUMERIC(10, 2),

    UNIQUE (country_id, year_id, vehicle_type_id, powertrain_id),
    FOREIGN KEY (country_id) REFERENCES Country(country_id),
    FOREIGN KEY (year_id) REFERENCES Year(year_id),
    FOREIGN KEY (vehicle_type_id) REFERENCES VehicleType(vehicle_type_id),
    FOREIGN KEY (powertrain_id) REFERENCES Powertrain(powertrain_id)
);

-- TABLE: EVInfrastructure

CREATE TABLE EVInfrastructure (
    infra_id SERIAL PRIMARY KEY,
    country_id INT NOT NULL,
    year_id INT NOT NULL,

    ev_charging_points INT,
    fast_charging_points INT,
    slow_charging_points INT,
    charging_points_per_ev NUMERIC(10, 4),

    UNIQUE (country_id, year_id),
    FOREIGN KEY (country_id) REFERENCES Country(country_id),
    FOREIGN KEY (year_id) REFERENCES Year(year_id),
);

-- TABLE: EnergyData

CREATE TABLE CountryEnergy (
    energy_id SERIAL PRIMARY KEY,
    country_id INT NOT NULL,
    year_id INT NOT NULL,

    energy_consumption NUMERIC(18, 4),
    electricity_generation NUMERIC(18, 4),
    electricity_demand NUMERIC(18, 4),

    fossil_electricity_generation NUMERIC(18, 4),
    coal_electricity_generation NUMERIC(18, 4),
    oil_electricity_generation NUMERIC(18, 4),
    gas_electricity_generation NUMERIC(18, 4),

    renewable_electricity_generation NUMERIC(18, 4),
    low_carbon_electricity_generation NUMERIC(18, 4),

    wind_electricity_generation NUMERIC(18, 4),
    hydro_electricity_generation NUMERIC(18, 4),
    nuclear_electricity_generation NUMERIC(18, 4),
    other_electricity_generation NUMERIC(18, 4),
    solar_electricity_generation NUMERIC(18, 4),

    net_electricity_imports NUMERIC(18, 4),

    UNIQUE (country_id, year_id),
    FOREIGN KEY (country_id) REFERENCES Country(country_id),
    FOREIGN KEY (year_id) REFERENCES Year(year_id)
);

-- TABLE: MacroeconomicData

CREATE TABLE CountryMacroeconomics (
    macro_id SERIAL PRIMARY KEY,
    country_id INT NOT NULL,
    year_id INT NOT NULL,

    population BIGINT,
    gdp NUMERIC(18, 2),

    co2_emissions NUMERIC(18, 4),
    co2_per_capita NUMERIC(18, 4),
    co2_per_gdp NUMERIC(18, 4),

    co2_emissions_oil NUMERIC(18, 4),
    co2_emissions_oil_per_capita NUMERIC(18, 4),

    co2_emissions_coal NUMERIC(18, 4),
    co2_emissions_coal_per_capita NUMERIC(18, 4),

    co2_per_unit_energy NUMERIC(18, 4),

    UNIQUE (country_id, year_id),
    FOREIGN KEY (country_id) REFERENCES Country(country_id),
    FOREIGN KEY (year_id) REFERENCES Year(year_id)
);
