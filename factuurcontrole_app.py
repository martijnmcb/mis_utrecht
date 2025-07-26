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

tab1, tab2 = st.tabs(["📥 Basisfactuur invoer", "📝 Afwijkingen invoeren"])

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
        factuur_id = data.loc[select_index, "id"]

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
                            factuur_id INTEGER,
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
    else:
        st.info("Er zijn nog geen facturen beschikbaar voor afwijkingsinvoer.")