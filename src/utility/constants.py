DW_QUERIES = {

"Q1": """
SELECT
    cont.continent,
    y.year,
    COALESCE(SUM(m.evSales), 0) AS total_ev_sales
FROM (
    SELECT DISTINCT continent
    FROM CountryDim
) cont
CROSS JOIN YearDim y
LEFT JOIN CountryDim c
    ON c.continent = cont.continent
LEFT JOIN EVMarket m
    ON m.keyC = c.keyC
   AND m.keyY = y.keyY
GROUP BY ROLLUP(cont.continent, y.year)
ORDER BY cont.continent, y.year
""",

"Q2": """
SELECT
    c.country,
    y.year,
    ce.renewableElectricityGeneration,
    cm.co2Emissions
FROM CountryEnergy ce
JOIN CountryMacroeconomics cm
    ON ce.keyC = cm.keyC
   AND ce.keyY = cm.keyY
JOIN CountryDim c ON ce.keyC = c.keyC
JOIN YearDim y ON ce.keyY = y.keyY
ORDER BY y.year, ce.renewableElectricityGeneration DESC
""",

"Q3": """
SELECT
    y.year,
    CASE
        WHEN cm.GDP >= 1000000000000 THEN 'High GDP'
        WHEN cm.GDP >= 100000000000 THEN 'Medium GDP'
        ELSE 'Low GDP'
    END AS GDP_class,
    AVG(em.evSalesShare) AS avg_ev_share
FROM CountryMacroeconomics cm
JOIN EVMarket em
    ON cm.keyC = em.keyC
   AND cm.keyY = em.keyY
JOIN YearDim y ON cm.keyY = y.keyY
GROUP BY y.year, GDP_class
ORDER BY y.year, GDP_class
""",

"Q4": """
SELECT
    y.year,
    c.country,
    SUM(evStock) AS stock,
    RANK() OVER (
        PARTITION BY y.year
        ORDER BY SUM(evStock) DESC
    ) AS ranking
FROM EVMarket m
JOIN CountryDim c ON m.keyC = c.keyC
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY y.year, c.country
""",

"Q5": """
SELECT
    v.vehicleType,
    p.powertrain,
    SUM(evSales) AS total_sales
FROM EVMarket m
JOIN VehicleTypeDim v ON m.keyV = v.keyV
JOIN PowertrainDim p ON m.keyP = p.keyP
GROUP BY CUBE(v.vehicleType, p.powertrain)
ORDER BY v.vehicleType, p.powertrain
""",

"Q6": """
SELECT
    y.pandemicPeriod,
    AVG(evSalesShare) AS avg_share
FROM EVMarket m
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY y.pandemicPeriod
""",

"Q7": """
SELECT
    c.country,
    y.year,
    evChargingPoints,
    LAG(evChargingPoints) OVER(
        PARTITION BY c.country
        ORDER BY y.year
    ) AS previous_year,
    evChargingPoints -
    LAG(evChargingPoints) OVER(
        PARTITION BY c.country
        ORDER BY y.year
    ) AS yearly_growth
FROM EVInfrastructure i
JOIN CountryDim c ON i.keyC = c.keyC
JOIN YearDim y ON i.keyY = y.keyY
""",

"Q8": """
SELECT
    c.country,
    y.year,
    SUM(em.evElectricityDemand) as evElectricityDemand,
    max(ce.renewableElectricityGeneration) as renewableElectricityGeneration,
    max(ce.fossilElectricityGeneration) as fossilElectricityGeneration
FROM EVMarket em
JOIN CountryEnergy ce
    ON em.keyC = ce.keyC
   AND em.keyY = ce.keyY
JOIN CountryDim c ON em.keyC = c.keyC
JOIN YearDim y ON em.keyY = y.keyY
WHERE em.evElectricityDemand > 0
GROUP BY c.country, y.year
ORDER BY c.country, y.year
""",

"Q9": """
SELECT
    c.continent,
    y.pandemicPeriod,
    SUM(evSales) AS sales
FROM EVMarket m
JOIN CountryDim c ON m.keyC = c.keyC
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY GROUPING SETS (
    (c.continent, y.pandemicPeriod),
    (c.continent),
    (y.pandemicPeriod),
    ()
)
""",

"Q10": """
SELECT
    c.country,
    y.year,
    ROUND(
        100 * renewableElectricityGeneration /
        electricityGeneration,
        2
    ) AS renewable_percentage
FROM CountryEnergy ce
JOIN CountryDim c ON ce.keyC = c.keyC
JOIN YearDim y ON ce.keyY = y.keyY
WHERE electricityGeneration > 0
ORDER BY c.country, y.year
""",

"Q11": """
SELECT
    c.country,
    MIN(y.year) AS first_year,
    MAX(y.year) AS last_year,
    MAX(evStockShare) - MIN(evStockShare) AS improvement
FROM EVMarket m
JOIN CountryDim c ON m.keyC = c.keyC
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY c.country
ORDER BY improvement DESC
""",

"Q12": """
SELECT
    c.country,
    y.year,
    SUM(em.evSalesShare) AS evSalesShare,
    AVG(ce.renewableElectricityGeneration) AS renewableElectricityGeneration,
    AVG(cm.co2PerCapita) AS co2PerCapita
FROM EVMarket em
JOIN CountryEnergy ce
    ON em.keyC = ce.keyC
    AND em.keyY = ce.keyY
JOIN CountryMacroeconomics cm
    ON em.keyC = cm.keyC
    AND em.keyY = cm.keyY
JOIN CountryDim c ON em.keyC = c.keyC
JOIN YearDim y ON em.keyY = y.keyY
GROUP BY
    c.country,
    y.year
ORDER BY
    c.country,
    y.year
""",

}


# ============================================================
# RDBMS QUERIES  (from src/RDBMS/sql/oltp.sql)
# ============================================================

RDBMS_QUERIES = {

"Q1": """
SELECT
    c.continent,
    y.year,
    COALESCE(SUM(s.ev_sales), 0)    AS total_ev_sales
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
JOIN Year    y ON s.year_id    = y.year_id
GROUP BY c.continent, y.year

UNION ALL

SELECT
    c.continent,
    NULL::INT                        AS year,
    COALESCE(SUM(s.ev_sales), 0)    AS total_ev_sales
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
GROUP BY c.continent

UNION ALL

SELECT
    NULL::VARCHAR                    AS continent,
    NULL::INT                        AS year,
    COALESCE(SUM(s.ev_sales), 0)    AS total_ev_sales
FROM EVSales s

ORDER BY continent, year
""",

"Q2": """
SELECT
    c.country_name                              AS country,
    y.year,
    e.renewable_electricity_generation,
    m.co2_emissions
FROM CountryEnergy e
JOIN CountryMacroeconomics m
    ON  e.country_id = m.country_id
    AND e.year_id    = m.year_id
JOIN Country c ON e.country_id = c.country_id
JOIN Year    y ON e.year_id    = y.year_id
ORDER BY y.year, e.renewable_electricity_generation DESC
""",

"Q3": """
SELECT
    y.year,
    CASE
        WHEN m.gdp >= 1000000000000 THEN 'High GDP'
        WHEN m.gdp >= 100000000000  THEN 'Medium GDP'
        ELSE                             'Low GDP'
    END                                 AS gdp_class,
    AVG(s.ev_sales_share)               AS avg_ev_share
FROM CountryMacroeconomics m
JOIN EVSales s
    ON  m.country_id = s.country_id
    AND m.year_id    = s.year_id
JOIN Year y ON m.year_id = y.year_id
GROUP BY y.year, gdp_class
ORDER BY y.year, gdp_class
""",

"Q4": """
WITH stock_by_country AS (
    SELECT
        c.country_name                  AS country,
        y.year,
        SUM(s.ev_stock)                 AS total_stock
    FROM EVSales s
    JOIN Country c ON s.country_id = c.country_id
    JOIN Year    y ON s.year_id    = y.year_id
    GROUP BY c.country_name, y.year
)
SELECT
    a.year,
    a.country,
    a.total_stock                       AS stock,
    1 + COUNT(b.country)                AS ranking
FROM stock_by_country a
LEFT JOIN stock_by_country b
    ON  a.year        = b.year
    AND b.total_stock > a.total_stock
GROUP BY a.year, a.country, a.total_stock
ORDER BY a.year, ranking
""",

"Q5": """
SELECT
    vt.type_name                        AS vehicle_type,
    pt.powertrain_name                  AS powertrain,
    SUM(s.ev_sales)                     AS total_sales
FROM EVSales s
JOIN VehicleType vt ON s.vehicle_type_id = vt.vehicle_type_id
JOIN Powertrain  pt ON s.powertrain_id   = pt.powertrain_id
GROUP BY vt.type_name, pt.powertrain_name

UNION ALL

SELECT
    vt.type_name,
    NULL         AS powertrain,
    SUM(s.ev_sales)                      AS total_sales
FROM EVSales s
JOIN VehicleType vt ON s.vehicle_type_id = vt.vehicle_type_id
GROUP BY vt.type_name

UNION ALL

SELECT
    NULL                      AS vehicle_type,
    pt.powertrain_name,
    SUM(s.ev_sales)                      AS total_sales
FROM EVSales s
JOIN Powertrain pt ON s.powertrain_id = pt.powertrain_id
GROUP BY pt.powertrain_name

UNION ALL

SELECT
    NULL                       AS vehicle_type,
    NULL                       AS powertrain,
    SUM(s.ev_sales)                      AS total_sales
FROM EVSales s

ORDER BY vehicle_type, powertrain
""",

"Q6": """
SELECT
    y.pandemic_period,
    AVG(s.ev_sales_share)               AS avg_share
FROM EVSales s
JOIN Year y ON s.year_id = y.year_id
GROUP BY y.pandemic_period
ORDER BY y.pandemic_period
""",

"Q7": """
SELECT
    c.country_name                      AS country,
    y.year,
    i.ev_charging_points,
    prev.ev_charging_points             AS previous_year,
    i.ev_charging_points
        - COALESCE(prev.ev_charging_points, 0)
                                        AS yearly_growth
FROM EVInfrastructure i
JOIN Country c   ON i.country_id  = c.country_id
JOIN Year    y   ON i.year_id     = y.year_id
LEFT JOIN (
    SELECT
        i2.country_id,
        y2.year                         AS this_year,
        i2.ev_charging_points
    FROM EVInfrastructure i2
    JOIN Year y2 ON i2.year_id = y2.year_id
) prev
    ON  prev.country_id = i.country_id
    AND prev.this_year  = y.year - 1
ORDER BY c.country_name, y.year
""",

"Q8": """
SELECT
    c.country_name                              AS country,
    y.year,
    SUM(s.ev_electricity_demand)                AS ev_electricity_demand,
    MAX(e.renewable_electricity_generation)     AS renewable_electricity_generation,
    MAX(e.fossil_electricity_generation)        AS fossil_electricity_generation
FROM EVSales s
JOIN CountryEnergy e
    ON  s.country_id = e.country_id
    AND s.year_id    = e.year_id
JOIN Country c ON s.country_id = c.country_id
JOIN Year    y ON s.year_id    = y.year_id
WHERE s.ev_electricity_demand > 0
GROUP BY c.country_name, y.year
ORDER BY c.country_name, y.year
""",

"Q9": """
SELECT
    c.continent,
    y.pandemic_period,
    SUM(s.ev_sales)                     AS sales
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
JOIN Year    y ON s.year_id    = y.year_id
GROUP BY c.continent, y.pandemic_period

UNION ALL

SELECT
    c.continent,
    NULL::VARCHAR                        AS pandemic_period,
    SUM(s.ev_sales)                      AS sales
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
GROUP BY c.continent

UNION ALL

SELECT
    NULL::VARCHAR                        AS continent,
    y.pandemic_period,
    SUM(s.ev_sales)                      AS sales
FROM EVSales s
JOIN Year y ON s.year_id = y.year_id
GROUP BY y.pandemic_period

UNION ALL

SELECT
    NULL::VARCHAR                        AS continent,
    NULL::VARCHAR                        AS pandemic_period,
    SUM(s.ev_sales)                      AS sales
FROM EVSales s

ORDER BY continent, pandemic_period
""",

"Q10": """
SELECT
    c.country_name                              AS country,
    y.year,
    ROUND(
        100.0 * e.renewable_electricity_generation
              / e.electricity_generation,
        2
    )                                           AS renewable_percentage
FROM CountryEnergy e
JOIN Country c ON e.country_id = c.country_id
JOIN Year    y ON e.year_id    = y.year_id
WHERE e.electricity_generation > 0
ORDER BY c.country_name, y.year
""",

"Q11": """
SELECT
    c.country_name                              AS country,
    MIN(y.year)                                 AS first_year,
    MAX(y.year)                                 AS last_year,
    MAX(s.ev_stock_share) - MIN(s.ev_stock_share)
                                                AS improvement
FROM EVSales s
JOIN Country c ON s.country_id = c.country_id
JOIN Year    y ON s.year_id    = y.year_id
GROUP BY c.country_name
ORDER BY improvement DESC
""",

"Q12": """
SELECT
    c.country_name                              AS country,
    y.year,
    SUM(s.ev_sales_share)                       AS ev_sales_share,
    AVG(e.renewable_electricity_generation)     AS renewable_electricity_generation,
    AVG(m.co2_per_capita)                       AS co2_per_capita
FROM EVSales s
JOIN CountryEnergy e
    ON  s.country_id = e.country_id
    AND s.year_id    = e.year_id
JOIN CountryMacroeconomics m
    ON  s.country_id = m.country_id
    AND s.year_id    = m.year_id
JOIN Country c ON s.country_id = c.country_id
JOIN Year    y ON s.year_id    = y.year_id
GROUP BY
    c.country_name,
    y.year
ORDER BY
    c.country_name,
    y.year
""",

}