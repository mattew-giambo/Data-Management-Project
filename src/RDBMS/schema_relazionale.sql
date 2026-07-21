-- ======================================================
-- GREEN_MOBILITY_RDBMS — Relational Schema (3NF)
-- ======================================================
-- This schema represents the RDBMS (relational) approach to the
-- same Green Mobility domain modelled as a Star Schema in the DW.
--
-- Key differences from the DW (src/DW/init.sql):
--   - Fully normalized (3NF): no redundant attributes in entity tables
--   - Surrogate primary keys (SERIAL) on every entity table
--   - No composite primary keys on fact/association tables
--   - Explicit UNIQUE constraints reflect real-world business keys
--   - Designed for OLTP-style access (individual inserts, updates, deletes)
--   - Analytical queries require more JOIN hops than the DW star schema
-- ======================================================

DROP DATABASE IF EXISTS GREEN_MOBILITY_RDBMS;
CREATE DATABASE GREEN_MOBILITY_RDBMS;

-- ======================================================
-- ENTITY TABLE: Country
-- Stores geographic information about each country.
-- In the DW this is CountryDim — here it is a standalone entity.
-- ======================================================

CREATE TABLE Country (
    country_id      SERIAL PRIMARY KEY,
    iso_code        CHAR(3)      NOT NULL UNIQUE,  -- ISO 3166-1 alpha-3
    country_name    VARCHAR(100) NOT NULL,
    continent       VARCHAR(50),
    continent_code  CHAR(2)
);

-- ======================================================
-- ENTITY TABLE: Year
-- Stores year-level temporal attributes.
-- Equivalent to YearDim in the DW.
-- ======================================================

CREATE TABLE Year (
    year_id         SERIAL PRIMARY KEY,
    year            INT          NOT NULL UNIQUE,
    half_decade     VARCHAR(15)  NOT NULL,          -- e.g. "2010-2014"
    pandemic_period VARCHAR(20)  NOT NULL           -- "Pre-Pandemic" | "Pandemic" | "Post-Pandemic"
);

-- ======================================================
-- ENTITY TABLE: VehicleType
-- Stores distinct vehicle categories (Cars, Buses, Vans, Trucks…).
-- Equivalent to VehicleTypeDim in the DW.
-- ======================================================

CREATE TABLE VehicleType (
    vehicle_type_id SERIAL PRIMARY KEY,
    type_name       VARCHAR(50) NOT NULL UNIQUE
);

-- ======================================================
-- ENTITY TABLE: Powertrain
-- Stores distinct powertrain technologies (BEV, PHEV, FCEV…).
-- Equivalent to PowertrainDim in the DW.
-- ======================================================

CREATE TABLE Powertrain (
    powertrain_id   SERIAL PRIMARY KEY,
    powertrain_name VARCHAR(50) NOT NULL UNIQUE
);

-- ======================================================
-- ASSOCIATION TABLE: EVSales
-- Records annual EV sales, stock and electricity demand
-- broken down by country, year, vehicle type and powertrain.
--
-- DW equivalent: EVMarket fact table (composite PK: keyC+keyY+keyV+keyP).
-- RDBMS difference: surrogate PK + UNIQUE constraint on the natural key.
-- ======================================================

CREATE TABLE EVSales (
    ev_sale_id              SERIAL PRIMARY KEY,
    country_id              INT NOT NULL REFERENCES Country(country_id),
    year_id                 INT NOT NULL REFERENCES Year(year_id),
    vehicle_type_id         INT NOT NULL REFERENCES VehicleType(vehicle_type_id),
    powertrain_id           INT NOT NULL REFERENCES Powertrain(powertrain_id),

    ev_sales                INT,
    ev_sales_share          NUMERIC(10, 6),
    ev_stock                NUMERIC(15, 1),
    ev_stock_share          NUMERIC(10, 6),
    ev_electricity_demand   NUMERIC(10, 2),

    UNIQUE (country_id, year_id, vehicle_type_id, powertrain_id)
);

-- ======================================================
-- ASSOCIATION TABLE: EVInfrastructure
-- Records annual charging-point counts per country/year.
-- DW equivalent: EVInfrastructure fact table.
-- ======================================================

CREATE TABLE EVInfrastructure (
    infra_id                SERIAL PRIMARY KEY,
    country_id              INT NOT NULL REFERENCES Country(country_id),
    year_id                 INT NOT NULL REFERENCES Year(year_id),

    ev_charging_points      INT,
    fast_charging_points    INT,
    slow_charging_points    INT,
    charging_points_per_ev  NUMERIC(10, 4),

    UNIQUE (country_id, year_id)
);

-- ======================================================
-- ASSOCIATION TABLE: EnergyData
-- Records annual electricity generation/consumption per country/year.
-- DW equivalent: CountryEnergy fact table.
-- ======================================================

CREATE TABLE EnergyData (
    energy_id                           SERIAL PRIMARY KEY,
    country_id                          INT NOT NULL REFERENCES Country(country_id),
    year_id                             INT NOT NULL REFERENCES Year(year_id),

    energy_consumption                  NUMERIC(18, 4),
    electricity_generation              NUMERIC(18, 4),
    electricity_demand                  NUMERIC(18, 4),

    fossil_electricity_generation       NUMERIC(18, 4),
    coal_electricity_generation         NUMERIC(18, 4),
    oil_electricity_generation          NUMERIC(18, 4),
    gas_electricity_generation          NUMERIC(18, 4),

    renewable_electricity_generation    NUMERIC(18, 4),
    low_carbon_electricity_generation   NUMERIC(18, 4),

    wind_electricity_generation         NUMERIC(18, 4),
    hydro_electricity_generation        NUMERIC(18, 4),
    nuclear_electricity_generation      NUMERIC(18, 4),
    other_electricity_generation        NUMERIC(18, 4),
    solar_electricity_generation        NUMERIC(18, 4),

    net_electricity_imports             NUMERIC(18, 4),

    UNIQUE (country_id, year_id)
);

-- ======================================================
-- ASSOCIATION TABLE: MacroeconomicData
-- Records annual population, GDP and CO₂ metrics per country/year.
-- DW equivalent: CountryMacroeconomics fact table.
-- ======================================================

CREATE TABLE MacroeconomicData (
    macro_id                        SERIAL PRIMARY KEY,
    country_id                      INT NOT NULL REFERENCES Country(country_id),
    year_id                         INT NOT NULL REFERENCES Year(year_id),

    population                      BIGINT,
    gdp                             NUMERIC(18, 2),

    co2_emissions                   NUMERIC(18, 4),
    co2_per_capita                  NUMERIC(18, 4),
    co2_per_gdp                     NUMERIC(18, 4),

    co2_emissions_oil               NUMERIC(18, 4),
    co2_emissions_oil_per_capita    NUMERIC(18, 4),

    co2_emissions_coal              NUMERIC(18, 4),
    co2_emissions_coal_per_capita   NUMERIC(18, 4),

    co2_per_unit_energy             NUMERIC(18, 4),

    UNIQUE (country_id, year_id)
);

-- ======================================================
-- INDEXES
-- Indexes on foreign keys and frequently filtered columns
-- to speed up the multi-join queries that the relational
-- approach requires (no pre-aggregated materialized structures).
-- ======================================================

CREATE INDEX idx_evsales_country   ON EVSales (country_id);
CREATE INDEX idx_evsales_year      ON EVSales (year_id);
CREATE INDEX idx_evsales_type      ON EVSales (vehicle_type_id);
CREATE INDEX idx_evsales_powertrain ON EVSales (powertrain_id);

CREATE INDEX idx_infra_country     ON EVInfrastructure (country_id);
CREATE INDEX idx_infra_year        ON EVInfrastructure (year_id);

CREATE INDEX idx_energy_country    ON EnergyData (country_id);
CREATE INDEX idx_energy_year       ON EnergyData (year_id);

CREATE INDEX idx_macro_country     ON MacroeconomicData (country_id);
CREATE INDEX idx_macro_year        ON MacroeconomicData (year_id);
