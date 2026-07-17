import pandas as pd
import difflib

def get_half_decade(year):
    if year <= 2014:
        return "2010-2014"
    elif year <= 2019:
        return "2015-2019"
    else:
        return "2020-2023"

def get_pandemic_period(year):
    if year < 2020:
        return "Pre-Pandemic"
    elif year <= 2021:
        return "Pandemic"
    else:
        return "Post-Pandemic"

def clean_country_name(name):
    words_to_remove = [
        "republic of", "republic", "kingdom of", "democratic", 
        "people's", "cooperative", "federation", "state of", 
        "principality of", "commonwealth of the", "commonwealth of"
    ]
    name_low = name.lower()
    for w in words_to_remove:
        name_low = name_low.replace(w, "")
    return name_low.strip()

def find_iso_code(name, owid_dict):
    """
    This function implements the country and ISO code mapping.
    Returns: (iso_code, standard_name)
    """
    name_low = name.lower()
    
    # Exact match (case insensitive)
    for k, v in owid_dict.items():
        if k.lower() == name_low:
            return v, k
            
    # Check if name is already an ISO code
    if name.upper() in owid_dict.values():
        for k, v in owid_dict.items():
            if v == name.upper():
                return v, k
        return name.upper(), name
        
    # Cleaned exact match (e.g., 'Czech Republic' -> 'Czechia' when normalized to 'czech')
    c_name = clean_country_name(name)
    for k, v in owid_dict.items():
        if clean_country_name(k) == c_name:
            return v, k
            
    # Handle Special case: Korea maps to South Korea (KOR) in the context of EV data
    if "korea" in name_low:
        for k, v in owid_dict.items():
            if "south korea" in k.lower():
                return v, k
                
    # Fuzzy match on cleaned names using difflib
    cleaned_owid = {clean_country_name(k): (v, k) for k, v in owid_dict.items()}
    matches = difflib.get_close_matches(c_name, cleaned_owid.keys(), n=1, cutoff=0.6)
    if matches:
        return cleaned_owid[matches[0]]
        
    # Fallback fuzzy match on raw names
    matches = difflib.get_close_matches(name_low, [k.lower() for k in owid_dict.keys()], n=1, cutoff=0.6)
    if matches:
        matched_name = list(owid_dict.keys())[[k.lower() for k in owid_dict.keys()].index(matches[0])]
        return owid_dict[matched_name], matched_name
        
    return None, name

def transform_data(ev, co2, energy, continent_mapping):
    """
    Applies data cleansing, automated mappings, pivots, and adds geographical
    and temporal dimensions. Returns the three cleaned DataFrames.
    """
    print("=== Transforming and Cleaning Data ===")
    
    # Clean the IEA EV Sales dataset
    print("Cleaning EV dataset...")

    # Only keep historical data between 2010 and 2023
    ev_clean = ev[(ev["category"] == "Historical") & (ev["year"] >= 2010) & (ev["year"] <= 2023)].copy()
    ev_clean = ev_clean.rename(columns={"region": "country"})
    
    # Remove aggregate areas to keep only actual countries
    aggregates = ["World", "Europe", "EU27", "Rest of the world"]
    ev_clean = ev_clean[~ev_clean["country"].isin(aggregates)]
    
    # Build OWID mapping dictionary from CO2 and Energy
    co2_map = co2[["country", "iso_code"]].dropna().drop_duplicates().set_index("country")["iso_code"].to_dict()
    energy_map = energy[["country", "iso_code"]].dropna().drop_duplicates().set_index("country")["iso_code"].to_dict()
    owid_dict = {**co2_map, **energy_map}
    
    # Map country names to ISO code and standardized name dynamically
    mapping_cache = {}
    for country in ev_clean["country"].unique():
        iso, std_name = find_iso_code(country, owid_dict)
        if iso:
            mapping_cache[country] = {"iso_code": iso, "country_name": std_name}
        else:
            print(f"Warning: Could not match country name: {country}")
            mapping_cache[country] = {"iso_code": None, "country_name": country}
            
    # Apply standardized names and ISO codes
    ev_clean["iso_code"] = ev_clean["country"].map(lambda x: mapping_cache[x]["iso_code"])
    ev_clean["country"] = ev_clean["country"].map(lambda x: mapping_cache[x]["country_name"])
    
    # Drop rows where we could not get an ISO code
    ev_clean = ev_clean.dropna(subset=["iso_code"])
    
    # Filter out parameters we don't need for the analysis
    unwanted_params = ["Oil displacement Mbd", "Oil displacement, million lge"]
    ev_clean = ev_clean[~ev_clean["parameter"].isin(unwanted_params)]
    
    # Pivot dataset from long format to wide format
    ev_wide = ev_clean.pivot_table(
        index=["country", "iso_code", "year", "mode", "powertrain"],
        columns="parameter",
        values="value",
        aggfunc="first"
    ).reset_index()
    
    ev_wide.columns.name = None
    ev_wide = ev_wide.rename(columns=lambda x: x.strip().lower().replace(" ", "_"))
    
    # Fill NaN with 0 for EV metrics
    ev_cols = ["ev_sales", "ev_stock", "ev_sales_share", "ev_stock_share", "electricity_demand", "ev_charging_points"]
    for col in ev_cols:
        if col in ev_wide.columns:
            ev_wide[col] = ev_wide[col].fillna(0.0).astype(float)
    ev_wide["year"] = ev_wide["year"].astype(int)
    
    # Map continents
    cc_unique = continent_mapping.drop_duplicates(subset=["Three_Letter_Country_Code"]).copy()
    continent_name_map = cc_unique.set_index("Three_Letter_Country_Code")["Continent_Name"].to_dict()
    continent_code_map = cc_unique.set_index("Three_Letter_Country_Code")["Continent_Code"].to_dict()
    
    ev_wide["halfDecade"] = ev_wide["year"].apply(get_half_decade)
    ev_wide["pandemicPeriod"] = ev_wide["year"].apply(get_pandemic_period)
    ev_wide["continent"] = ev_wide["iso_code"].map(continent_name_map)
    ev_wide["continentCode"] = ev_wide["iso_code"].map(continent_code_map)
    
    rename_ev = {
        "iso_code": "isoCode",
        "mode": "vehicleType",
        "ev_sales": "evSales",
        "ev_sales_share": "evSalesShare",
        "ev_stock": "evStock",
        "ev_stock_share": "evStockShare",
        "electricity_demand": "evElectricityDemand",
        "ev_charging_points": "evChargingPoints"
    }
    ev_wide = ev_wide.rename(columns=rename_ev)
    
    ev_cols_order = [
        "country", "isoCode", "continent", "continentCode", 
        "year", "halfDecade", "pandemicPeriod", 
        "vehicleType", "powertrain", 
        "evSales", "evSalesShare", "evStock", "evStockShare", "evElectricityDemand", "evChargingPoints"
    ]
    ev_transformed = ev_wide[ev_cols_order]

    # Clean CO2 dataset
    print("Cleaning CO2 dataset...")
    co2_cols = [
        "country", "year", "iso_code", "population", "gdp", 
        "co2", "co2_per_capita", "co2_per_gdp", 
        "oil_co2", "oil_co2_per_capita", "coal_co2", "coal_co2_per_capita", 
        "co2_per_unit_energy", "primary_energy_consumption"
    ]
    
    co2_clean = co2[co2_cols].dropna(subset=["iso_code"]).copy()
    co2_clean = co2_clean[(co2_clean["year"] >= 2010) & (co2_clean["year"] <= 2023)]
    co2_clean["year"] = co2_clean["year"].astype(int)
    for col in co2_cols:
        if col not in ["country", "iso_code", "year"]:
            co2_clean[col] = co2_clean[col].astype(float)
            
    co2_clean["halfDecade"] = co2_clean["year"].apply(get_half_decade)
    co2_clean["pandemicPeriod"] = co2_clean["year"].apply(get_pandemic_period)
    co2_clean["continent"] = co2_clean["iso_code"].map(continent_name_map)
    co2_clean["continentCode"] = co2_clean["iso_code"].map(continent_code_map)
    
    rename_co2 = {
        "iso_code": "isoCode",
        "gdp": "GDP",
        "co2": "co2Emissions",
        "co2_per_capita": "co2PerCapita",
        "co2_per_gdp": "co2PerGDP",
        "oil_co2": "co2EmissionsOil",
        "oil_co2_per_capita": "co2EmissionsOilPerCapita",
        "coal_co2": "co2EmissionsCoal",
        "coal_co2_per_capita": "co2EmissionsCoalPerCapita",
        "co2_per_unit_energy": "co2EmissionsPerUnitEnergy",
        "primary_energy_consumption": "energyConsumption"
    }
    co2_clean = co2_clean.rename(columns=rename_co2)
    
    co2_cols_order = [
        "country", "isoCode", "continent", "continentCode", 
        "year", "halfDecade", "pandemicPeriod", 
        "population", "GDP", "co2Emissions", "co2PerCapita", "co2PerGDP", 
        "co2EmissionsOil", "co2EmissionsOilPerCapita", "co2EmissionsCoal", "co2EmissionsCoalPerCapita", 
        "co2EmissionsPerUnitEnergy", "energyConsumption"
    ]
    co2_transformed = co2_clean[co2_cols_order]

    # Clean Energy dataset
    print("Cleaning Energy dataset...")
    energy_cols = [
        "country", "year", "iso_code", "population", "gdp", 
        "electricity_generation", "electricity_demand", "primary_energy_consumption", 
        "low_carbon_electricity", "fossil_electricity", "renewables_electricity", 
        "coal_electricity", "gas_electricity", "oil_electricity", 
        "nuclear_electricity", "hydro_electricity", "solar_electricity", 
        "wind_electricity", "other_renewable_electricity", "net_elec_imports"
    ]
    
    energy_clean = energy[energy_cols].dropna(subset=["iso_code"]).copy()
    energy_clean = energy_clean[(energy_clean["year"] >= 2010) & (energy_clean["year"] <= 2023)]
    energy_clean["year"] = energy_clean["year"].astype(int)
    for col in energy_cols:
        if col not in ["country", "iso_code", "year"]:
            energy_clean[col] = energy_clean[col].astype(float)
            
    energy_clean["halfDecade"] = energy_clean["year"].apply(get_half_decade)
    energy_clean["pandemicPeriod"] = energy_clean["year"].apply(get_pandemic_period)
    energy_clean["continent"] = energy_clean["iso_code"].map(continent_name_map)
    energy_clean["continentCode"] = energy_clean["iso_code"].map(continent_code_map)
    
    rename_energy = {
        "iso_code": "isoCode",
        "gdp": "GDP",
        "primary_energy_consumption": "energyConsumption",
        "electricity_generation": "electricityGeneration",
        "electricity_demand": "electricityDemand",
        "fossil_electricity": "fossilElectricityGeneration",
        "coal_electricity": "coalElectricityGeneration",
        "oil_electricity": "oilElectricityGeneration",
        "gas_electricity": "gasElectricityGeneration",
        "renewables_electricity": "renewableElectricityGeneration",
        "low_carbon_electricity": "lowCarbonElectricityGeneration",
        "wind_electricity": "windElectricityGeneration",
        "hydro_electricity": "hydroElectricityGeneration",
        "nuclear_electricity": "nuclearElectricityGeneration",
        "other_renewable_electricity": "otherElectricityGeneration",
        "solar_electricity": "solarElectricityGeneration",
        "net_elec_imports": "netElectricityImports"
    }
    energy_clean = energy_clean.rename(columns=rename_energy)
    
    energy_cols_order = [
        "country", "isoCode", "continent", "continentCode", 
        "year", "halfDecade", "pandemicPeriod", 
        "population", "GDP", "energyConsumption", 
        "electricityGeneration", "electricityDemand", 
        "fossilElectricityGeneration", "coalElectricityGeneration", "oilElectricityGeneration", "gasElectricityGeneration", 
        "renewableElectricityGeneration", "lowCarbonElectricityGeneration", 
        "windElectricityGeneration", "hydroElectricityGeneration", "nuclearElectricityGeneration", 
        "otherElectricityGeneration", "solarElectricityGeneration", "netElectricityImports"
    ]
    energy_transformed = energy_clean[energy_cols_order]
    
    print("Transformation phase completed successfully!\n")
    return ev_transformed, co2_transformed, energy_transformed
