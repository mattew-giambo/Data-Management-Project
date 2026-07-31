# REPORT DI DATA PROFILING AND DATA CLEANING
## Fase di Data Staging - Progetto di Data Management

Il presente documento descrive le attività di **Data Profiling** e di **Data Cleaning** condotte sui tre dataset del progetto (`iea-global-ev-sales.csv`, `owid-co2-data.csv`, `owid-energy-data.csv`). L'obiettivo di questa fase è preparare i dati grezzi nella **Data Staging Area** ed esportare dei file CSV puliti ed elaborati, pronti per essere inseriti nello schema logico del Data Warehouse (DWH), garantendo l'esclusione di stime previsionali e il rispetto dei requisiti accademici.

---

## 1. SINTESI DEL DATA PROFILING (ANALISI DEI FILE GREZZI)

Prima di procedere alla pulizia dei dati, è stata eseguita una scansione programmatica delle fonti informative per mappare le anomalie di **Data Quality**, le discrepanze tra le chiavi di join e la presenza di dati non storici.

### A. Rilevamento di Proiezioni e Scenari Futuri (Forecasts)
Il vincolo fondamentale del progetto prevede l'elaborazione esclusiva di **Historical Data** reali. L'analisi ha evidenziato le seguenti criticità:
* **Dataset IEA EV Sales**: Contiene **3.480 righe** associate a scenari previsionali futuri fino al 2035. Nello specifico, la colonna `category` presenta tre valori distinti:
  - `Historical` (9.174 righe): dati reali consuntivati nel range temporale **2010–2023**.
  - `Projection-STEPS` (1.738 righe): proiezioni basate sulle politiche dichiarate (*Stated Policies Scenario*), nel range **2020–2035**.
  - `Projection-APS` (1.742 righe): proiezioni basate sugli impegni annunciati (*Announced Pledges Scenario*), nel range **2020–2035**.
* **Dataset OWID CO2**: Contiene dati esclusivamente storici a partire dal 1750 fino al **2024** (0 righe future oltre il 2024).
* **Dataset OWID Energy**: Contiene dati storici dal 1900 al 2024, ma presenta **106 righe** associate all'anno **2025** (es. stime preliminari per aggregati come *ASEAN (Ember)* o singoli paesi come *Argentina*, *Australia*).

### B. Discrepanze nelle Chiavi di Integrazione (Country & ISO Code)
Per integrare le tre sorgenti, è necessario disporre di chiavi logiche coerenti. L'analisi ha rilevato i seguenti conflitti:
* **Assenza di ISO Code in IEA**: Il dataset IEA EV Sales non contiene i codici ISO standard dei paesi, ma solo la colonna testuale `region`.
* **Incoerenze nei Nomi dei Paesi**: Alcuni paesi hanno nomi discordanti tra IEA e i dataset OWID:
  - `USA` (IEA) $\rightarrow$ `United States` (OWID)
  - `Korea` (IEA) $\rightarrow$ `South Korea` (OWID)
  - `Turkiye` (IEA) $\rightarrow$ `Turkey` (OWID)
  - `Czech Republic` (IEA) $\rightarrow$ `Czechia` (OWID)
* **Aggregati Regionali**: Il dataset IEA presenta aggregati economici e macro-regionali (`World`, `Europe`, `EU27`, `Rest of the world`) privi di una corrispondenza nazionale diretta. Nei dataset OWID, gli aggregati regionali (es. *Africa*, *Asia*, *OPEC*) sono identificati da un valore `iso_code` nullo (*Null Values*).

### C. Inconsistenze Temporali nei Dati Storici
* I range storici effettivi rilevati sono:
  - IEA EV Sales (storico reale): **2010–2023**
  - OWID CO2 (storico reale): **1750–2024**
  - OWID Energy (storico reale): **1900–2025**
* Per allineare temporalmente i tre flussi in modo coerente ed evitare di inserire anni non coperti da tutte le fonti, l'orizzonte temporale consolidato deve essere limitato all'intervallo **2010–2023**.

### D. Missing Values & Anomalie
* **Tasso di Nulli su Variabili Macroeconomiche**: Nel periodo storico 2010–2023, la variabile `gdp` (PIL) presenta un tasso di valori mancanti del **43.8%** nel dataset CO2. La popolazione presenta circa l'11% di nulli nel dataset Energy. Molti di questi nulli sono dovuti a territori minori o isole (es. *Bermuda*, *Sint Maarten*).
* **Anomalie su Metriche Energetiche**: Variabili come `electricity_generation` e `electricity_demand` presentano rispettivamente 717 e 912 valori nulli nel periodo storico a causa di lacune di rilevamento in paesi in via di sviluppo.
* **Valori Negativi**: Non si registrano valori negativi anomali sulle vendite di EV, sulla generazione elettrica o sulle emissioni di CO2. La colonna `net_elec_imports` (importazioni nette) presenta 1.481 valori negativi, il che è **corretto** e coerente con la definizione della misura (un'importazione netta negativa rappresenta un'esportazione netta).

---

## 2. REGISTRO DELLE AZIONI DI CLEANING (DATA CLEANING LOG)

Per risolvere i problemi evidenziati nel profiling, è stato eseguito lo script Python `clean_data.py`. Di seguito vengono documentate le regole e le logiche implementate:

### Azione 1: Esclusione delle Proiezioni ed Allineamento Temporale
* Lo script ha filtrato il dataset IEA EV Sales tenendo solo le righe in cui `category == 'Historical'`.
* Tutti e tre i dataset sono stati filtrati per includere esclusivamente record con `year >= 2010` e `year <= 2023`. Questo ha rimosso automaticamente le 106 righe del 2025 nel dataset Energy e le proiezioni IEA oltre il 2023.

### Azione 2: Risoluzione dei Conflitti Geografici ed Eliminazione degli Aggregati
* **Mappatura ISO per IEA**: È stato costruito un dizionario di lookup `country` $\rightarrow$ `iso_code` basandosi sulle associazioni univoche presenti nei file OWID.
* **Correzione Nomi Paesi**: Prima dell'assegnazione dell'ISO Code, i nomi dei paesi nel dataset IEA sono stati normalizzati (`USA` $\rightarrow$ `United States`, `Korea` $\rightarrow$ `South Korea`, `Turkiye` $\rightarrow$ `Turkey`, `Czech Republic` $\rightarrow$ `Czechia`).
* **Rimozione degli Aggregati**:
  - Nel dataset IEA sono state rimosse le righe relative alle macro-aree `World`, `Europe`, `EU27`, `Rest of the world` in quanto non associabili ad un singolo `iso_code` nazionale reale.
  - Nei dataset OWID CO2 ed Energy, sono state rimosse tutte le righe aventi `iso_code` nullo (`dropna(subset=['iso_code'])`). Questo ha eliminato automaticamente tutti i raggruppamenti continentali ed economici (es. OPEC, OECD, Europa ex-UE).

### Azione 3: Pivoting del Dataset EV (Da formato Long a Wide)
* Le misure originariamente impilate nella colonna `parameter` (es. `EV sales`, `EV stock`, ecc.) sono state ruotate in colonne separate tramite un'operazione di `pivot_table` indicizzata su `['country', 'iso_code', 'year', 'mode', 'powertrain']`.
* Le colonne dei parametri `Oil displacement Mbd` e `Oil displacement, million lge` sono state escluse in quanto non necessarie ai fini del DWH.
* I nomi delle colonne generate dal pivot sono stati ripuliti e convertiti in lettere minuscole con caratteri *underscore* per facilitare l'importazione in SQL.

### Azione 4: Gestione Metodologica dei Valori Nulli nelle Misure
* **Misure EV**: La rotazione (pivoting) genera valori `NaN` per quelle combinazioni di veicolo/alimentazione in cui un paese non ha registrato vendite o stock in un certo anno. Questi valori sono stati imputati a `0.0` (es. se l'Italia non ha venduto camion BEV nel 2010, il valore corretto della misura è 0).
* **Misure Socio-Economiche ed Energetiche (OWID)**: I valori nulli per `gdp`, `population`, `electricity_generation`, ecc., **NON sono stati imputati a 0**. Sostituire il PIL o la popolazione mancante con zero falserebbe gravemente le medie e le aggregazioni nel DWH. Tali campi sono stati mantenuti vuoti (`NULL` in SQL), consentendo alle funzioni aggregate del database (es. `AVG`) di ignorarli correttamente a livello di calcolo.

### Azione 5: Casting dei Tipi di Dato
* La colonna `year` è stata forzata a tipo `int` (Intero).
* Tutte le colonne quantitative e le misure scientifiche (es. CO2, GDP, popolazione, vendite EV) sono stato castate a `float` (Virgola mobile).

---

## 3. VALIDAZIONE FINALE DEI DATI IN STAGING

Al termine del processo di cleaning, i file puliti salvati nella cartella `staging_area/` sono stati validati tramite lo script `validate_clean_data.py`, confermando il soddisfacimento dei requisiti di qualità:

1. **Assenza di Proiezioni Future**:
   - `clean_iea_ev_sales.csv`: Range temporale fisso **2010–2023**. Righe totali: **4.259** (dopo la rotazione delle colonne).
   - `clean_owid_co2.csv`: Range temporale fisso **2010–2023**. Righe totali: **3.052**.
   - `clean_owid_energy.csv`: Range temporale fisso **2010–2023**. Righe totali: **3.078**.
2. **Integrità Referenziale delle Chiavi di Join**:
   - Tutte le righe di tutti e tre i dataset presentano un `iso_code` standard compilato (0 valori nulli sulle chiavi geografiche).
   - Tutti i record presentano un campo `year` valido e non nullo.
   - Sono stati mappati con successo **50 paesi storici** nel dataset EV.
   - **Copertura Geografica al 100%**: Tutti i 50 codici ISO presenti nel dataset pulito degli EV sono pienamente presenti ed esistenti sia nel dataset CO2 sia nel dataset Energy. Non ci sono orfani geografici, garantendo join referenziali pulite nel DWH.
3. **Assenza di Nulli nelle Misure EV**:
   - Tutte le metriche EV ruotate (vendite, stock, share, punti di ricarica, domanda elettrica) presentano 0 valori nulli (completamente imputati a 0.0 laddove assenti).

I tre file in `staging_area/` sono metodologicamente coerenti, privi di stime previsionali future e pronti per essere importati nel Data Warehouse.
