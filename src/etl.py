import pandas as pd
import numpy as np

def extract():
    """
        EXTRACTION PHASE
    """
    df_emissions = pd.read_csv("./datasets/owid-co2-data.csv", low_memory=False)
    df_energy = pd.read_csv("./datasets/owid-energy-data.csv", low_memory=False)
    df_ev = pd.read_csv("./datasets/iea-global-ev-sales.csv", low_memory=False)
    print("Data extraction completed...")
    return df_emissions, df_energy, df_ev

def transform(df_emissions, df_energy, df_ev):
    """
        TRANSFORMATION PHASE
    """
    # ==========================================
    # 2.1. PULIZIA E FILTRAGGIO DATASET 1 E 2 (OWID)
    # ==========================================
    df_emissions.columns = df_emissions.columns.str.strip()
    df_energy.columns = df_energy.columns.str.strip()
    df_ev.columns = df_ev.columns.str.strip()
    df_energy.columns = df_energy.columns.str.replace(r'[^\w]', '', regex=True).str.strip()

    df_emissions = df_emissions[[
        'country',
        'year',
        'iso_code',
        'population',
        'gdp',
        'co2',
        'co2_per_capita',
        'co2_per_gdp',
        'oil_co2',
        'oil_co2_per_capita',
        'coal_co2',
        'coal_co2_per_capita',
        'co2_per_unit_energy',
        'primary_energy_consumption',
        'consumption_co2',
        'consumption_co2_per_capita',
        'consumption_co2_per_gdp'
    ]]
    df_energy = df_energy[[
        'country',
        'year',
        'iso_code',
        'population',
        'gdp',
        'electricity_generation',
        'electricity_demand',
        'primary_energy_consumption',
        'low_carbon_electricity',
        'fossil_electricity',
        'renewables_electricity',
        'coal_electricity',
        'gas_electricity',
        'oil_electricity',
        'nuclear_electricity',
        'hydro_electricity',
        'solar_electricity',
        'wind_electricity',
        'other_renewable_electricity',
        'net_elec_imports'
    ]]
    # Applichiamo il filtro temporale richiesto (2010-2024)
    df_emissions = df_emissions[(df_emissions['year'] >= 2010) & (df_emissions['year'] <= 2024)]
    df_energy = df_energy[(df_energy['year'] >= 2010) & (df_energy['year'] <= 2024)]
    
    # Rimuoviamo le righe dove l'iso_code è nullo (spesso aggregati regionali globali disallineati)
    df_emissions = df_emissions.dropna(subset=['iso_code'])
    df_energy = df_energy.dropna(subset=['iso_code'])
    df_energy = df_energy.rename(columns={'electricity_demand': 'electricity_demand_tot'})
    # Gestione delle ridondanze (Scenario 3 del nostro caso): 
    # Le chiavi primarie di join sono 'iso_code' e 'year'. 
    # Rimuoviamo 'country', 'population', 'gdp' e 'primary_energy_consumption' da df_energy 
    # per evitare colonne duplicate (.x / .y) dopo la Join. Teniamo quelle di df_emissions.
    df_energy_clean = df_energy.drop(columns=['country', 'population', 'gdp', 'primary_energy_consumption'])

    # JOIN tra i due dataset OWID (Emissions + Energy)
    df_owid = pd.merge(df_emissions, df_energy_clean, on=['iso_code', 'year'], how='inner')

    # ==========================================
    # 2.2. TRASFORMAZIONE DATASET 3 (IEA EV SALES)
    # ==========================================
    # Filtriamo per tenere solo i dati storici effettivi, escludendo le proiezioni future
    df_ev = df_ev[(df_ev['region'] != 'World')]
    df_ev = df_ev[(df_ev['region'] != 'Rest of the world')]
    df_ev = df_ev[df_ev['category'] == 'Historical']
    df_ev = df_ev[(df_ev['year'] >= 2010) & (df_ev['year'] <= 2024)]

    # Standardizziamo il nome della colonna geografica per la join successiva
    df_ev = df_ev.rename(columns={'region': 'country'})

    # PIVOTING: Trasformiamo il formato "long" in "wide".
    # Vogliamo che i valori dentro la colonna 'parameter' diventino colonne a sé stanti.
    # Usiamo le dimensioni come indice e aggreghiamo i valori della colonna 'value'.
    df_ev_wide = df_ev.pivot_table(
        index=['country', 'year', 'mode', 'powertrain'],
        columns='parameter',
        values='value',
        aggfunc='first'
    ).reset_index()

    # Rinominiamo le colonne generate dal pivot per evitare spazi o caratteri speciali in SQL
    df_ev_wide.columns.name = None  # Rimuove il nome dell'indice delle colonne
    df_ev_wide = df_ev_wide.rename(columns=lambda x: x.strip().lower().replace(" ", "_"))
    
    df_ev_wide = df_ev_wide.rename(columns={'electricity_demand': 'electricity_demand_ev'})


    # ==========================================
    # 2.3. INTEGRAZIONE FINALE (OWID + IEA)
    # ==========================================
    # Uniamo il blocco OWID (Emissions+Energy) con il blocco IEA EV.
    # Usiamo 'country' e 'year' come chiavi di join. 
    # Nota: Usiamo una left join per mantenere tutti i dati storici dei paesi, 
    # anche se non hanno record sulle vendite EV nel dataset IEA per quell'anno.
    df_final = pd.merge(df_ev_wide, df_owid, on=['country', 'year'], how='left')

    # Riattiviamo la coerenza dei dati: sostituiamo i valori NaN nelle metriche EV con 0
    # per i paesi che non hanno registrato vendite in quegli anni.
    ev_metrics = [col for col in df_ev_wide.columns if col not in ['country', 'year', 'mode', 'powertrain']]
    df_final[ev_metrics] = df_final[ev_metrics].fillna(0)

    print("Transformation completed...")
    return df_final

def load(df_final):
    """
        LOADING PHASE
    """
    name_file_output = "ev_energy_emissions_integrated.csv"
    print(f"Saving the final dataset in {name_file_output}...")
    
    # index=False evita che venga creata una colonna inutile con i numeri di riga di Pandas
    df_final.to_csv(name_file_output, index=False, encoding='utf-8')
    
    print(f"ETL completed! File created '{name_file_output}' with {len(df_final)} rows.")

if __name__ == "__main__":
    try:
        raw_emissions, raw_energy, raw_ev = extract()
        clean_data = transform(raw_emissions, raw_energy, raw_ev)
        load(clean_data)
    except Exception as e:
        print(f"Error: {e}")