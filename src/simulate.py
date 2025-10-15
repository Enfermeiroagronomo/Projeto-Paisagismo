import numpy as np
import pandas as pd
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
import trimesh
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.solar import get_solar_position
from src.scene import create_tree_mesh

def get_sun_vectors(solar_position):
    """Converte a posição solar para vetores de direção 3D."""
    azimuth_rad = np.deg2rad(solar_position['azimuth'])
    elevation_rad = np.deg2rad(solar_position['apparent_elevation'])
    x = np.sin(azimuth_rad) * np.cos(elevation_rad)
    y = np.cos(azimuth_rad) * np.cos(elevation_rad)
    z = np.sin(elevation_rad)
    return np.vstack([x, y, z]).T

def run_simulation_for_timestep(args):
    """Função de trabalho para processamento paralelo."""
    sun_vector, grid_points, tree_mesh_data = args
    tree_mesh = trimesh.Trimesh(vertices=tree_mesh_data[0], faces=tree_mesh_data[1])
    
    ray_origins = grid_points
    ray_directions = np.tile(sun_vector, (len(grid_points), 1))

    # --- ESTA É A CORREÇÃO ---
    # Usamos o método de ray tracing padrão do trimesh, que não depende de pyembree.
    _, index_ray, _ = tree_mesh.ray.intersects_location(
        ray_origins=ray_origins,
        ray_directions=ray_directions
    )
    
    in_sun_mask = np.ones(len(grid_points), dtype=bool)
    in_sun_mask[index_ray] = False
    return in_sun_mask

def run_full_simulation(config, solar_pos, grid_points):
    """Executa a simulação de sombreamento completa."""
    tree = create_tree_mesh(
        trunk_radius=config['tree']['trunk']['radius_m'],
        trunk_height=config['tree']['trunk']['height_m'],
        canopy_x=config['tree']['canopy']['x_radius_m'],
        canopy_y=config['tree']['canopy']['y_radius_m'],
        canopy_z=config['tree']['canopy']['z_radius_m'],
        v_offset=config['tree']['canopy']['vertical_offset_m']
    )
    tree_mesh_data = (tree.vertices, tree.faces)
    sun_vectors = get_sun_vectors(solar_pos)
    tasks = [(sun_vec, grid_points, tree_mesh_data) for sun_vec in sun_vectors]

    if config['simulation'].get('use_multiprocessing', True):
        num_cores = config['simulation'].get('cpu_cores') or cpu_count()
        with Pool(processes=num_cores) as pool:
            results = list(tqdm(pool.imap(run_simulation_for_timestep, tasks), total=len(tasks), desc="Simulando Raios"))
    else:
        results = [run_simulation_for_timestep(task) for task in tqdm(tasks, desc="Simulando Raios")]
        
    sun_exposure_matrix = np.array(results).T
    results_df = pd.DataFrame(sun_exposure_matrix,
                              columns=solar_pos.index,
                              index=[f"p_{i}" for i in range(len(grid_points))])
    return results_df

def calculate_sun_hours(results_df, freq_minutes):
    """Calcula o total de horas de sol para cada ponto."""
    sunlit_intervals = results_df.sum(axis=1)
    total_hours = (sunlit_intervals * freq_minutes) / 60.0
    return total_hours.values