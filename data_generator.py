import pandas as pd
import numpy as np

# 1. Generate Fake "Critical Infrastructure" (Static Data)
# Randomly scattering hospitals around a center point (e.g., Santa Rosa, CA)
def get_static_infrastructure():
    data = []
    # Center approx: 38.44, -122.71
    for i in range(50):
        lat = 38.44 + np.random.uniform(-0.1, 0.1)
        lon = -122.71 + np.random.uniform(-0.1, 0.1)
        data.append({"name": f"Hospital {i}", "lat": lat, "lon": lon, "type": "Hospital"})
    return pd.DataFrame(data)

# 2. Generate Fake "Fire Perimeter" (Dynamic Data)
# Creates a hexagon shape that grows or moves based on time
def get_fire_polygon(t):
    # Center of fire moves slightly over time
    center_lat = 38.44 + (t * 0.001) 
    center_lon = -122.71 + (t * 0.001)
    
    # Create a small hexagon shape for the fire
    radius = 0.02 # Size of fire
    polygon = []
    for i in range(6):
        angle = 2 * np.pi * i / 6
        x = center_lon + radius * np.cos(angle)
        y = center_lat + radius * np.sin(angle)
        polygon.append([x, y])
    
    # PyDeck expects the first point to match the last point to close the loop
    polygon.append(polygon[0])
    
    return [{"name": "Fire Alpha", "path": polygon}]