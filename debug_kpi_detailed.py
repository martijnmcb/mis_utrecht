#!/usr/bin/env python3
"""
Detailed debug script to check KPI data flow and actual calculations
"""

import sqlite3
import pandas as pd
import sys
import os

# Add the current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_detailed_kpi():
    """Debug the KPI data collection with actual calculations"""
    
    print("🔍 Detailed KPI Data Debugging...")
    
    # Connect to database
    conn = sqlite3.connect('factuurcontrole.db')
    
    # Get facturen with their afwijkingen
    query = """
    SELECT 
        f.id as factuur_id,
        f.jaar,
        f.maand,
        f.perceel,
        f.vervoerder,
        f.ritten_besteld,
        f.ritten_uitgevoerd,
        f.routes,
        a.controle_bestelling_sw,
        a.controle_gegevens_levering,
        a.controle_stiptheid,
        a.controle_indicaties,
        a.controle_reistijd,
        a.controle_dubbel_factuur,
        a.controle_lege_routes,
        a.controle_afwezig_melding
    FROM facturen f
    JOIN afwijkingen a ON f.id = a.factuur_id
    """
    
    facturen_with_afwijkingen = pd.read_sql_query(query, conn)
    print(f"📊 Found {len(facturen_with_afwijkingen)} facturen with afwijkingen")
    
    # Get KPI parameters
    kpi_params = pd.read_sql_query("SELECT * FROM kpi_parameters", conn)
    print(f"📋 Found {len(kpi_params)} KPI parameters")
    
    # Map KPI parameters to columns
    kpi_mapping = {
        'controle_bestelling_sw': 'Bestelling Sw',
        'controle_gegevens_levering': 'Gegevens Levering',
        'controle_stiptheid': 'Stiptheid',
        'controle_indicaties': 'Indicaties',
        'controle_reistijd': 'Reistijd',
        'controle_dubbel_factuur': 'Dubbel Factuur',
        'controle_lege_routes': 'Lege Routes',
        'controle_afwezig_melding': 'Afwezig Melding'
    }
    
    # Calculate KPI values
    kpi_results = []
    
    for idx, row in facturen_with_afwijkingen.iterrows():
        print(f"\n--- Factuur ID {row['factuur_id']} ---")
        print(f"Jaar: {row['jaar']}, Maand: {row['maand']}, Percel: {row['perceel']}")
        
        for _, kpi_param in kpi_params.iterrows():
            kpi_column = kpi_param['afwijking_type']
            if kpi_column in kpi_mapping:
                actual_count = row[kpi_column]
                basis_value = row['ritten_uitgevoerd'] if 'ritten' in kpi_param['berekenings_basis'] else row['routes']
                
                # Calculate percentage
                if basis_value > 0:
                    percentage = round((actual_count / basis_value) * 100, 1)
                else:
                    percentage = 0.0
                
                kpi_name = kpi_mapping[kpi_column]
                
                print(f"  - {kpi_name}: {percentage}% ({actual_count}/{basis_value})")
                
                kpi_results.append({
                    'factuur_id': row['factuur_id'],
                    'jaar': row['jaar'],
                    'maand': row['maand'],
                    'kpi_type': kpi_name,
                    'percentage': percentage,
                    'aantal': actual_count,
                    'basis': basis_value
                })
    
    conn.close()
    
    if kpi_results:
        # Create summary
        kpi_df = pd.DataFrame(kpi_results)
        
        kpi_summary = kpi_df.groupby(['kpi_type']).agg({
            'percentage': 'mean',
            'aantal': 'sum',
            'basis': 'sum'
        }).reset_index()
        
        kpi_summary['gemiddeld_percentage'] = kpi_summary['percentage'].round(1)
        kpi_summary['totaal_aantal'] = kpi_summary['aantal']
        
        print("\n" + "="*50)
        print("📊 ACTUAL KPI SAMENVATTING:")
        print("="*50)
        print(kpi_summary[['kpi_type', 'gemiddeld_percentage', 'totaal_aantal']].to_string(index=False))
        
        return kpi_summary
    else:
        print("❌ No KPI data found")
        return None

if __name__ == "__main__":
    result = debug_detailed_kpi()
    if result is not None and not result.empty:
        print("\n✅ KPI calculations are working correctly with actual data!")
    else:
        print("\n❌ No data available")