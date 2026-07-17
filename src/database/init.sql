DROP DATABASE IF EXISTS GREEN_MOBILITY;
CREATE DATABASE GREEN_MOBILITY;

-- ======================================================
-- DIMENSION TABLES
-- ======================================================

CREATE TABLE CountryDim (
    keyC SERIAL PRIMARY KEY,
    country VARCHAR(50) NOT NULL,
    isoCode CHAR(3) NOT NULL UNIQUE,
    continent VARCHAR(50),
    continentCode CHAR(2)
);

CREATE TABLE YearDim (
    keyY SERIAL PRIMARY KEY,
    year INT NOT NULL UNIQUE,
    halfDecade VARCHAR(15) NOT NULL,
    pandemicPeriod VARCHAR(20) NOT NULL
);

CREATE TABLE VehicleTypeDim (
    keyV SERIAL PRIMARY KEY,
    vehicleType VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE PowertrainDim (
    keyP SERIAL PRIMARY KEY,
    powertrain VARCHAR(50) NOT NULL UNIQUE
);

-- ======================================================
-- FACT TABLE: EV MARKET
-- ======================================================

CREATE TABLE EVMarket (

    keyC INT NOT NULL,
    keyY INT NOT NULL,
    keyV INT NOT NULL,
    keyP INT NOT NULL,

    evSales NUMERIC(15,1),
    evSalesShare NUMERIC(21, 20),
    evStock NUMERIC(15,1),
    evStockShare NUMERIC(21, 20),
    evElectricityDemand NUMERIC(10,2),

    PRIMARY KEY (keyC, keyY, keyV, keyP),

    FOREIGN KEY (keyC) REFERENCES CountryDim(keyC),
    FOREIGN KEY (keyY) REFERENCES YearDim(keyY),
    FOREIGN KEY (keyV) REFERENCES VehicleTypeDim(keyV),
    FOREIGN KEY (keyP) REFERENCES PowertrainDim(keyP)
);

-- ======================================================
-- FACT TABLE: EV INFRASTRUCTURE
-- ======================================================

CREATE TABLE EVInfrastructure (

    keyC INT NOT NULL,
    keyY INT NOT NULL,

    evChargingPoints NUMERIC(10,1),
    fastChargingPoints NUMERIC(10,1),
    slowChargingPoints NUMERIC(10,1),
    chargingPointsPerEv NUMERIC(10,4),

    PRIMARY KEY (keyC, keyY),

    FOREIGN KEY (keyC) REFERENCES CountryDim(keyC),
    FOREIGN KEY (keyY) REFERENCES YearDim(keyY)
);

-- ======================================================
-- FACT TABLE: COUNTRY ENERGY
-- ======================================================

CREATE TABLE CountryEnergy (

    keyC INT NOT NULL,
    keyY INT NOT NULL,

    energyConsumption NUMERIC(18,4),
    electricityGeneration NUMERIC(18,3),
    electricityDemand NUMERIC(18,3),

    fossilElectricityGeneration NUMERIC(18,4),
    coalElectricityGeneration NUMERIC(18,4),
    oilElectricityGeneration NUMERIC(18,4),
    gasElectricityGeneration NUMERIC(18,4),

    renewableElectricityGeneration NUMERIC(18,4),
    lowCarbonElectricityGeneration NUMERIC(18,4),

    windElectricityGeneration NUMERIC(18,4),
    hydroElectricityGeneration NUMERIC(18,4),
    nuclearElectricityGeneration NUMERIC(18,4),
    otherElectricityGeneration NUMERIC(18,4),
    solarElectricityGeneration NUMERIC(18,4),

    netElectricityImports NUMERIC(18,4),

    PRIMARY KEY (keyC, keyY),

    FOREIGN KEY (keyC) REFERENCES CountryDim(keyC),
    FOREIGN KEY (keyY) REFERENCES YearDim(keyY)
);

-- ======================================================
-- FACT TABLE: COUNTRY MACROECONOMICS
-- ======================================================

CREATE TABLE CountryMacroeconomics (

    keyC INT NOT NULL,
    keyY INT NOT NULL,

    population INT,
    GDP NUMERIC(18,2),

    co2Emissions NUMERIC(18,4),
    co2PerCapita NUMERIC(18,4),
    co2PerGDP NUMERIC(18,4),

    co2EmissionsOil NUMERIC(18,2),
    co2EmissionsOilPerCapita NUMERIC(18,4),

    co2EmissionsCoal NUMERIC(18,2),
    co2EmissionsCoalPerCapita NUMERIC(18,4),

    co2EmissionsPerUnitEnergy NUMERIC(18,4),

    PRIMARY KEY (keyC, keyY),

    FOREIGN KEY (keyC) REFERENCES CountryDim(keyC),
    FOREIGN KEY (keyY) REFERENCES YearDim(keyY)
);
