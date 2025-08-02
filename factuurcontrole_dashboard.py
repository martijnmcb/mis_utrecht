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
        'controle_bestelling_sw': 'controle_bestelling_sw',
        'controle_gegevens_levering': 'controle_gegevens_levering',
        'controle_stiptheid': 'controle_stiptheid',
        'controle_indicaties': 'controle_indicaties',
        'controle_reistijd': 'controle_reistijd',
        'controle_dubbel_factuur': 'controle_dubbel_factuur',
        'controle_lege_routes': 'controle_lege_routes',
        'controle_afwezig_melding': 'controle_afwezig_melding'
    }
    
    # Convert kpi_params to DataFrame if it's a list
    if isinstance(kpi_params, list):
        kpi_params_df = pd.DataFrame(kpi_params)
    else:
        kpi_params_df = kpi_params
    
    for afwijking_key, kpi_key in afwijking_mapping.items():
        kpi_row = kpi_params_df[kpi_params_df['afwijking_type'] == kpi_key]
        if not kpi_row.empty:
            percentage = kpi_row.iloc[0]['percentage']
            basis_type = kpi_row.iloc[0]['berekenings_basis']
            
            # Get actual counts
            afwijking_count = factuur_data.get(kpi_key, 0)
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
        "Ritten besteld": factuur_data.get('ritten_besteld', 0),
        "Ritten uitgevoerd": factuur_data.get('ritten_uitgevoerd', 0),
        "Ritten geannuleerd": factuur_data.get('ritten_geannuleerd', 0),
        "Ritten loos": factuur_data.get('ritten_loos', 0),
        "Routes": factuur_data.get('routes', 0)
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

def create_traffic_light_display(score):
    """Creëer een eenvoudige verkeerslicht visualisatie met Streamlit componenten"""
    if score >= 90:
        color = "🟢"
        status = "GOED"
    elif score >= 70:
        color = "🟡"
        status = "AANDACHT NODIG"
    else:
        color = "🔴"
        status = "ACTIE VEREIST"
    
    return color, status

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
    #st.info("💡 Grafiek download is beschikbaar via de Plotly toolbar (camera icoon rechtsboven in de grafiek)")

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

# === Stacked Bar Graph Filter ===
def apply_stacked_bar_filters(data):
    """Apply filters specifically for the stacked bar graph tab"""
    st.header("🔍 Stacked Bar Graph Filters")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        jaren = sorted([x for x in data['jaar'].unique() if x is not None])
        geselecteerde_jaren = st.multiselect("Jaar", jaren, default=jaren, key="stacked_bar_filter_jaar")
    
    with col2:
        maanden = sorted([x for x in data['maand'].unique() if x is not None])
        geselecteerde_maanden = st.multiselect("Maand", maanden, default=maanden, key="stacked_bar_filter_maand")
    
    with col3:
        percelen = sorted([x for x in data['perceel'].unique() if x is not None])
        geselecteerde_percelen = st.multiselect("Perceel", percelen, default=percelen, key="stacked_bar_filter_perceel")
    
    with col4:
        vervoerders = sorted([x for x in data['vervoerder'].unique() if x is not None])
        geselecteerde_vervoerders = st.multiselect("Vervoerder", vervoerders, default=vervoerders, key="stacked_bar_filter_vervoerder")
    
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
            # Use traffic light display
            color, status = create_traffic_light_display(overall_score)
            
            st.markdown(f"""
            <div style="border: 2px solid #ddd; border-radius: 10px; padding: 15px; margin: 10px; background-color: #f9f9f9;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 2em;">{color}</span>
                    <div>
                        <h3 style="margin: 0; color: #333;">Factuur {factuur['jaar']}-{factuur['maand']}</h3>
                        <p style="margin: 5px 0;"><strong>Perceel:</strong> {factuur['perceel']}</p>
                        <p style="margin: 5px 0;"><strong>Vervoerder:</strong> {factuur['vervoerder']}</p>
                        <p style="margin: 5px 0;"><strong>Totaal Score:</strong> {overall_score:.1f}%</p>
                        <p style="margin: 5px 0;"><strong>Status:</strong> {status}</p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # KPI details expander
            with st.expander("📊 Details"):
                for kpi in kpi_results:
                    st.write(f"{get_stoplight_color(kpi['score'])} {kpi['naam']}: {kpi['percentage']:.1f}% (doel: {kpi['doel']}%)")
    
    # Export knoppen
    st.header("📤 Export")
    col1, col2 = st.columns(2)
    with col2:
        export_dataframe_to_csv(facturen_df, f"factuur_scores_{datetime.now().strftime('%Y%m%d')}.csv")
    with col1:
        # Maak een samenvattende tabel
        summary_df = facturen_df[['jaar', 'maand', 'perceel', 'vervoerder', 'score', 'status']]
        st.dataframe(summary_df, use_container_width=True)
    
    # Factuur data met afwijkingen
    st.header("📋 Factuur Data met Afwijkingen")
    
    # Selecteer relevante kolommen voor weergave
    factuur_afwijkingen_cols = [
        'jaar', 'maand', 'perceel', 'vervoerder', 'vaste_kosten', 'variabele_kosten',
        'ritten_besteld', 'ritten_uitgevoerd', 'ritten_geannuleerd', 'ritten_loos',
        'routes', 'controle_bestelling_sw', 'controle_gegevens_levering',
        'controle_stiptheid', 'controle_indicaties', 'controle_reistijd',
        'controle_dubbel_factuur', 'controle_lege_routes', 'controle_afwezig_melding'
    ]
    
    # Filter alleen de kolommen die daadwerkelijk bestaan in de data
    available_cols = [col for col in factuur_afwijkingen_cols if col in gefilterde_data.columns]
    display_df = gefilterde_data[available_cols].copy()
    
    # Geef kolommen Nederlandse namen voor betere leesbaarheid
    column_mapping = {
        'jaar': 'Jaar',
        'maand': 'Maand',
        'perceel': 'Perceel',
        'vervoerder': 'Vervoerder',
        'vaste_kosten': 'Vaste Kosten (€)',
        'variabele_kosten': 'Variabele Kosten (€)',
        'ritten_besteld': 'Ritten Besteld',
        'ritten_uitgevoerd': 'Ritten Uitgevoerd',
        'ritten_geannuleerd': 'Ritten Geannuleerd',
        'ritten_loos': 'Ritten Loos',
        'routes': 'Routes',
        'controle_bestelling_sw': 'Bestelling SW',
        'controle_gegevens_levering': 'Gegevens Levering',
        'controle_stiptheid': 'Stiptheid',
        'controle_indicaties': 'Indicaties',
        'controle_reistijd': 'Reistijd',
        'controle_dubbel_factuur': 'Dubbel Factuur',
        'controle_lege_routes': 'Lege Routes',
        'controle_afwezig_melding': 'Afwezig Melding'
    }
    
    display_df = display_df.rename(columns=column_mapping)
    
    # Toon de dataframe
    st.dataframe(display_df, use_container_width=True)
    
    # Export knop voor de volledige factuur data met afwijkingen
    export_dataframe_to_csv(display_df, f"factuur_afwijkingen_data_{datetime.now().strftime('%Y%m%d')}.csv")

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
    
    # Define color mapping for percelen
    color_map = {
        'Perceel 2': 'green',
        'Perceel 3': 'blue',
        'Perceel 4': 'red'
    }
    
    # 1. Score trend over tijd
    fig_trend = px.line(
        facturen_df,
        x='jaar_maand',
        y='score',
        color='perceel',
        title='Kwaliteitsscore per maand (chronologisch)',
        labels={'score': 'Kwaliteitsscore (%)', 'jaar_maand': 'Jaar-Maand'},
        color_discrete_map=color_map
    )
    
    # Ensure consistent 1-month increments
    fig_trend.update_xaxes(
        tickangle=-45,
        tickmode='linear',
        dtick='M1',  # 1 month increments
        tickformat='%Y-%m'  # Format as YYYY-MM
    )
    
    st.plotly_chart(fig_trend, use_container_width=True, key="trend_chart")
    
    # 2. Kwaliteitsscore per perceel over tijd (bar chart)
    fig_kwaliteit_perceel = px.bar(
        facturen_df,
        x='jaar_maand',
        y='score',
        color='perceel',
        title='Gemiddelde kwaliteitsscore per perceel over tijd',
        labels={'score': 'Gemiddelde kwaliteitsscore (%)', 'jaar_maand': 'Jaar-Maand'},
        color_discrete_map=color_map,
        barmode='group'
    )
    
    # Ensure consistent 1-month increments
    fig_kwaliteit_perceel.update_xaxes(
        tickangle=-45,
        tickmode='linear',
        dtick='M1',  # 1 month increments
        tickformat='%Y-%m'  # Format as YYYY-MM
    )
    
    st.plotly_chart(fig_kwaliteit_perceel, use_container_width=True, key="kwaliteit_perceel_chart")
    
    # 3. Kosten analyse per maand
    fig_kosten = px.bar(
        facturen_df,
        x='jaar_maand',
        y='variabele_kosten',
        color='perceel',
        title='Variabele kosten per maand',
        labels={'variabele_kosten': 'Variabele kosten (€)', 'jaar_maand': 'Jaar-Maand'},
        color_discrete_map=color_map
    )
    
    # Ensure consistent 1-month increments
    fig_kosten.update_xaxes(
        tickangle=-45,
        tickmode='linear',
        dtick='M1',  # 1 month increments
        tickformat='%Y-%m'  # Format as YYYY-MM
    )
    
    st.plotly_chart(fig_kosten, use_container_width=True, key="kosten_chart")
    
    # Export knoppen
    st.header("📤 Export")
    col1, col2 = st.columns(2)
    
    with col1:
        export_dataframe_to_csv(facturen_df, f"analytics_data_{datetime.now().strftime('%Y%m%d')}.csv")
    
    with col2:
        export_plot_to_png(fig_trend, f"trend_chart_{datetime.now().strftime('%Y%m%d')}.png")
    
    # Factuur data met afwijkingen
    st.header("📋 Factuur Data met Afwijkingen")
    
    # Selecteer relevante kolommen voor weergave
    factuur_afwijkingen_cols = [
        'jaar', 'maand', 'perceel', 'vervoerder', 'vaste_kosten', 'variabele_kosten',
        'ritten_besteld', 'ritten_uitgevoerd', 'ritten_geannuleerd', 'ritten_loos',
        'routes', 'controle_bestelling_sw', 'controle_gegevens_levering',
        'controle_stiptheid', 'controle_indicaties', 'controle_reistijd',
        'controle_dubbel_factuur', 'controle_lege_routes', 'controle_afwezig_melding'
    ]
    
    # Filter alleen de kolommen die daadwerkelijk bestaan in de data
    available_cols = [col for col in factuur_afwijkingen_cols if col in gefilterde_data.columns]
    display_df = gefilterde_data[available_cols].copy()
    
    # Geef kolommen Nederlandse namen voor betere leesbaarheid
    column_mapping = {
        'jaar': 'Jaar',
        'maand': 'Maand',
        'perceel': 'Perceel',
        'vervoerder': 'Vervoerder',
        'vaste_kosten': 'Vaste Kosten (€)',
        'variabele_kosten': 'Variabele Kosten (€)',
        'ritten_besteld': 'Ritten Besteld',
        'ritten_uitgevoerd': 'Ritten Uitgevoerd',
        'ritten_geannuleerd': 'Ritten Geannuleerd',
        'ritten_loos': 'Ritten Loos',
        'routes': 'Routes',
        'controle_bestelling_sw': 'Bestelling SW',
        'controle_gegevens_levering': 'Gegevens Levering',
        'controle_stiptheid': 'Stiptheid',
        'controle_indicaties': 'Indicaties',
        'controle_reistijd': 'Reistijd',
        'controle_dubbel_factuur': 'Dubbel Factuur',
        'controle_lege_routes': 'Lege Routes',
        'controle_afwezig_melding': 'Afwezig Melding'
    }
    
    display_df = display_df.rename(columns=column_mapping)
    
    # Toon de dataframe
    st.dataframe(display_df, use_container_width=True)
    
    # Export knop voor de volledige factuur data met afwijkingen
    export_dataframe_to_csv(display_df, f"factuur_afwijkingen_analytics_{datetime.now().strftime('%Y%m%d')}.csv")

def show_stacked_bar_graph():
    """Toon stacked bar graph per perceel met ritten statussen"""
    st.title("📊 Stacked Bar Graph - Ritten Status per Perceel")
    
    # Laad data
    data = load_data()
    
    if data.empty:
        st.warning("Geen factuurgegevens gevonden.")
        return
    
    # Apply filters
    gefilterde_data = apply_stacked_bar_filters(data)
    
    if gefilterde_data.empty:
        st.warning("Geen data gevonden met de geselecteerde filters.")
        return
    
    # Bereken jaar-maand combinatie voor chronologische volgorde
    gefilterde_data['jaar_maand'] = gefilterde_data.apply(
        lambda row: f"{row['jaar']}-{row['maand']:02d}", axis=1
    )
    
    # Sorteer data chronologisch
    gefilterde_data = gefilterde_data.sort_values(['jaar', 'maand'])
    
    # Groepeer data per perceel en jaar-maand
    grouped_data = gefilterde_data.groupby(['perceel', 'jaar_maand']).agg({
        'ritten_besteld': 'sum',
        'ritten_geannuleerd': 'sum',
        'ritten_loos': 'sum'
    }).reset_index()
    
    # Maak stacked bar graph
    fig_stacked = go.Figure()
    
    # Voeg traces toe voor elke ritten status
    fig_stacked.add_trace(go.Bar(
        name='Ritten Besteld',
        x=grouped_data['jaar_maand'],
        y=grouped_data['ritten_besteld'],
        marker_color='green',
        hovertemplate='<b>%{x}</b><br>Ritten Besteld: %{y}<extra></extra>'
    ))
    
    fig_stacked.add_trace(go.Bar(
        name='Ritten Geannuleerd',
        x=grouped_data['jaar_maand'],
        y=grouped_data['ritten_geannuleerd'],
        marker_color='yellow',
        hovertemplate='<b>%{x}</b><br>Ritten Geannuleerd: %{y}<extra></extra>'
    ))
    
    fig_stacked.add_trace(go.Bar(
        name='Ritten Loos',
        x=grouped_data['jaar_maand'],
        y=grouped_data['ritten_loos'],
        marker_color='red',
        hovertemplate='<b>%{x}</b><br>Ritten Loos: %{y}<extra></extra>'
    ))
    
    # Configureer layout
    fig_stacked.update_layout(
        title='Ritten Status per Perceel (Stacked)',
        xaxis_title='Jaar-Maand',
        yaxis_title='Aantal Ritten',
        barmode='stack',
        height=600,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Update x-as voor consistente 1-maand increments
    fig_stacked.update_xaxes(
        tickangle=-45,
        tickmode='linear',
        dtick='M1',
        tickformat='%Y-%m'
    )
    
    # Create tabs for different views
    view_tab1, view_tab2 = st.tabs(["📊 Gecombineerd Overzicht", "📈 Per Perceel"])
    
    with view_tab1:
        st.plotly_chart(fig_stacked, use_container_width=True)
        
        # New stacked bar chart for controle_bestelling_sw percentage
        st.header("📊 Controle Bestelling SW Percentage")
        
        # Calculate percentage data
        percentage_data = gefilterde_data.groupby(['jaar_maand']).agg({
            'ritten_besteld': 'sum',
            'controle_bestelling_sw': 'sum'
        }).reset_index()
        
        # Calculate percentages
        percentage_data['percentage_goed'] = 100  # Always 100% for green base
        percentage_data['percentage_fout'] = (percentage_data['controle_bestelling_sw'] / percentage_data['ritten_besteld'] * 100).fillna(0)
        
        fig_percentage = go.Figure()
        
        # Green base (100%)
        fig_percentage.add_trace(go.Bar(
            name='Ritten Besteld (100%)',
            x=percentage_data['jaar_maand'],
            y=percentage_data['percentage_goed'],
            marker_color='green',
            hovertemplate='<b>%{x}</b><br>Ritten Besteld: 100%<extra></extra>'
        ))
        
        # Red percentage (controle_bestelling_sw)
        fig_percentage.add_trace(go.Bar(
            name='Controle Bestelling SW (%)',
            x=percentage_data['jaar_maand'],
            y=percentage_data['percentage_fout'],
            marker_color='red',
            hovertemplate='<b>%{x}</b><br>Controle Bestelling SW: %{y:.1f}%<extra></extra>'
        ))
        
        fig_percentage.update_layout(
            title='Controle Bestelling SW Percentage (Gecombineerd)',
            xaxis_title='Jaar-Maand',
            yaxis_title='Percentage (%)',
            barmode='stack',
            height=600,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        fig_percentage.update_xaxes(
            tickangle=-45,
            tickmode='linear',
            dtick='M1',
            tickformat='%Y-%m'
        )
        
        st.plotly_chart(fig_percentage, use_container_width=True)
    
    with view_tab2:
        percelen = sorted(grouped_data['perceel'].unique())
        
        for perceel in percelen:
            perceel_data = grouped_data[grouped_data['perceel'] == perceel]
            
            fig_perceel = go.Figure()
            
            fig_perceel.add_trace(go.Bar(
                name='Ritten Besteld',
                x=perceel_data['jaar_maand'],
                y=perceel_data['ritten_besteld'],
                marker_color='green'
            ))
            
            fig_perceel.add_trace(go.Bar(
                name='Ritten Geannuleerd',
                x=perceel_data['jaar_maand'],
                y=perceel_data['ritten_geannuleerd'],
                marker_color='yellow'
            ))
            
            fig_perceel.add_trace(go.Bar(
                name='Ritten Loos',
                x=perceel_data['jaar_maand'],
                y=perceel_data['ritten_loos'],
                marker_color='red'
            ))
            
            fig_perceel.update_layout(
                title=f'Ritten Status - {perceel}',
                xaxis_title='Jaar-Maand',
                yaxis_title='Aantal Ritten',
                barmode='stack',
                height=400
            )
            
            fig_perceel.update_xaxes(
                tickangle=-45,
                tickmode='linear',
                dtick='M1',
                tickformat='%Y-%m'
            )
            
            st.plotly_chart(fig_perceel, use_container_width=True)
            
            # New percentage chart per perceel
            perceel_percentage_data = gefilterde_data[gefilterde_data['perceel'] == perceel].groupby(['jaar_maand']).agg({
                'ritten_besteld': 'sum',
                'controle_bestelling_sw': 'sum'
            }).reset_index()
            
            perceel_percentage_data['percentage_goed'] = 100
            perceel_percentage_data['percentage_fout'] = (perceel_percentage_data['controle_bestelling_sw'] / perceel_percentage_data['ritten_besteld'] * 100).fillna(0)
            
            fig_perceel_percentage = go.Figure()
            
            fig_perceel_percentage.add_trace(go.Bar(
                name='Ritten Besteld (100%)',
                x=perceel_percentage_data['jaar_maand'],
                y=perceel_percentage_data['percentage_goed'],
                marker_color='green'
            ))
            
            fig_perceel_percentage.add_trace(go.Bar(
                name='Controle Bestelling SW (%)',
                x=perceel_percentage_data['jaar_maand'],
                y=perceel_percentage_data['percentage_fout'],
                marker_color='red'
            ))
            
            fig_perceel_percentage.update_layout(
                title=f'Controle Bestelling SW Percentage - {perceel}',
                xaxis_title='Jaar-Maand',
                yaxis_title='Percentage (%)',
                barmode='stack',
                height=400
            )
            
            fig_perceel_percentage.update_xaxes(
                tickangle=-45,
                tickmode='linear',
                dtick='M1',
                tickformat='%Y-%m'
            )
            
            st.plotly_chart(fig_perceel_percentage, use_container_width=True)
    
    # Export knop
    st.header("📤 Export")
    export_dataframe_to_csv(grouped_data, f"stacked_bar_data_{datetime.now().strftime('%Y%m%d')}.csv")

# === Hoofdapplicatie ===
def main():
    st.set_page_config(
        page_title="Factuurcontrole Dashboard",
        page_icon="📊",
        layout="wide"
    )
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["🚦 Dashboard", "📈 Analytics", "📊 Stacked Bar Graph"])
    
    with tab1:
        show_dashboard()
    
    with tab2:
        show_analytics()
    
    with tab3:
        show_stacked_bar_graph()

if __name__ == "__main__":
    main()