-- 1. EV Sales by Continent and Year (ROLL-UP)
-- Question: How have EV sales evolved across continents over time?

SELECT
    c.continent,
    y.year,
    SUM(m.evSales) AS total_ev_sales
FROM EVMarket m
JOIN CountryDim c ON m.keyC = c.keyC
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY ROLLUP(c.continent, y.year)
ORDER BY c.continent, y.year;

-- 2. Renewable Electricity vs CO₂ Emissions
-- Question: Are countries with more renewable electricity producing less CO₂?

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
ORDER BY y.year, ce.renewableElectricityGeneration DESC;

-- 3. Rich vs Poor Countries
-- Question: Do richer countries have higher EV adoption?

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
ORDER BY y.year, GDP_class;

-- 4. Top Countries by EV Stock
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
GROUP BY y.year, c.country;

-- 5. Vehicle Type Analysis (CUBE)
-- Question: Which vehicle type and powertrain dominate sales?

SELECT
    v.vehicleType,
    p.powertrain,
    SUM(evSales) AS total_sales
FROM EVMarket m
JOIN VehicleTypeDim v ON m.keyV = v.keyV
JOIN PowertrainDim p ON m.keyP = p.keyP
GROUP BY CUBE(v.vehicleType, p.powertrain)
ORDER BY v.vehicleType, p.powertrain;

-- 6. Pandemic Impact
-- Since you created pandemicPeriod.

SELECT
    y.pandemicPeriod,
    AVG(evSalesShare) AS avg_share
FROM EVMarket m
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY y.pandemicPeriod;

-- 7. Charging Infrastructure Growth
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
JOIN YearDim y ON i.keyY = y.keyY;

-- 8. Countries Producing Green Electricity but High EV Demand
-- Shows countries where EV demand may still rely heavily on fossil fuels.

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
ORDER BY c.country, y.year;

-- 9. Continent × Pandemic Period (GROUPING SETS) (superflua)
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
);

-- 10. Renewable Share of Electricity
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
ORDER BY c.country, y.year;

-- 11. Countries Improving the Most (Superflua)
SELECT
    c.country,
    MIN(y.year) AS first_year,
    MAX(y.year) AS last_year,
    MAX(evStockShare) - MIN(evStockShare) AS improvement
FROM EVMarket m
JOIN CountryDim c ON m.keyC = c.keyC
JOIN YearDim y ON m.keyY = y.keyY
GROUP BY c.country
ORDER BY improvement DESC;

-- 12. Is EV Adoption Reducing CO₂?
-- This directly answers your project question.
-- This dataset is ideal for scatter plots, dashboards, or statistical analysis 
-- to assess whether higher EV adoption combined with cleaner electricity generation corresponds to lower CO₂ emissions.
SELECT
    c.country,
    y.year,
    SUM(em.evSalesShare) AS evSalesShare, -- Usa SUM() se le quote sono spezzate per categoria (es. BEV + PHEV), altrimenti AVG()
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
    y.year;