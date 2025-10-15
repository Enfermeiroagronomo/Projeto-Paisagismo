# app.py - Versão Otimizada

import streamlit as st
import pandas as pd
import yaml
import json
from datetime import datetime, timedelta
import os
import sys
import traceback

# Garante que os módulos locais sejam encontrados
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.solar import get_solar_position
from src.scene import create_circular_area, create_grid_points
from src.simulate import run_full_simulation, calculate_sun_hours
from src.visualize import create_heatmap, create_planting_plan
from scripts.export_dxf import export_to_dxf

st.set_page_config(page_title="Análise Solar", page_icon="☀️", layout="wide")

# <<< MELHORIA: Funções de carregamento com tratamento de erros >>>
@st.cache_data
def load_config():
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        st.error("Arquivo de configuração 'config.yaml' não encontrado.")
        return None

@st.cache_data
def load_plant_catalog():
    try:
        with open('catalog/plant_catalog.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Catálogo de plantas 'catalog/plant_catalog.json' não encontrado.")
        return None

# <<< MELHORIA: Lógica principal da simulação encapsulada em uma função >>>
# Isso torna o código principal mais limpo e organizado.
def run_simulation_logic(lat, lon, start_date, end_date, freq, sim_type, config, plant_catalog):
    """
    Executa a simulação solar completa em lotes para economizar memória.
    """
    try:
        area = create_circular_area(config['scene']['radius_m'])
        grid_points = create_grid_points(area, config['scene']['grid_resolution_m'])
        
        # <<< MELHORIA PRINCIPAL: Processamento em Lotes (Batch Processing) >>>
        # Em vez de calcular para o período todo, calculamos dia a dia (ou em blocos)
        
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        total_days = len(date_range)
        
        # Inicializa um array para acumular as horas de sol. Mais eficiente que um DataFrame.
        sun_hours_accumulator = pd.Series(0.0, index=range(len(grid_points)))

        # Feedback de progresso para o usuário
        progress_bar = st.progress(0, text="Iniciando simulação...")
        
        for i, current_day in enumerate(date_range):
            progress_bar.progress((i + 1) / total_days, text=f"Processando Dia {i+1} de {total_days}...")
            
            # 1. Pega a posição solar APENAS para o dia atual
            solar_pos_chunk = get_solar_position(
                lat, lon, config['location']['timezone'], 
                str(current_day.date()), str(current_day.date()), freq
            )
            
            if solar_pos_chunk.empty:
                continue # Pula para o próximo dia se este não tiver sol (noite polar, etc.)

            # 2. Roda a simulação para o dia atual e calcula as horas de sol
            results_df_chunk = run_full_simulation(config, solar_pos_chunk, grid_points)
            freq_min = pd.to_timedelta(freq).total_seconds() / 60
            sun_hours_chunk = calculate_sun_hours(results_df_chunk, freq_min)
            
            # 3. Adiciona o resultado do dia ao acumulador
            sun_hours_accumulator += sun_hours_chunk

        progress_bar.empty() # Limpa a barra de progresso

        # Finaliza o cálculo das horas de sol
        if sim_type == 'Anual' and total_days > 0:
            final_sun_hours = sun_hours_accumulator / total_days # Média diária para o ano
        else:
            final_sun_hours = sun_hours_accumulator
            
        # Gera as visualizações
        heatmap_file = create_heatmap(grid_points, final_sun_hours, config['scene']['grid_resolution_m'], config['scene']['radius_m'])
        plan_file = create_planting_plan(grid_points, final_sun_hours, plant_catalog, config['luminosity_classes'], config['scene']['radius_m'])
        
        return {
            "sun_hours": final_sun_hours,
            "grid_points": grid_points,
            "heatmap_file": heatmap_file,
            "plan_file": plan_file
        }
        
    except Exception as e:
        st.error(f"Ocorreu um erro durante a simulação: {e}")
        st.error(f"Detalhes: {traceback.format_exc()}")
        return None


# --- Início da Interface do Streamlit ---

config = load_config()
plant_catalog = load_plant_catalog()

if config and plant_catalog:
    os.makedirs(config['output']['directory'], exist_ok=True)

    if 'sun_hours' not in st.session_state:
        st.session_state.sun_hours = None

    st.title("☀️ Análise Solar para Planejamento Paisagístico")

    with st.sidebar:
        st.header("Parâmetros da Simulação")
        st.subheader("Localização")
        lat_input = st.number_input("Latitude", value=config['location']['latitude'], format="%.6f")
        lon_input = st.number_input("Longitude", value=config['location']['longitude'], format="%.6f")
        
        st.subheader("Período")
        sim_type = st.radio("Tipo de Simulação", ('Anual', 'Data Específica'), index=1)
        
        if sim_type == 'Anual':
            date_for_sim = st.date_input("Selecione um ano", datetime(2025, 1, 1))
            start_date, end_date = f"{date_for_sim.year}-01-01", f"{date_for_sim.year}-12-31"
        else:
            date_for_sim = st.date_input("Data da simulação", datetime.now().date())
            start_date, end_date = date_for_sim, date_for_sim

        freq = st.select_slider("Frequência", options=['1H', '30min', '15min'], value='1H')
        run_button = st.button("Executar Simulação", type="primary")

    st.markdown(f"Análise para **Lat: {lat_input:.4f}, Lon: {lon_input:.4f}**")

    # <<< MELHORIA: O bloco do botão agora é muito mais limpo >>>
    if run_button:
        # Chama a função principal que contém toda a lógica
        results = run_simulation_logic(lat_input, lon_input, start_date, end_date, freq, sim_type, config, plant_catalog)
        
        # Se a simulação foi bem-sucedida, armazena os resultados no estado da sessão
        if results:
            st.session_state.sun_hours = results["sun_hours"]
            st.session_state.grid_points = results["grid_points"]
            st.session_state.heatmap_file = results["heatmap_file"]
            st.session_state.plan_file = results["plan_file"]
            st.success("Simulação Concluída!")

    # A lógica de exibição permanece a mesma, pois já era muito boa
    if st.session_state.sun_hours is not None:
        st.header("Resultados")
        col1, col2 = st.columns(2)
        with col1:
            if 'heatmap_file' in st.session_state and st.session_state.heatmap_file:
                st.image(st.session_state.heatmap_file, caption="Mapa de Calor Solar")
        with col2:
            if 'plan_file' in st.session_state and st.session_state.plan_file:
                st.image(st.session_state.plan_file, caption="Planta Baixa Sugerida")

        results_data = pd.DataFrame({
            'x': st.session_state.grid_points[:, 0], 
            'y': st.session_state.grid_points[:, 1], 
            'sun_hours': st.session_state.sun_hours
        }).astype({'sun_hours': 'float32'}) # <<< MELHORIA: Reduz tipo de dado para economizar memória

        st.download_button("Baixar Dados (CSV)", results_data.to_csv(index=False).encode('utf-8'), "solar_data.csv", "text/csv")
        
        dxf_filename = os.path.join(config['output']['directory'], "layout.dxf")
        export_to_dxf(results_data, config, dxf_filename)
        with open(dxf_filename, "rb") as fp:
            st.download_button("Baixar Layout (DXF)", fp, file_name="layout.dxf")
