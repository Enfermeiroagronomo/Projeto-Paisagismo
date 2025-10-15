import ezdxf
import pandas as pd
import os

def export_to_dxf(results_df, config, filename="output/planting_layout.dxf"):
    """Exporta o layout de plantio para um arquivo DXF."""
    doc = ezdxf.new()
    msp = doc.modelspace()

    l_classes = config['luminosity_classes']
    colors = {
        'full_sun': 1,      # Red
        'partial_shade': 3, # Green
        'full_shade': 5,    # Blue
        'boundary': 7       # White/Black
    }
    
    for name, color_index in colors.items():
        doc.layers.new(name=name.upper(), dxfattribs={'color': color_index})

    msp.add_circle(
        center=(0, 0),
        radius=config['scene']['radius_m'],
        dxfattribs={'layer': 'BOUNDARY'}
    )
    msp.add_circle(
        center=(0, 0),
        radius=config['tree']['trunk']['radius_m'],
        dxfattribs={'layer': 'BOUNDARY'}
    )

    for _, row in results_df.iterrows():
        h = row['sun_hours']
        point = (row['x'], row['y'])
        
        if h >= l_classes['full_sun']['min_hours']:
            layer = 'FULL_SUN'
        elif h >= l_classes['partial_shade']['min_hours']:
            layer = 'PARTIAL_SHADE'
        else:
            layer = 'FULL_SHADE'
        
        msp.add_point(point, dxfattribs={'layer': layer})

    # Garante que o diretório de saída existe
    output_dir = os.path.dirname(filename)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    doc.saveas(filename)
    print(f"Layout exportado para {filename}")