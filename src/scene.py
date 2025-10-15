import numpy as np
import trimesh
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon

def create_circular_area(radius, center=(0, 0)):
    """Cria uma área circular (Polygon)."""
    return Point(center).buffer(radius)

def create_grid_points(area, resolution):
    """Gera uma grade de pontos dentro de uma área."""
    xmin, ymin, xmax, ymax = area.bounds
    x_coords = np.arange(xmin, xmax, resolution)
    y_coords = np.arange(ymin, ymax, resolution)
    
    points_2d = []
    for x in x_coords:
        for y in y_coords:
            point = Point(x, y)
            if area.contains(point):
                points_2d.append((x, y))
    
    points_3d = np.array([[p[0], p[1], 0] for p in points_2d])
    return points_3d

def create_tree_mesh(trunk_radius, trunk_height, canopy_x, canopy_y, canopy_z, v_offset):
    """Cria um modelo 3D de uma árvore."""
    trunk = trimesh.creation.cylinder(radius=trunk_radius, height=trunk_height)
    trunk.apply_translation([0, 0, trunk_height / 2])
    canopy = trimesh.creation.icosphere(subdivisions=4)
    canopy.apply_scale([canopy_x, canopy_y, canopy_z])
    canopy.apply_translation([0, 0, v_offset])
    tree_mesh = trimesh.util.concatenate([trunk, canopy])
    return tree_mesh

def create_scene(tree_mesh):
    """Cria um objeto trimesh.Scene contendo a árvore."""
    scene = trimesh.Scene(tree_mesh)
    return scene