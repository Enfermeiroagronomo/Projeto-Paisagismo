import streamlit as st
import pandas as pd
import yaml
import json
from datetime import datetime
import os
import sys
import time

# Garante que os módulos locais sejam encontrados
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.solar import get_solar_position
from src.scene import create_circular_area, create_grid_points
from src.simulate import run_full_simulation, calculate_sun_hours
from src.visualize import create_heatmap, create_planting_plan
from scripts.export_dxf import export_to_dxf

st.set_page_config(page_title="Análise Solar", page_icon="☀️", layout="wide")

# Detectar ambiente Cloud
IS_CLOUD = os.getenv('STREAMLIT_SHARING_MODE') is not None or os.getenv('HOSTNAME', '').startswith('streamlit')

@st.cache_data(ttl=3600)
def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        
    # Ajustar parâmetros para Cloud automaticamente
    if IS_CLOUD:
        config['scene']['radius_m'] = min(config['scene']['radius_m'], 10)
        config['scene']['grid_resolution_m'] = max(config['scene']['grid_resolution_m'], 1.5)
        if 'simulation' in config:
            config['simulation']['num_rays'] = min(config['simulation'].get('num_rays', 50), 20)
            config['simulation']['max_bounces'] = min(config['simulation'].get('max_bounces', 3), 1)
    
    return config

@st.cache_data(ttl=3600)
def load_plant_catalog():
    with open('catalog/plant_catalog.json', 'r', encoding='utf-8') as f:
        return json.load(f)

@st.cache_data(ttl=3600, show_spinner=False)
def run_cached_simulation(lat, lon, timezone, start_date, end_date, freq, radius, resolution):
    """Versão cacheada da simulação para evitar reprocessamento"""
    try:
        # Criar área e grid
        area = create_circular_area(radius)
        grid_points = create_grid_points(area, resolution)
        
        # Limitar número de pontos no Cloud
        if IS_CLOUD and len(grid_points) > 200:
            st.warning(f"⚠️ Reduzindo pontos de {len(grid_points)} para 200 (limite Cloud)")
            step = len(grid_points) // 200
            grid_points = grid_points[::step][:200]
        
        # Obter posição solar
        solar_pos = get_solar_position(lat, lon, timezone, str(start_date), str(end_date), freq)
        
        if solar_pos.empty:
            return None, None, "Não há dados solares para o período selecionado"
        
        # Limitar timesteps no Cloud
        if IS_CLOUD and len(solar_pos) > 100:
            st.info(f"ℹ️ Usando {100} de {len(solar_pos)} timesteps para velocidade")
            step = len(solar_pos) // 100
            solar_pos = solar_pos.iloc[::step][:100]
        
        # Executar simulação
        results_df = run_full_simulation(config, solar_pos, grid_points)
        
        freq_min = pd.to_timedelta(freq).total_seconds() / 60
        total_sun_hours = calculate_sun_hours(results_df, freq_min)
        
        return grid_points, total_sun_hours, None
        
    except Exception as e:
        return None, None, f"Erro na simulação: {str(e)}"

config = load_config()
plant_catalog = load_plant_catalog()

# Criar diretório de output se não existir
try:
    os.makedirs(config['output']['directory'], exist_ok=True)
except:
    pass

# Inicializar session state
if 'sun_hours' not in st.session_state:
    st.session_state.sun_hours = None
if 'grid_points' not in st.session_state:
    st.session_state.grid_points = None

# Título principal
st.title("☀️ Análise Solar para Planejamento Paisagístico")

# Alerta sobre modo Cloud
if IS_CLOUD:
    st.info("⚡ **Modo Cloud Ativo** - Parâmetros otimizados para performance. Para simulações completas, rode localmente.")

# Sidebar com parâmetros
with st.sidebar:
    st.header("Parâmetros da Simulação")
    
    st.subheader("Localização")
    lat_input = st.number_input(
        "Latitude",
        value=float(config['location']['latitude']),
        min_value=-90.0,
        max_value=90.0,
        format="%.6f",
        help="Latitude em graus decimais"
    )
    lon_input = st.number_input(
        "Longitude",
        value=float(config['location']['longitude']),
        min_value=-180.0,
        max_value=180.0,
        format="%.6f",
        help="Longitude em graus decimais"
    )
    
    st.subheader("Período")
    sim_type = st.radio(
        "Tipo de Simulação", 
        ('Data Específica', 'Anual'),
        index=0,
        help="Data específica é mais rápida"
    )
    
    if sim_type == 'Anual':
        if IS_CLOUD:
            st.warning("⚠️ Simulação anual pode ser lenta no Cloud. Recomenda-se data específica.")
        date_for_sim = st.date_input("Selecione um ano", datetime(2025, 1, 1))
        start_date = f"{date_for_sim.year}-01-01"
        end_date = f"{date_for_sim.year}-12-31"
    else:
        date_for_sim = st.date_input("Data da simulação", datetime.now().date())
        start_date = date_for_sim
        end_date = date_for_sim
    
    freq_options = ['1H', '30min'] if IS_CLOUD else ['1H', '30min', '15min']
    freq = st.select_slider(
        "Frequência", 
        options=freq_options, 
        value='1H' if IS_CLOUD else '30min',
        help="Maior frequência = mais lento"
    )
    
    st.subheader("Área de Análise")
    max_radius = 10 if IS_CLOUD else 30
    radius = st.slider(
        "Raio (metros)",
        min_value=5,
        max_value=max_radius,
        value=min(config['scene']['radius_m'], max_radius),
        help="Raio da área circular a analisar"
    )
    
    min_resolution = 1.5 if IS_CLOUD else 0.5
    resolution = st.slider(
        "Resolução (metros)",
        min_value=min_resolution,
        max_value=3.0,
        value=max(config['scene']['grid_resolution_m'], min_resolution),
        step=0.5,
        help="Menor = mais pontos = mais lento"
    )
    
    run_button = st.button("🚀 Executar Simulação", type="primary", use_container_width=True)

# Área principal
st.markdown(f"**Localização:** Lat: {lat_input:.4f}°, Lon: {lon_input:.4f}°")

# Mostrar estimativa de pontos
estimated_points = int((radius * 2 / resolution) ** 2 * 3.14 / 4)
if IS_CLOUD and estimated_points > 200:
    st.caption(f"⚠️ {estimated_points} pontos estimados (será limitado a 200 no Cloud)")
else:
    st.caption(f"📊 ~{estimated_points} pontos de análise")

# Executar simulação
if run_button:
    start_time = time.time()
    
    progress_bar = st.progress(0, text="Iniciando simulação...")
    
    try:
        with st.spinner("🔄 Processando simulação solar..."):
            progress_bar.progress(25, text="Criando grid de análise...")
            
            # Executar simulação cacheada
            grid_points, sun_hours, error = run_cached_simulation(
                lat_input, lon_input,
                config['location']['timezone'],
                start_date, end_date, freq,
                radius, resolution
            )
            
            progress_bar.progress(75, text="Finalizando cálculos...")
            
            if error:
                st.error(f"❌ {error}")
                progress_bar.empty()
            elif grid_points is None:
                st.error("❌ Falha na simulação. Tente parâmetros mais simples.")
                progress_bar.empty()
            else:
                # Ajustar para média diária se for anual
                if sim_type == 'Anual':
                    num_days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
                    sun_hours = sun_hours / num_days
                
                st.session_state.sun_hours = sun_hours
                st.session_state.grid_points = grid_points
                
                elapsed = time.time() - start_time
                progress_bar.progress(100, text="✅ Concluído!")
                time.sleep(0.5)
                progress_bar.empty()
                
                st.success(f"✅ Simulação concluída em {elapsed:.1f} segundos!")
                st.balloons()
                
    except Exception as e:
        st.error(f"❌ Erro inesperado: {str(e)}")
        if not IS_CLOUD:
            st.exception(e)
        progress_bar.empty()

# Mostrar resultados
if st.session_state.sun_hours is not None and st.session_state.grid_points is not None:
    st.header("📊 Resultados da Análise")
    
    try:
        # Criar visualizações
        with st.spinner("Gerando visualizações..."):
            heatmap_file = create_heatmap(
                st.session_state.grid_points, 
                st.session_state.sun_hours, 
                resolution,
                radius
            )
            
            plan_file = create_planting_plan(
                st.session_state.grid_points, 
                st.session_state.sun_hours, 
                plant_catalog, 
                config['luminosity_classes'],
                radius
            )
        
        # Mostrar imagens
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🌡️ Mapa de Calor Solar")
            if heatmap_file and os.path.exists(heatmap_file):
                st.image(heatmap_file, use_container_width=True)
            else:
                st.warning("Não foi possível gerar o mapa de calor")
        
        with col2:
            st.subheader("🌱 Planta Baixa Sugerida")
            if plan_file and os.path.exists(plan_file):
                st.image(plan_file, use_container_width=True)
            else:
                st.warning("Não foi possível gerar a planta baixa")
        
        # Estatísticas
        st.subheader("📈 Estatísticas")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Pontos Analisados", len(st.session_state.grid_points))
        with col2:
            st.metric("Sol Médio", f"{st.session_state.sun_hours.mean():.1f}h")
        with col3:
            st.metric("Sol Máximo", f"{st.session_state.sun_hours.max():.1f}h")
        with col4:
            st.metric("Sol Mínimo", f"{st.session_state.sun_hours.min():.1f}h")
        
        # Downloads
        st.subheader("💾 Exportar Dados")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV
            results_data = pd.DataFrame({
                'x': st.session_state.grid_points[:, 0],
                'y': st.session_state.grid_points[:, 1],
                'sun_hours': st.session_state.sun_hours
            })
            
            csv_data = results_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📄 Baixar Dados (CSV)",
                csv_data,
                "analise_solar.csv",
                "text/csv",
                use_container_width=True
            )
        
        with col2:
            # DXF
            try:
                dxf_filename = os.path.join(config['output']['directory'], "layout.dxf")
                export_to_dxf(results_data, config, dxf_filename)
                
                if os.path.exists(dxf_filename):
                    with open(dxf_filename, "rb") as fp:
                        st.download_button(
                            "📐 Baixar Layout (DXF)",
                            fp,
                            file_name="layout_paisagismo.dxf",
                            use_container_width=True
                        )
            except Exception as e:
                st.caption(f"DXF indisponível: {str(e)}")
    
    except Exception as e:
        st.error(f"Erro ao gerar visualizações: {str(e)}")
        if not IS_CLOUD:
            st.exception(e)

# Rodapé
st.markdown("---")
st.caption("💡 **Dica:** Para análises mais detalhadas, reduza a resolução ou rode localmente.")
