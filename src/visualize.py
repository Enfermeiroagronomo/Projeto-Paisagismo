import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import griddata
import os

def create_heatmap(grid_points, sun_hours, resolution, radius, dpi=300):
    """Gera e salva um heatmap de exposição solar."""
    x = grid_points[:, 0]
    y = grid_points[:, 1]
    z = sun_hours
    
    if len(x) < 4: # griddata precisa de pelo menos 4 pontos
        print("Não há pontos suficientes para gerar o heatmap.")
        return None

    grid_x, grid_y = np.mgrid[-radius:radius:500j, -radius:radius:500j]
    grid_z = griddata((x, y), z, (grid_x, grid_y), method='cubic')
    
    fig, ax = plt.subplots(figsize=(8, 8))
    c = ax.imshow(grid_z.T, extent=(-radius, radius, -radius, radius), origin='lower',
                  cmap='viridis', interpolation='hermite')
    fig.colorbar(c, ax=ax, shrink=0.8, label='Horas de Sol Direto')
    circle = plt.Circle((0, 0), radius, color='white', fill=False, linestyle='--', linewidth=1.5)
    ax.add_artist(circle)
    ax.set_aspect('equal')
    ax.set_xlim(-radius - 1, radius + 1)
    ax.set_ylim(-radius - 1, radius + 1)
    ax.set_xlabel("Distância (m)")
    ax.set_ylabel("Distância (m)")
    ax.set_title("Mapa de Calor de Exposição Solar")
    ax.grid(False)
    
    filename = os.path.join("output", "solar_heatmap.png")
    plt.savefig(filename, dpi=dpi, bbox_inches='tight')
    plt.close(fig)
    return filename

def create_planting_plan(grid_points, sun_hours, plant_catalog, luminosity_classes, radius):
    """Gera uma planta baixa com sugestões de plantio."""
    fig, ax = plt.subplots(figsize=(10, 10))
    colors = {
        'full_sun': 'gold',
        'partial_shade': 'yellowgreen',
        'full_shade': 'darkgreen'
    }
    labels = {
        'full_sun': f"Sol Pleno (≥ {luminosity_classes['full_sun']['min_hours']}h)",
        'partial_shade': f"Meia Sombra ({luminosity_classes['partial_shade']['min_hours']}-{luminosity_classes['partial_shade']['max_hours']}h)",
        'full_shade': f"Sombra Plena (< {luminosity_classes['full_shade']['max_hours']}h)"
    }
    
    point_classes = []
    for h in sun_hours:
        if h >= luminosity_classes['full_sun']['min_hours']:
            point_classes.append('full_sun')
        elif h >= luminosity_classes['partial_shade']['min_hours']:
            point_classes.append('partial_shade')
        else:
            point_classes.append('full_shade')
            
    for l_class in ['full_sun', 'partial_shade', 'full_shade']:
        mask = np.array(point_classes) == l_class
        if np.any(mask):
            ax.scatter(grid_points[mask, 0], grid_points[mask, 1], 
                       c=colors[l_class], label=labels[l_class], s=50,
                       edgecolors='black', linewidth=0.5)

    boundary = plt.Circle((0, 0), radius, color='gray', fill=False, linestyle='-', linewidth=2)
    trunk = plt.Circle((0, 0), 0.25, color='saddlebrown', fill=True)
    ax.add_artist(boundary)
    ax.add_artist(trunk)

    ax.legend(title="Classificação de Luminosidade")
    ax.set_aspect('equal')
    ax.set_xlim(-radius - 1, radius + 1)
    ax.set_ylim(-radius - 1, radius + 1)
    ax.set_xlabel("Distância (m)")
    ax.set_ylabel("Distância (m)")
    ax.set_title("Planta Baixa com Slots de Plantio Sugeridos")
    ax.grid(True, linestyle=':', alpha=0.6)

    filename = os.path.join("output", "planting_plan.png")
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return filename