#!/usr/bin/env python3
"""
Debug script to check KPI data flow in factuurcontrole dashboard
"""

import sqlite3
import pandas as pd
import sys
import os

# Add the current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the KPI calculation function
from factuurcontrole_dashboard import calculate_kpi_scores

def debug_kpi_data():
    """Debug the KPI data collection and calculation process"""
    
    print("🔍 Debugging KPI Data Flow...")
    
    # Connect to database
    conn = sqlite3.connect('factuurcontrole.db')
    
    # Get facturen data
    facturen_df = pd.read_sql_query("SELECT * FROM facturen", conn)
    print(f"📊 Found {len(facturen_df)} facturen")
    
    # Get KPI parameters
    kpi_params_df = pd.read_sql_query("SELECT * FROM kpi_parameters", conn)
    print(f"📋 Found {len(kpi_params_df)} KPI parameters")
    
    # Use DataFrame directly
    kpi_params = kpi_params_df
    
    # Debug each factuur
    kpi_data = []
    for idx, factuur in facturen_df.iterrows():
        print(f"\n--- Factuur {idx+1} ---")
        print(f"Jaar: {factuur['jaar']}, Maand: {factuur['maand']}, Percel: {factuur['perceel']}")
        
        try:
            kpi_results = calculate_kpi_scores(factuur, kpi_params)
            print(f"✅ KPI results found: {len(kpi_results)}")
            
            for kpi in kpi_results:
                print(f"  - {kpi['naam']}: {kpi['percentage']}% (aantal: {kpi['aantal']}, basis: {kpi['basis']})")
                
                kpi_data.append({
                    'kpi_type': kpi['naam'],
                    'percentage': kpi['percentage'],
                    'aantal': kpi['aantal'],
                    'basis': kpi['basis']
                })
                
        except Exception as e:
            print(f"❌ Error: {e}")
            continue
    
    conn.close()
    
    if kpi_data:
        print(f"\n✅ Total KPI data points: {len(kpi_data)}")
        kpi_df = pd.DataFrame(kpi_data)
        
        # Create summary
        kpi_summary = kpi_df.groupby(['kpi_type']).agg({
            'percentage': 'mean',
            'aantal': 'sum',
            'basis': 'sum'
        }).reset_index()
        
        kpi_summary['gemiddeld_percentage'] = kpi_summary['percentage'].round(1)
        kpi_summary['totaal_aantal'] = kpi_summary['aantal']
        
        print("\n📋 KPI Samenvatting:")
        print(kpi_summary[['kpi_type', 'gemiddeld_percentage', 'totaal_aantal']])
        
        return kpi_summary
    else:
        print("❌ No KPI data found")
        return None

if __name__ == "__main__":
    result = debug_kpi_data()
    if result is not None and not result.empty:
        print("\n✅ KPI Samenvatting calculation is working correctly!")
    else:
        print("\n❌ No data available for KPI Samenvatting")