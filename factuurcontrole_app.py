import sqlite3
import streamlit as st
import pandas as pd
import os
from datetime import datetime

# === Configuratie ===
DB_FILE = "factuurcontrole.db"

# === Functie om bestaande data te laden of nieuwe aan te maken ===
def load_data():
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query("SELECT * FROM facturen", conn)
    return df

# === Opslaan ===
def save_data(new_row):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facturen (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jaar INTEGER,
                maand INTEGER,
                perceel INTEGER,
                vervoerder TEXT,
                vaste_kosten REAL,
                variabele_kosten REAL,
                ritten_besteld INTEGER,
                ritten_geannuleerd INTEGER,
                ritten_loos INTEGER,
                ritten_uitgevoerd INTEGER,
                routes INTEGER
            );
        """)
        cursor.execute("""
            INSERT INTO facturen 
            (jaar, maand, perceel, vervoerder, vaste_kosten, variabele_kosten, 
             ritten_besteld, ritten_geannuleerd, ritten_loos, ritten_uitgevoerd, routes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_row["Jaar"], new_row["Maand"], new_row["Perceel"], new_row["Vervoerder"],
            new_row["VasteKosten"], new_row["VariabeleKosten"], new_row["RittenBesteld"],
            new_row["RittenGeannuleerd"], new_row["RittenLoos"], new_row["RittenUitgevoerd"],
            new_row["Routes"]
        ))
        conn.commit()
    st.success("Factuurgegevens opgeslagen!")

tab1, tab2, tab3 = st.tabs(["📥 Basisfactuur invoer", "📝 Afwijkingen invoeren", "⚙️ KPI Parameters"])

with tab1:
    st.title("📊 Factuurbasis Invoer Perceelrapportage")

    # Sidebar voor maand en jaar
    with st.sidebar:
        st.header("Instellingen")
        today = datetime.today()
        jaar = st.selectbox("Jaar", list(range(2024, today.year + 2)), index=1)
        maand = st.selectbox("Maand", list(range(1, 13)), index=today.month - 1)
        perceel = st.selectbox("Perceel", [2, 3, 4])
        vervoerder = st.selectbox("Vervoerder", ["WdK", "connexxion"])

    st.subheader("1️⃣ Invoer basisgegevens factuur")

    form = st.form("factuurbasis_form", clear_on_submit=True)
    with form:
        vaste_kosten = st.number_input("💶 Vaste kosten", min_value=0.0, step=100.0, format="%f", key="vaste_kosten")
        variabele_kosten = st.number_input("💶 Variabele kosten", min_value=0.0, step=100.0, format="%f", key="variabele_kosten")

        st.markdown("---")
        st.markdown("### 🚐 Ritten")
        ritten_besteld = st.number_input("Aantal bestelde ritten", min_value=0, step=1, key="ritten_besteld")
        ritten_geannuleerd = st.number_input("Aantal geannuleerde ritten", min_value=0, step=1, key="ritten_geannuleerd")
        ritten_loos = st.number_input("Aantal loos gemelde ritten", min_value=0, step=1, key="ritten_loos")
        ritten_uitgevoerd = st.number_input("Aantal uitgevoerde ritten", min_value=0, step=1, key="ritten_uitgevoerd")

        st.markdown("---")
        st.markdown("### 🧭 Routes")
        aantal_routes = st.number_input("Aantal routes", min_value=0, step=1, key="routes")

        submitted = st.form_submit_button("Opslaan")
        if submitted:
            nieuwe_row = {
                "Jaar": jaar,
                "Maand": maand,
                "Perceel": perceel,
                "Vervoerder": vervoerder,
                "VasteKosten": vaste_kosten,
                "VariabeleKosten": variabele_kosten,
                "RittenBesteld": ritten_besteld,
                "RittenGeannuleerd": ritten_geannuleerd,
                "RittenLoos": ritten_loos,
                "RittenUitgevoerd": ritten_uitgevoerd,
                "Routes": aantal_routes
            }
            save_data(nieuwe_row)

    # Rapportage tonen
    st.subheader("2️⃣ Ingevoerde factuurgegevens")
    data = load_data()

    if not data.empty:
        edited_data = st.data_editor(data, num_rows="dynamic", use_container_width=True)
        if st.button("Wijzigingen opslaan"):
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM facturen")
                for _, row in edited_data.iterrows():
                    cursor.execute("""
                        INSERT INTO facturen 
                        (jaar, maand, perceel, vervoerder, vaste_kosten, variabele_kosten, 
                         ritten_besteld, ritten_geannuleerd, ritten_loos, ritten_uitgevoerd, routes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row["jaar"], row["maand"], row["perceel"], row["vervoerder"],
                        row["vaste_kosten"], row["variabele_kosten"], row["ritten_besteld"],
                        row["ritten_geannuleerd"], row["ritten_loos"], row["ritten_uitgevoerd"],
                        row["routes"]
                    ))
                conn.commit()
            st.success("Wijzigingen opgeslagen.")
    else:
        st.info("Nog geen invoer beschikbaar.")

with tab2:
    st.subheader("Selecteer een factuur om afwijkingen toe te voegen")

    data = load_data()
    if not data.empty:
        select_index = st.selectbox(
            "Factuurselectie:",
            data.index,
            format_func=lambda i: f"{data.loc[i, 'jaar']}-{data.loc[i, 'maand']} | Perceel {data.loc[i, 'perceel']} - {data.loc[i, 'vervoerder']}"
        )
        factuur_id = int(data.loc[select_index, "id"])
        
        # Validate factuur_id before proceeding
        if pd.isna(factuur_id) or factuur_id <= 0:
            st.error("Geen geldige factuur geselecteerd. Selecteer een factuur voordat u doorgaat.")
            st.stop()

        # Toon basisgegevens van de geselecteerde factuur
        st.markdown("### 📊 Basisgegevens factuur")
        selected_factuur = data.loc[select_index]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Vaste kosten", f"€ {selected_factuur['vaste_kosten']:.2f}")
            st.metric("Variabele kosten", f"€ {selected_factuur['variabele_kosten']:.2f}")
        with col2:
            st.metric("Ritten besteld", int(selected_factuur['ritten_besteld']))
            st.metric("Ritten uitgevoerd", int(selected_factuur['ritten_uitgevoerd']))
            st.metric("Ritten geannuleerd", int(selected_factuur['ritten_geannuleerd']))
        with col3:
            st.metric("Ritten loos", int(selected_factuur['ritten_loos']))
            st.metric("Aantal routes", int(selected_factuur['routes']))
        
        st.markdown("---")

        st.markdown("### 🛠️ Invoer afwijkingen (aantallen)")
        with st.form("afwijking_form"):
            afwijkingen = {
                "controle_bestelling_sw": st.number_input("Controle Bestelling ook in SW", min_value=0, step=1),
                "controle_gegevens_levering": st.number_input("Controle levering data afwijking", min_value=0, step=1),
                "controle_stiptheid": st.number_input("Controle stiptheid", min_value=0, step=1),
                "controle_indicaties": st.number_input("Controle indicatie(s)", min_value=0, step=1),
                "controle_reistijd": st.number_input("Controle Overschrijden reistijd", min_value=0, step=1),
                "controle_dubbel_factuur": st.number_input("Controle Ritten dubbel op factuur", min_value=0, step=1),
                "controle_lege_routes": st.number_input("Controle Routes zonder reizigers", min_value=0, step=1),
                "controle_afwezig_melding": st.number_input("Controle Tijdig afwezig gemeld ritten", min_value=0, step=1)
            }

            submitted = st.form_submit_button("Afwijkingen opslaan")
            if submitted:
                with sqlite3.connect(DB_FILE) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS afwijkingen (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            factuur_id INTEGER UNIQUE,
                            controle_bestelling_sw INTEGER,
                            controle_gegevens_levering INTEGER,
                            controle_stiptheid INTEGER,
                            controle_indicaties INTEGER,
                            controle_reistijd INTEGER,
                            controle_dubbel_factuur INTEGER,
                            controle_lege_routes INTEGER,
                            controle_afwezig_melding INTEGER,
                            FOREIGN KEY (factuur_id) REFERENCES facturen(id)
                        )
                    """)
                    # Validate factuur_id before database operations
                    if not factuur_id or factuur_id <= 0:
                        st.error("Factuur ID is niet geldig. Kan geen afwijkingen opslaan.")
                        st.stop()
                    
                    # Check if a record already exists for this factuur_id
                    cursor.execute("SELECT COUNT(*) FROM afwijkingen WHERE factuur_id = ?", (factuur_id,))
                    exists = cursor.fetchone()[0] > 0
                    
                    # Debug: print the factuur_id value
                    st.write(f"DEBUG: factuur_id = {factuur_id} (type: {type(factuur_id)})")
                    st.write(f"DEBUG: exists = {exists}")
                     
                    if exists:
                        # Update existing record
                        st.write(f"DEBUG: Updating existing record for factuur_id = {factuur_id}")
                        cursor.execute("""
                            UPDATE afwijkingen SET
                                controle_bestelling_sw = ?,
                                controle_gegevens_levering = ?,
                                controle_stiptheid = ?,
                                controle_indicaties = ?,
                                controle_reistijd = ?,
                                controle_dubbel_factuur = ?,
                                controle_lege_routes = ?,
                                controle_afwezig_melding = ?
                            WHERE factuur_id = ?
                        """, (
                            afwijkingen["controle_bestelling_sw"],
                            afwijkingen["controle_gegevens_levering"],
                            afwijkingen["controle_stiptheid"],
                            afwijkingen["controle_indicaties"],
                            afwijkingen["controle_reistijd"],
                            afwijkingen["controle_dubbel_factuur"],
                            afwijkingen["controle_lege_routes"],
                            afwijkingen["controle_afwezig_melding"],
                            factuur_id
                        ))
                    else:
                        # Insert new record with validated factuur_id
                        st.write(f"DEBUG: Inserting new record for factuur_id = {factuur_id}")
                        cursor.execute("""
                            INSERT INTO afwijkingen (
                                factuur_id, controle_bestelling_sw, controle_gegevens_levering,
                                controle_stiptheid, controle_indicaties, controle_reistijd,
                                controle_dubbel_factuur, controle_lege_routes, controle_afwezig_melding
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            factuur_id,
                            afwijkingen["controle_bestelling_sw"],
                            afwijkingen["controle_gegevens_levering"],
                            afwijkingen["controle_stiptheid"],
                            afwijkingen["controle_indicaties"],
                            afwijkingen["controle_reistijd"],
                            afwijkingen["controle_dubbel_factuur"],
                            afwijkingen["controle_lege_routes"],
                            afwijkingen["controle_afwezig_melding"]
                        ))
                    conn.commit()
                st.success("Afwijkingen opgeslagen voor geselecteerde factuur.")
                
                # Toon KPI berekeningen
                st.markdown("### 📊 KPI Berekeningen")
                
                try:
                    with sqlite3.connect(DB_FILE) as conn:
                        kpi_params = pd.read_sql_query("SELECT * FROM kpi_parameters", conn)
                    
                    if not kpi_params.empty:
                        kpi_results = []
                        
                        # Map afwijkingen naar KPI parameters
                        afwijking_mapping = {
                            'controle_bestelling_sw': 'controle_bestelling_sw',
                            'controle_gegevens_levering': 'controle_levering',
                            'controle_stiptheid': 'controle_stiptheid',
                            'controle_indicaties': 'controle_indicaties',
                            'controle_reistijd': 'controle_reistijd',
                            'controle_dubbel_factuur': 'controle_dubbel_factuur',
                            'controle_lege_routes': 'controle_lege_routes',
                            'controle_afwezig_melding': 'controle_afwezig_melding'
                        }
                        
                        for afwijking_key, kpi_key in afwijking_mapping.items():
                            kpi_row = kpi_params[kpi_params['afwijking_type'] == kpi_key]
                            if not kpi_row.empty:
                                percentage = kpi_row.iloc[0]['percentage']
                                basis_type = kpi_row.iloc[0]['berekenings_basis']
                                
                                # Get actual counts
                                afwijking_count = afwijkingen.get(f"controle_{afwijking_key}", 0)
                                basis_count = get_basis_count(data.loc[select_index], basis_type)
                                
                                # Calculate KPI
                                actual_percentage = (afwijking_count / basis_count * 100) if basis_count > 0 else 0
                                meets_target = actual_percentage <= percentage
                                
                                kpi_results.append({
                                    'Afwijking': afwijking_key.replace('_', ' ').title(),
                                    'Aantal': afwijking_count,
                                    'Basis': basis_count,
                                    'Percentage': f"{actual_percentage:.1f}%",
                                    'Doel': f"{percentage}%",
                                    'Status': "✅ Voldoet" if meets_target else "❌ Overschreden"
                                })
                        
                        if kpi_results:
                            st.dataframe(pd.DataFrame(kpi_results), use_container_width=True)
                    else:
                        st.info("Configureer eerst KPI parameters in het KPI Parameters tab.")
                        
                except Exception as e:
                    st.info("Configureer eerst KPI parameters in het KPI Parameters tab.")
                    
    else:
        st.info("Er zijn nog geen facturen beschikbaar voor afwijkingsinvoer.")

def calculate_kpi_score(afwijking_count, basis_count, percentage):
    """Bereken KPI score op basis van afwijkingen en basis"""
    if basis_count == 0:
        return 0.0
    actual_percentage = (afwijking_count / basis_count) * 100
    return actual_percentage, actual_percentage <= percentage

def get_basis_count(factuur_data, basis_type):
    """Haal het juiste aantal op basis van het basis type"""
    basis_mapping = {
        "Ritten besteld": factuur_data['ritten_besteld'],
        "Ritten uitgevoerd": factuur_data['ritten_uitgevoerd'],
        "Ritten geannuleerd": factuur_data['ritten_geannuleerd'],
        "Ritten loos": factuur_data['ritten_loos'],
        "Routes": factuur_data['routes']
    }
    return basis_mapping.get(basis_type, 1)

with tab3:
    st.subheader("⚙️ KPI Parameters Configuratie")
    st.markdown("### 📊 Definieer percentages en berekeningsgrondslagen per afwijking")

    # KPI Parameters configuratie
    with st.form("kpi_parameters_form"):
        
        # KPI configuratie voor elke afwijking
        kpi_config = {}
        
        st.markdown("#### 🔍 Controle Bestelling ook in SW")
        col1, col2 = st.columns(2)
        with col1:
            kpi_config['controle_bestelling_sw_percentage'] = st.number_input(
                "Percentage (%)",
                min_value=0.0,
                max_value=100.0,
                value=5.0,
                step=0.5,
                key="kpi_bestelling_percentage"
            )
        with col2:
            kpi_config['controle_bestelling_sw_basis'] = st.selectbox(
                "Berekeningsgrondslag",
                ["Ritten besteld", "Ritten uitgevoerd", "Ritten geannuleerd", "Ritten loos"],
                index=0,
                key="kpi_bestelling_basis"
            )

        st.markdown("#### 📦 Controle levering data afwijking")
        col1, col2 = st.columns(2)
        with col1:
            kpi_config['controle_levering_percentage'] = st.number_input(
                "Percentage (%)",
                min_value=0.0,
                max_value=100.0,
                value=3.0,
                step=0.5,
                key="kpi_levering_percentage"
            )
        with col2:
            kpi_config['controle_levering_basis'] = st.selectbox(
                "Berekeningsgrondslag",
                ["Ritten besteld", "Ritten uitgevoerd", "Ritten geannuleerd", "Ritten loos"],
                index=1,
                key="kpi_levering_basis"
            )

        st.markdown("#### ⏰ Controle stiptheid")
        col1, col2 = st.columns(2)
        with col1:
            kpi_config['controle_stiptheid_percentage'] = st.number_input(
                "Percentage (%)",
                min_value=0.0,
                max_value=100.0,
                value=2.0,
                step=0.5,
                key="kpi_stiptheid_percentage"
            )
        with col2:
            kpi_config['controle_stiptheid_basis'] = st.selectbox(
                "Berekeningsgrondslag",
                ["Ritten besteld", "Ritten uitgevoerd", "Ritten geannuleerd", "Ritten loos"],
                index=1,
                key="kpi_stiptheid_basis"
            )

        st.markdown("#### 🎯 Controle indicatie(s)")
        col1, col2 = st.columns(2)
        with col1:
            kpi_config['controle_indicaties_percentage'] = st.number_input(
                "Percentage (%)",
                min_value=0.0,
                max_value=100.0,
                value=1.5,
                step=0.5,
                key="kpi_indicaties_percentage"
            )
        with col2:
            kpi_config['controle_indicaties_basis'] = st.selectbox(
                "Berekeningsgrondslag",
                ["Ritten besteld", "Ritten uitgevoerd", "Ritten geannuleerd", "Ritten loos"],
                index=1,
                key="kpi_indicaties_basis"
            )

        st.markdown("#### 🕐 Controle Overschrijden reistijd")
        col1, col2 = st.columns(2)
        with col1:
            kpi_config['controle_reistijd_percentage'] = st.number_input(
                "Percentage (%)",
                min_value=0.0,
                max_value=100.0,
                value=2.5,
                step=0.5,
                key="kpi_reistijd_percentage"
            )
        with col2:
            kpi_config['controle_reistijd_basis'] = st.selectbox(
                "Berekeningsgrondslag",
                ["Ritten besteld", "Ritten uitgevoerd", "Ritten geannuleerd", "Ritten loos"],
                index=1,
                key="kpi_reistijd_basis"
            )

        st.markdown("#### 🔄 Controle Ritten dubbel op factuur")
        col1, col2 = st.columns(2)
        with col1:
            kpi_config['controle_dubbel_factuur_percentage'] = st.number_input(
                "Percentage (%)",
                min_value=0.0,
                max_value=100.0,
                value=1.0,
                step=0.5,
                key="kpi_dubbel_percentage"
            )
        with col2:
            kpi_config['controle_dubbel_factuur_basis'] = st.selectbox(
                "Berekeningsgrondslag",
                ["Ritten besteld", "Ritten uitgevoerd", "Ritten geannuleerd", "Ritten loos"],
                index=1,
                key="kpi_dubbel_basis"
            )

        st.markdown("#### 🛤️ Controle Routes zonder reizigers")
        col1, col2 = st.columns(2)
        with col1:
            kpi_config['controle_lege_routes_percentage'] = st.number_input(
                "Percentage (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.5,
                step=0.5,
                key="kpi_lege_percentage"
            )
        with col2:
            kpi_config['controle_lege_routes_basis'] = st.selectbox(
                "Berekeningsgrondslag",
                ["Ritten besteld", "Ritten uitgevoerd", "Ritten geannuleerd", "Ritten loos", "Routes"],
                index=4,
                key="kpi_lege_basis"
            )

        st.markdown("#### 📞 Controle Tijdig afwezig gemeld ritten")
        col1, col2 = st.columns(2)
        with col1:
            kpi_config['controle_afwezig_melding_percentage'] = st.number_input(
                "Percentage (%)",
                min_value=0.0,
                max_value=100.0,
                value=1.0,
                step=0.5,
                key="kpi_afwezig_percentage"
            )
        with col2:
            kpi_config['controle_afwezig_melding_basis'] = st.selectbox(
                "Berekeningsgrondslag",
                ["Ritten besteld", "Ritten uitgevoerd", "Ritten geannuleerd", "Ritten loos"],
                index=1,
                key="kpi_afwezig_basis"
            )

        submitted = st.form_submit_button("KPI Parameters Opslaan")
        
        if submitted:
            # Opslaan KPI parameters
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS kpi_parameters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        afwijking_type TEXT UNIQUE,
                        percentage REAL,
                        berekenings_basis TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert or update KPI parameters
                for afwijking, config in kpi_config.items():
                    if 'percentage' in afwijking:
                        afwijking_type = afwijking.replace('_percentage', '')
                        cursor.execute("""
                            INSERT OR REPLACE INTO kpi_parameters (afwijking_type, percentage, berekenings_basis)
                            VALUES (?, ?, ?)
                        """, (
                            afwijking_type,
                            kpi_config[afwijking],
                            kpi_config[afwijking.replace('_percentage', '_basis')]
                        ))
                
                conn.commit()
            st.success("KPI parameters succesvol opgeslagen!")

    # Toon huidige KPI configuratie
    st.markdown("### 📋 Huidige KPI Configuratie")
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            kpi_data = pd.read_sql_query("SELECT * FROM kpi_parameters ORDER BY afwijking_type", conn)
        
        if not kpi_data.empty:
            st.dataframe(
                kpi_data[['afwijking_type', 'percentage', 'berekenings_basis']].rename(columns={
                    'afwijking_type': 'Afwijking Type',
                    'percentage': 'Percentage (%)',
                    'berekenings_basis': 'Berekeningsgrondslag'
                }),
                use_container_width=True
            )
        else:
            st.info("Nog geen KPI parameters geconfigureerd.")
            
    except Exception as e:
        st.info("Nog geen KPI parameters geconfigureerd.")