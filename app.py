import streamlit as st
import pandas as pd
import yaml
import json
from datetime import datetime
import os
import sys

# Garante que os módulos locais sejam encontrados
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.solar import get_solar_position
from src.scene import create_circular_area, create_grid_points
from src.simulate import run_full_simulation, calculate_sun_hours
from src.visualize import create_heatmap, create_planting_plan
from scripts.export_dxf import export_to_dxf

st.set_page_config(page_title="Análise Solar", page_icon="☀️", layout="wide")

@st.cache_data
def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

@st.cache_data
def load_plant_catalog():
    with open('catalog/plant_catalog.json', 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_config()
plant_catalog = load_plant_catalog()
os.makedirs(config['output']['directory'], exist_ok=True)

if 'sun_hours' not in st.session_state:
    st.session_state.sun_hours = None

st.title("☀️ Análise Solar para Planejamento Paisagístico")

with st.sidebar:
    st.header("Parâmetros da Simulação")
    sim_type = st.radio("Tipo de Simulação", ('Anual', 'Data Específica'), index=1)
    
    if sim_type == 'Anual':
        date_for_sim = st.date_input("Selecione um ano", datetime(2025, 1, 1))
        start_date, end_date = f"{date_for_sim.year}-01-01", f"{date_for_sim.year}-12-31"
    else:
        date_for_sim = st.date_input("Data da simulação", datetime.now().date())
        start_date, end_date = date_for_sim, date_for_sim

    freq = st.select_slider("Frequência", options=['1H', '30min', '15min'], value='30min')
    run_button = st.button("Executar Simulação", type="primary")

if run_button:
    area = create_circular_area(config['scene']['radius_m'])
    grid_points = create_grid_points(area, config['scene']['grid_resolution_m'])
    
    solar_pos = get_solar_position(
        config['location']['latitude'], config['location']['longitude'],
        config['location']['timezone'], str(start_date), str(end_date), freq
    )
    
    results_df = run_full_simulation(config, solar_pos, grid_points)
    
    freq_min = pd.to_timedelta(freq).total_seconds() / 60
    total_sun_hours = calculate_sun_hours(results_df, freq_min)
    
    if sim_type == 'Anual':
        num_days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
        st.session_state.sun_hours = total_sun_hours / num_days
    else:
        st.session_state.sun_hours = total_sun_hours
        
    st.session_state.grid_points = grid_points
    st.success("Simulação Concluída!")
    
    st.session_state.heatmap_file = create_heatmap(grid_points, st.session_state.sun_hours, config['scene']['grid_resolution_m'], config['scene']['radius_m'])
    st.session_state.plan_file = create_planting_plan(grid_points, st.session_state.sun_hours, plant_catalog, config['luminosity_classes'], config['scene']['radius_m'])

if st.session_state.sun_hours is not None:
    st.header("Resultados")
    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.heatmap_file:
            st.image(st.session_state.heatmap_file, caption="Mapa de Calor Solar")
    with col2:
        if st.session_state.plan_file:
            st.image(st.session_state.plan_file, caption="Planta Baixa Sugerida")

    results_data = pd.DataFrame({'x': st.session_state.grid_points[:, 0], 'y': st.session_state.grid_points[:, 1], 'sun_hours': st.session_state.sun_hours})
    st.download_button("Baixar Dados (CSV)", results_data.to_csv(index=False), "solar_data.csv", "text/csv")
    
    dxf_filename = os.path.join(config['output']['directory'], "layout.dxf")
    export_to_dxf(results_data, config, dxf_filename)
    with open(dxf_filename, "rb") as fp:
        st.download_button("Baixar Layout (DXF)", fp, file_name="layout.dxf")
