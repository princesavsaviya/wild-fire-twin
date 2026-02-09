import pandas as pd
import numpy as np

# 1. Generate Fake "Critical Infrastructure" (Static Data)
# Randomly scattering hospitals around a center point (e.g., Santa Rosa, CA)
def get_static_infrastructure():
    # Real Hospital Data for Riverside, CA
    data = [
        {"name": "Riverside Community Hospital", "lat": 33.976664, "lon": -117.382645, "type": "Hospital"},
        {"name": "Parkview Community Hospital", "lat": 33.926914, "lon": -117.439392, "type": "Hospital"},
        {"name": "Kaiser Permanente Riverside", "lat": 33.904991, "lon": -117.469264, "type": "Hospital"},
        {"name": "Corona Regional Medical Center", "lat": 33.873061, "lon": -117.568370, "type": "Hospital"},
        {"name": "UC Riverside School of Medicine", "lat": 33.975000, "lon": -117.325000, "type": "Hospital"},
    ]
    return pd.DataFrame(data)

# 2. Generate Fake "Fire Perimeter" (Dynamic Data)
# Creates a hexagon shape that grows or moves based on time
def get_fire_polygon(t):
    # Center of fire moves slightly over time
    # Starting near Box Springs Mountain Reserve (East of Riverside)
    center_lat = 33.97 + (t * 0.001) 
    center_lon = -117.30 + (t * 0.001)
    
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