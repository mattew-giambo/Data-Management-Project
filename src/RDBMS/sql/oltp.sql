-- Query 1: EV Sales by Continent and Year
-- 1: detailed (continent, year)
SELECT
    c.continent,
    y.year,
    COALESCE(SUM(s.ev_sales), 0) AS total_ev_sales
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
JOIN Year y ON s.year_id = y.year_id
GROUP BY c.continent, y.year

UNION ALL

-- 2: continent subtotal  (ROLLUP partial aggregate)
SELECT
    c.continent,
    NULL AS year,
    COALESCE(SUM(s.ev_sales), 0) AS total_ev_sales
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
GROUP BY c.continent

UNION ALL

-- 3: grand total  (ROLLUP grand aggregate)
SELECT
    NULL AS continent,
    NULL AS year,
    COALESCE(SUM(s.ev_sales), 0) AS total_ev_sales
FROM EVSales s

ORDER BY continent, year;


-- Query 2: Renewable Electricity vs CO2 Emissions
-- Question: Are countries with more renewable electricity producing less CO2?

SELECT
    c.country_name AS country,
    y.year,
    e.renewable_electricity_generation,
    m.co2_emissions
FROM CountryEnergy e
JOIN CountryMacroeconomics m
    ON  e.country_id = m.country_id
    AND e.year_id = m.year_id
JOIN Country c ON e.country_id = c.country_id
JOIN Year y ON e.year_id = y.year_id
ORDER BY y.year, e.renewable_electricity_generation DESC;


-- Query 3: Rich vs Poor Countries - EV Adoption by GDP class
-- Question: Do richer countries have higher EV adoption?

SELECT
    y.year,
    CASE
        WHEN m.gdp >= 1000000000000 THEN 'High GDP'
        WHEN m.gdp >= 100000000000 THEN 'Medium GDP'
        ELSE 'Low GDP'
    END AS gdp_class,
    AVG(s.ev_sales_share) AS avg_ev_share
FROM CountryMacroeconomics m
JOIN EVSales s
    ON m.country_id = s.country_id
    AND m.year_id = s.year_id
JOIN Year y ON m.year_id = y.year_id
GROUP BY y.year, gdp_class
ORDER BY y.year, gdp_class;


-- Query 4: Top Countries by EV Stock - Annual Ranking
-- Question: Which countries lead EV stock each year?

WITH stock_by_country AS (
    SELECT
        c.country_name AS country,
        y.year,
        SUM(s.ev_stock) AS total_stock
    FROM EVSales s
    JOIN Country c ON s.country_id = c.country_id
    JOIN Year y ON s.year_id = y.year_id
    GROUP BY c.country_name, y.year
)
SELECT
    a.year,
    a.country,
    a.total_stock AS stock,
    1 + COUNT(b.country) AS ranking
FROM stock_by_country a
LEFT JOIN stock_by_country b
    ON  a.year = b.year
    AND b.total_stock > a.total_stock
GROUP BY a.year, a.country, a.total_stock
ORDER BY a.year, ranking;

-- Query 5: Vehicle Type Analysis  [RDBMS equivalent of CUBE]
-- Question: Which vehicle type and powertrain dominate EV sales?

-- Combination 1: (vehicle_type, powertrain) - most detailed
SELECT
    vt.type_name AS vehicle_type,
    pt.powertrain_name AS powertrain,
    SUM(s.ev_sales) AS total_sales
FROM EVSales s
JOIN VehicleType vt ON s.vehicle_type_id = vt.vehicle_type_id
JOIN Powertrain pt ON s.powertrain_id = pt.powertrain_id
GROUP BY vt.type_name, pt.powertrain_name

UNION ALL

-- Combination 2: (vehicle_type, NULL) - subtotal by type
SELECT
    vt.type_name,
    NULL AS powertrain,
    SUM(s.ev_sales) AS total_sales
FROM EVSales s
JOIN VehicleType vt ON s.vehicle_type_id = vt.vehicle_type_id
GROUP BY vt.type_name

UNION ALL

-- Combination 3: (NULL, powertrain) - subtotal by powertrain
SELECT
    NULL AS vehicle_type,
    pt.powertrain_name,
    SUM(s.ev_sales) AS total_sales
FROM EVSales s
JOIN Powertrain pt ON s.powertrain_id = pt.powertrain_id
GROUP BY pt.powertrain_name

UNION ALL

-- Combination 4: (NULL, NULL) - grand total
SELECT
    NULL AS vehicle_type,
    NULL AS powertrain,
    SUM(s.ev_sales) AS total_sales
FROM EVSales s

ORDER BY vehicle_type, powertrain;


-- Query 6: Pandemic Impact on EV Adoption
-- Question: Did the pandemic affect the average EV sales share?

SELECT
    y.pandemic_period,
    AVG(s.ev_sales_share) AS avg_share
FROM EVSales s
JOIN Year y ON s.year_id = y.year_id
GROUP BY y.pandemic_period
ORDER BY y.pandemic_period;


-- Query 7: Charging Infrastructure Growth
-- Question: How many charging points did each country add each year?

SELECT
    c.country_name AS country,
    y.year,
    i.ev_charging_points,
    prev.ev_charging_points AS previous_year,
    i.ev_charging_points - COALESCE(prev.ev_charging_points, 0) AS yearly_growth
FROM EVInfrastructure i
JOIN Country c ON i.country_id = c.country_id
JOIN Year y ON i.year_id = y.year_id
LEFT JOIN (
    SELECT
        i2.country_id,
        y2.year AS this_year,
        i2.ev_charging_points
    FROM EVInfrastructure i2
    JOIN Year y2 ON i2.year_id = y2.year_id
) prev
    ON  prev.country_id = i.country_id
    AND prev.this_year = y.year - 1
ORDER BY c.country_name, y.year;


-- Query 8: Countries with Green Electricity but High EV Demand
-- Question: Which countries still rely on fossil fuels despite high EV demand?

SELECT
    c.country_name AS country,
    y.year,
    SUM(s.ev_electricity_demand) AS ev_electricity_demand,
    MAX(e.renewable_electricity_generation) AS renewable_electricity_generation,
    MAX(e.fossil_electricity_generation) AS fossil_electricity_generation
FROM EVSales s
JOIN CountryEnergy e
    ON  s.country_id = e.country_id
    AND s.year_id = e.year_id
JOIN Country c ON s.country_id = c.country_id
JOIN Year y ON s.year_id = y.year_id
WHERE s.ev_electricity_demand > 0
GROUP BY c.country_name, y.year
ORDER BY c.country_name, y.year;


-- Query 9: Continent x Pandemic Period  [RDBMS equivalent of GROUPING SETS]
-- Question: How do EV sales vary by continent and pandemic period?

-- Level 1: (continent, pandemic_period)
SELECT
    c.continent,
    y.pandemic_period,
    SUM(s.ev_sales) AS sales
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
JOIN Year y ON s.year_id = y.year_id
GROUP BY c.continent, y.pandemic_period

UNION ALL

-- Level 2: (continent) subtotal
SELECT
    c.continent,
    NULL AS pandemic_period,
    SUM(s.ev_sales) AS sales
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
GROUP BY c.continent

UNION ALL

-- Level 3: (pandemic_period) subtotal
SELECT
    NULL AS continent,
    y.pandemic_period,
    SUM(s.ev_sales) AS sales
FROM EVSales s
JOIN Year y ON s.year_id = y.year_id
GROUP BY y.pandemic_period

UNION ALL

-- Level 4: grand total
SELECT
    NULL AS continent,
    NULL AS pandemic_period,
    SUM(s.ev_sales) AS sales
FROM EVSales s

ORDER BY continent, pandemic_period;


-- Query 10: Renewable Share of Electricity Generation
-- Question: What percentage of electricity comes from renewables per country/year?

SELECT
    c.country_name AS country,
    y.year,
    ROUND(100.0 * e.renewable_electricity_generation/ e.electricity_generation,2) AS renewable_percentage
FROM CountryEnergy e
JOIN Country c ON e.country_id = c.country_id
JOIN Year y ON e.year_id = y.year_id
WHERE e.electricity_generation > 0
ORDER BY c.country_name, y.year;


-- Query 11: Countries Improving the Most in EV Stock Share
-- Question: Which countries increased their EV stock share the most over time?

SELECT
    c.country_name AS country,
    MIN(y.year) AS first_year,
    MAX(y.year) AS last_year,
    MAX(s.ev_stock_share) - MIN(s.ev_stock_share) AS improvement
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
JOIN Year y ON s.year_id = y.year_id
GROUP BY c.country_name
ORDER BY improvement DESC;


-- Query 12: Is EV Adoption Reducing CO2?
-- Question: Is there a correlation between EV adoption and lower CO2?

SELECT
    c.country_name AS country,
    y.year,
    SUM(s.ev_sales_share) AS ev_sales_share,
    AVG(e.renewable_electricity_generation) AS renewable_electricity_generation,
    AVG(m.co2_per_capita) AS co2_per_capita
FROM EVSales s
JOIN CountryEnergy e
    ON  s.country_id = e.country_id
    AND s.year_id = e.year_id
JOIN CountryMacroeconomics m
    ON  s.country_id = m.country_id
    AND s.year_id = m.year_id
JOIN Country c ON s.country_id = c.country_id
JOIN Year y ON s.year_id = y.year_id
GROUP BY
    c.country_name,
    y.year
ORDER BY
    c.country_name,
    y.year;
