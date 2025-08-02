#!/usr/bin/env python3
import sqlite3
import pandas as pd
import numpy as np

# Test the KPI calculation
DB_FILE = "factuurcontrole.db"

def load_data():
    """Laad alle factuurgegevens"""
    with sqlite3.connect(DB_FILE) as conn:
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
    
    for afwijking_key, kpi_key in afwijking_mapping.items():
        kpi_row = kpi_params[kpi_params['afwijking_type'] == kpi_key]
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

# Test the calculation
print("Testing KPI calculations...")
data = load_data()
kpi_params = load_kpi_parameters()

print(f"Found {len(data)} facturen")
print(f"Found {len(kpi_params)} KPI parameters")

for idx, factuur in data.iterrows():
    print(f"\n--- Factuur {factuur['jaar']}-{factuur['maand']} ---")
    kpi_results = calculate_kpi_scores(factuur, kpi_params)
    
    for kpi in kpi_results:
        print(f"{kpi['naam']}: {kpi['aantal']}/{kpi['basis']} = {kpi['percentage']:.1f}% (target: {kpi['doel']}%)")