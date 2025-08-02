import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io
from PIL import Image
import base64
import numpy as np

# === Configuratie ===
DB_FILE = "factuurcontrole.db"

# === Database functies ===
def load_data():
    """Laad alle factuurgegevens"""
    with sqlite3.connect(DB_FILE) as conn:
        # Ensure all facturen have corresponding afwijkingen records
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO afwijkingen (factuur_id, controle_bestelling_sw, controle_gegevens_levering, 
            controle_stiptheid, controle_indicaties, controle_reistijd, controle_dubbel_factuur, 
            controle_lege_routes, controle_afwezig_melding)
            SELECT f.id, 0, 0, 0, 0, 0, 0, 0, 0
            FROM facturen f
            WHERE NOT EXISTS (SELECT 1 FROM afwijkingen a WHERE a.factuur_id = f.id)
        """)
        conn.commit()
        
        query = """
        SELECT f.*, 
               COALESCE(a.controle_bestelling_sw, 0) as controle_bestelling_sw,
               COALESCE(a.controle_gegevens_levering, 0) as controle_gegevens_levering,
               COALESCE(a.controle_stiptheid, 0) as controle_stiptheid,
               COALESCE(a.controle_indicaties, 0) as controle_indicaties,
               COALESCE(a.controle_reistijd, 0) as controle_reistijd,
               COALESCE(a.controle_dubbel_factuur, 0) as controle_dubbel_factuur,
               COALESCE(a.controle_lege_routes, 0) as controle_lege_routes,
               COALESCE(a.controle_afwezig_melding, 0) as controle_afwezig_melding
        FROM facturen f
        LEFT JOIN afwijkingen a ON f.id = a.factuur_id
        """
        df = pd.read_sql_query(query, conn)
    return df

def load_kpi_parameters():
    """Laad KPI parameters"""
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query("SELECT * FROM kpi_parameters", conn)
    return df

# === KPI Berekeningen ===
def calculate_kpi_scores(factuur_data, kpi_params):
    """Bereken KPI scores voor een factuur"""
    kpi_results = []
    
    afwijking_mapping = {
        'bestelling_sw': 'controle_bestelling_sw',
        'gegevens_levering': 'controle_gegevens_levering',
        'stiptheid': 'controle_stiptheid',
        'indicaties': 'controle_indicaties',
        'reistijd': 'controle_reistijd',
        'dubbel_factuur': 'controle_dubbel_factuur',
        'lege_routes': 'controle_lege_routes',
        'afwezig_melding': 'controle_afwezig_melding'
    }
    
    for afwijking_key, kpi_key in afwijking_mapping.items():
        kpi_row = kpi_params[kpi_params['afwijking_type'] == kpi_key]
        if not kpi_row.empty:
            percentage = kpi_row.iloc[0]['percentage']
            basis_type = kpi_row.iloc[0]['berekenings_basis']
            
            # Get actual counts
            afwijking_count = factuur_data.get(f"controle_{afwijking_key}", 0)
            basis_count = get_basis_count(factuur_data, basis_type)
            
            # Calculate KPI
            actual_percentage = (afwijking_count / basis_count * 100) if basis_count > 0 else 0
            meets_target = actual_percentage <= percentage
            
            kpi_results.append({
                'afwijking': afwijking_key,
                'naam': afwijking_key.replace('_', ' ').replace('controle ', '').title(),
                'aantal': afwijking_count,
                'basis': basis_count,
                'percentage': actual_percentage,
                'doel': percentage,
                'status': 'GOED' if meets_target else 'AFWIJKING',
                'score': 100 if meets_target else max(0, 100 - (actual_percentage - percentage) * 10)
            })
    
    return kpi_results

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

# === Stoplight Model ===
def get_stoplight_color(score):
    """Bepaal stoplight kleur op basis van score"""
    if score >= 90:
        return "🟢"  # Groen
    elif score >= 70:
        return "🟡"  # Geel
    else:
        return "🔴"  # Rood

def create_stoplight_card(factuur_data, kpi_results):
    """Creëer een stoplight kaart voor een factuur"""
    overall_score = np.mean([kpi['score'] for kpi in kpi_results]) if kpi_results else 0
    
    card_html = f"""
    <div style="border: 2px solid #ddd; border-radius: 10px; padding: 15px; margin: 10px; background-color: #f9f9f9;">
        <h3>{get_stoplight_color(overall_score)} Factuur {factuur_data['jaar']}-{factuur_data['maand']}</h3>
        <p><strong>Perceel:</strong> {factuur_data['perceel']}</p>
        <p><strong>Vervoerder:</strong> {factuur_data['vervoerder']}</p>
        <p><strong>Totaal Score:</strong> {overall_score:.1f}%</p>
        <p><strong>Status:</strong> {"GOED" if overall_score >= 90 else "AANDACHT NODIG" if overall_score >= 70 else "ACTIE VEREIST"}</p>
    </div>
    """
    return card_html

# === Export functies ===
def export_dataframe_to_csv(df, filename):
    """Exporteer DataFrame naar CSV"""
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download als CSV",
        data=csv,
        file_name=filename,
        mime="text/csv"
    )

def export_plot_to_png(fig, filename):
    """Exporteer plot naar PNG zonder Chrome dependency"""
    # Gebruik Streamlit's native plotly_chart met download optie
    # Dit vermijdt Kaleido/Chrome dependency
    st.info("💡 Grafiek download is beschikbaar via de Plotly toolbar (camera icoon rechtsboven in de grafiek)")

# === Dashboard Filter (Sidebar) ===
def apply_dashboard_filters(data):
    """Apply dashboard filters in sidebar and return filtered dataframe"""
    st.sidebar.header("🔍 Dashboard Filters")
    
    # Jaar filter
    jaren = sorted([x for x in data['jaar'].unique() if x is not None])
    geselecteerde_jaren = st.sidebar.multiselect("Jaar", jaren, default=jaren, key="dashboard_filter_jaar")
    
    # Maand filter
    maanden = sorted([x for x in data['maand'].unique() if x is not None])
    geselecteerde_maanden = st.sidebar.multiselect("Maand", maanden, default=maanden, key="dashboard_filter_maand")
    
    # Perceel filter
    percelen = sorted([x for x in data['perceel'].unique() if x is not None])
    geselecteerde_percelen = st.sidebar.multiselect("Perceel", percelen, default=percelen, key="dashboard_filter_perceel")
    
    # Vervoerder filter
    vervoerders = sorted([x for x in data['vervoerder'].unique() if x is not None])
    geselecteerde_vervoerders = st.sidebar.multiselect("Vervoerder", vervoerders, default=vervoerders, key="dashboard_filter_vervoerder")
    
    # Filter data
    gefilterde_data = data[
        (data['jaar'].isin(geselecteerde_jaren)) &
        (data['maand'].isin(geselecteerde_maanden)) &
        (data['perceel'].isin(geselecteerde_percelen)) &
        (data['vervoerder'].isin(geselecteerde_vervoerders))
    ]
    
    return gefilterde_data

# === Analytics Filter (In-tab) ===
def apply_analytics_filters(data):
    """Apply analytics filters within the tab content and return filtered dataframe"""
    st.header("🔍 Analytics Filters")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        jaren = sorted([x for x in data['jaar'].unique() if x is not None])
        geselecteerde_jaren = st.multiselect("Jaar", jaren, default=jaren, key="analytics_filter_jaar")
    
    with col2:
        maanden = sorted([x for x in data['maand'].unique() if x is not None])
        geselecteerde_maanden = st.multiselect("Maand", maanden, default=maanden, key="analytics_filter_maand")
    
    with col3:
        percelen = sorted([x for x in data['perceel'].unique() if x is not None])
        geselecteerde_percelen = st.multiselect("Perceel", percelen, default=percelen, key="analytics_filter_perceel")
    
    with col4:
        vervoerders = sorted([x for x in data['vervoerder'].unique() if x is not None])
        geselecteerde_vervoerders = st.multiselect("Vervoerder", vervoerders, default=vervoerders, key="analytics_filter_vervoerder")
    
    # Filter data
    gefilterde_data = data[
        (data['jaar'].isin(geselecteerde_jaren)) &
        (data['maand'].isin(geselecteerde_maanden)) &
        (data['perceel'].isin(geselecteerde_percelen)) &
        (data['vervoerder'].isin(geselecteerde_vervoerders))
    ]
    
    return gefilterde_data

# === Dashboard Layout ===
def show_dashboard():
    """Toon het hoofddashboard met stoplight model"""
    st.title("📊 Factuurcontrole Dashboard")
    
    # Laad data
    data = load_data()
    kpi_params = load_kpi_parameters()
    
    if data.empty:
        st.warning("Geen factuurgegevens gevonden. Voer eerst factuurgegevens in.")
        return
    
    if kpi_params.empty:
        st.warning("Geen KPI parameters gevonden. Configureer eerst KPI parameters.")
        return
    
    # Apply dashboard filters (sidebar)
    gefilterde_data = apply_dashboard_filters(data)
    
    if gefilterde_data.empty:
        st.warning("Geen data gevonden met de geselecteerde filters.")
        return
    
    # Stoplight overzicht
    st.header("🚦 Stoplight Overzicht")
    
    # Bereken scores voor alle facturen
    facturen_scores = []
    for _, factuur in gefilterde_data.iterrows():
        kpi_results = calculate_kpi_scores(factuur, kpi_params)
        overall_score = np.mean([kpi['score'] for kpi in kpi_results]) if kpi_results else 0
        
        facturen_scores.append({
            'jaar': factuur['jaar'],
            'maand': factuur['maand'],
            'perceel': factuur['perceel'],
            'vervoerder': factuur['vervoerder'],
            'score': overall_score,
            'status': 'GOED' if overall_score >= 90 else 'AANDACHT' if overall_score >= 70 else 'ACTIE',
            'vaste_kosten': factuur['vaste_kosten'],
            'variabele_kosten': factuur['variabele_kosten'],
            'ritten_besteld': factuur['ritten_besteld'],
            'ritten_uitgevoerd': factuur['ritten_uitgevoerd']
        })
    
    facturen_df = pd.DataFrame(facturen_scores)
    
    # Toon stoplight kaarten
    cols = st.columns(3)
    for idx, (_, factuur) in enumerate(gefilterde_data.iterrows()):
        kpi_results = calculate_kpi_scores(factuur, kpi_params)
        overall_score = np.mean([kpi['score'] for kpi in kpi_results]) if kpi_results else 0
        
        col_idx = idx % 3
        with cols[col_idx]:
            st.markdown(create_stoplight_card(factuur, kpi_results), unsafe_allow_html=True)
            
            # KPI details expander
            with st.expander("📊 Details"):
                for kpi in kpi_results:
                    st.write(f"{get_stoplight_color(kpi['score'])} {kpi['naam']}: {kpi['percentage']:.1f}% (doel: {kpi['doel']}%)")
    
    # Export knoppen
    st.header("📤 Export")
    col1, col2 = st.columns(2)
    with col1:
        export_dataframe_to_csv(facturen_df, f"factuur_scores_{datetime.now().strftime('%Y%m%d')}.csv")
    with col2:
        # Maak een samenvattende tabel
        summary_df = facturen_df[['jaar', 'maand', 'perceel', 'vervoerder', 'score', 'status']]
        st.dataframe(summary_df, use_container_width=True)

def show_analytics():
    """Toon analytics pagina met grafieken"""
    st.title("📈 Factuur Analytics")
    
    # Laad data
    data = load_data()
    kpi_params = load_kpi_parameters()
    
    if data.empty:
        st.warning("Geen factuurgegevens gevonden.")
        return
    
    # Apply analytics filters (within tab content)
    gefilterde_data = apply_analytics_filters(data)
    
    # Bereken scores
    facturen_scores = []
    for _, factuur in gefilterde_data.iterrows():
        kpi_results = calculate_kpi_scores(factuur, kpi_params)
        overall_score = np.mean([kpi['score'] for kpi in kpi_results]) if kpi_results else 0
        
        # Create year-month combination for proper chronological ordering
        year_month = f"{factuur['jaar']}-{factuur['maand']:02d}"
        
        facturen_scores.append({
            'jaar': factuur['jaar'],
            'maand': factuur['maand'],
            'jaar_maand': year_month,
            'perceel': factuur['perceel'],
            'vervoerder': factuur['vervoerder'],
            'score': overall_score,
            'vaste_kosten': factuur['vaste_kosten'],
            'variabele_kosten': factuur['variabele_kosten'],
            'ritten_besteld': factuur['ritten_besteld'],
            'ritten_uitgevoerd': factuur['ritten_uitgevoerd']
        })
    
    facturen_df = pd.DataFrame(facturen_scores)
    
    # Sort by year and month for proper chronological order
    facturen_df = facturen_df.sort_values(['jaar', 'maand'])
    
    # Grafieken
    st.header("📊 Prestatie Overzicht")
    
    # 1. Score trend over tijd
    fig_trend = px.line(
        facturen_df,
        x='jaar_maand',
        y='score',
        color='vervoerder',
        title='Kwaliteitsscore per maand (chronologisch)',
        labels={'score': 'Kwaliteitsscore (%)', 'jaar_maand': 'Jaar-Maand'}
    )
    
    # Ensure consistent 1-month increments
    fig_trend.update_xaxes(
        tickangle=-45,
        tickmode='linear',
        dtick='M1',  # 1 month increments
        tickformat='%Y-%m'  # Format as YYYY-MM
    )
    
    st.plotly_chart(fig_trend, use_container_width=True)
    
    # 2. Vergelijking vervoerders over tijd
    fig_vervoerder = px.box(
        facturen_df,
        x='jaar_maand',
        y='score',
        color='vervoerder',
        title='Kwaliteitsscore per vervoerder over tijd',
        labels={'score': 'Kwaliteitsscore (%)', 'jaar_maand': 'Jaar-Maand'}
    )
    
    # Ensure consistent 1-month increments
    fig_vervoerder.update_xaxes(
        tickangle=-45,
        tickmode='linear',
        dtick='M1',  # 1 month increments
        tickformat='%Y-%m'  # Format as YYYY-MM
    )
    
    st.plotly_chart(fig_vervoerder, use_container_width=True)
    
    # 3. Kosten analyse per maand
    fig_kosten = px.bar(
        facturen_df,
        x='jaar_maand',
        y='variabele_kosten',
        color='vervoerder',
        title='Variabele kosten per maand',
        labels={'variabele_kosten': 'Variabele kosten (€)', 'jaar_maand': 'Jaar-Maand'}
    )
    
    # Ensure consistent 1-month increments
    fig_kosten.update_xaxes(
        tickangle=-45,
        tickmode='linear',
        dtick='M1',  # 1 month increments
        tickformat='%Y-%m'  # Format as YYYY-MM
    )
    
    st.plotly_chart(fig_kosten, use_container_width=True)
    
    # 4. Perceel performance
    fig_perceel = px.bar(
        facturen_df,
        x='perceel',
        y='score',
        color='vervoerder',
        title='Kwaliteitsscore per perceel',
        labels={'score': 'Gemiddelde kwaliteitsscore (%)', 'perceel': 'Perceel'}
    )
    st.plotly_chart(fig_perceel, use_container_width=True)
    
    # Export knoppen
    st.header("📤 Export")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        export_dataframe_to_csv(facturen_df, f"analytics_data_{datetime.now().strftime('%Y%m%d')}.csv")
    
    with col2:
        export_plot_to_png(fig_trend, f"trend_chart_{datetime.now().strftime('%Y%m%d')}.png")
    
    with col3:
        export_plot_to_png(fig_vervoerder, f"vervoerder_chart_{datetime.now().strftime('%Y%m%d')}.png")
    
    with col4:
        export_plot_to_png(fig_perceel, f"perceel_chart_{datetime.now().strftime('%Y%m%d')}.png")

# === Hoofdapplicatie ===
def main():
    st.set_page_config(
        page_title="Factuurcontrole Dashboard",
        page_icon="📊",
        layout="wide"
    )
    
    # Tabs
    tab1, tab2 = st.tabs(["🚦 Dashboard", "📈 Analytics"])
    
    with tab1:
        show_dashboard()
    
    with tab2:
        show_analytics()

if __name__ == "__main__":
    main()