import streamlit as st
import pydeck as pdk
import pandas as pd
from data_generator import get_static_infrastructure, get_fire_polygon

# --- Page Config ---
st.set_page_config(layout="wide", page_title="Wildfire Digital Twin")

# --- Header ---
st.title("🔥 Real-Time Wildfire Resilience Twin")
st.markdown("Monitoring active fire perimeters and critical infrastructure risk.")

# --- Sidebar Controls ---
st.sidebar.header("Simulation Controls")
time_step = st.sidebar.slider("Simulation Time (Minutes)", 0, 60, 0)
wind_speed = st.sidebar.metric(label="Live Wind Speed", value="45 mph")
wind_dir = st.sidebar.metric(label="Wind Direction", value="North-East")

# --- Load Data ---
# 1. Load Static Infrastructure
df_infra = get_static_infrastructure()

# 2. Load Dynamic Fire Data (based on the slider)
fire_data = get_fire_polygon(time_step)

# --- Define Visual Layers (The "Cake") ---

# Layer 1: Critical Infrastructure (Blue dots)
layer_infra = pdk.Layer(
    "ScatterplotLayer",
    df_infra,
    get_position="[lon, lat]",
    get_color="[0, 128, 255, 160]", # Blue
    get_radius=200,
    pickable=True,
    auto_highlight=True,
)

# Layer 2: The Fire (Red, semi-transparent polygon)
layer_fire = pdk.Layer(
    "PolygonLayer",
    fire_data,
    get_polygon="path",
    get_fill_color="[255, 0, 0, 100]", # Red with transparency
    get_line_color="[255, 0, 0, 255]",
    get_line_width=50,
    pickable=True,
)

# Layer 3: Risk Zone (Yellow Cone - Simulated logic)
# (In a real app, this would be calculated by Spark)
# For now, we visualize the concept
risk_zone_data = [{"path": [
    [-122.71 + (time_step * 0.001), 38.44 + (time_step * 0.001)], # Fire Center
    [-122.75 + (time_step * 0.001), 38.40 + (time_step * 0.001)], # Wide point A
    [-122.65 + (time_step * 0.001), 38.40 + (time_step * 0.001)], # Wide point B
]}]

layer_risk = pdk.Layer(
    "PolygonLayer",
    risk_zone_data,
    get_polygon="path",
    get_fill_color="[255, 165, 0, 80]", # Orange/Yellow
    stroked=False,
)

# --- Render the Map ---
# Set the initial camera view (Santa Rosa, CA)
view_state = pdk.ViewState(
    latitude=38.44,
    longitude=-122.71,
    zoom=11,
    pitch=50, # Tilts the map for 3D effect
)

# Create the deck
r = pdk.Deck(
    layers=[layer_risk, layer_fire, layer_infra],
    initial_view_state=view_state,
    map_style="mapbox://styles/mapbox/dark-v10", # Dark mode looks "serious"
    tooltip={"text": "{name}"}
)

# Display in Streamlit
st.pydeck_chart(r)

# --- Alert Logic ---
# Simple logic to show how alerts would look
if time_step > 30:
    st.error("🚨 ALERT: 3 Hospitals are now in the Projected Risk Zone!")
    st.table(df_infra.head(3)) # Show the specific hospitals
else:
    st.success("✅ Status: Monitoring. No immediate infrastructure threat.")