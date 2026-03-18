"""
Wildfire Twin — Streamlit Dashboard

Architecture:
  - Building data loaded from GeoParquet (cached)
  - Alerts loaded from DuckDB live store (populated by alert_sink consumer)
  - NO direct Kafka consumption — fully decoupled
"""

import os
import sys
import json
import uuid
import random
import math
from datetime import datetime, timezone
import streamlit as st
import pydeck as pdk
import folium
from streamlit_folium import st_folium
from kafka import KafkaProducer

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.backend.data_loader import (
    check_data_exists,
    load_and_classify_buildings,
    load_alerts,
    load_alert_count,
    filter_to_viewport,
)
from dashboard.backend.map_layers import (
    build_static_layers,
    build_dynamic_layers,
    apply_alert_highlighting,
)
from scripts.fetch_weather_data import fetch_live_weather
from alert_sink.duckdb_store import delete_simulations

# --- Kafka Simulation Logic ---
def trigger_simulation(lat: float, lon: float, temp: float, count: int = 1, radius_miles: float = 0.0):
    """Publish `count` fire events randomly scattered within `radius_miles` of (lat, lon)."""
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
    topic = os.getenv("KAFKA_TOPIC_INPUT", "fire_events")
    producer = KafkaProducer(
        bootstrap_servers=[bootstrap],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all"
    )
    
    # Approx degrees per mile
    DEG_PER_MILE_LAT = 1.0 / 69.0
    DEG_PER_MILE_LON = 1.0 / (69.0 * math.cos(math.radians(lat)))
    
    live_weather = fetch_live_weather(lat, lon)
    if not live_weather:
        live_weather = {
            "temperature_f": temp,
            "humidity_percent": 30.0,
            "wind_speed_mph": 0.0,
            "wind_direction_deg": 0.0
        }
    
    for _ in range(max(1, count)):
        # Random polar offset within the requested radius
        r = radius_miles * math.sqrt(random.random())  # sqrt for uniform disc distribution
        theta = random.uniform(0, 2 * math.pi)
        fire_lat = lat + r * math.cos(theta) * DEG_PER_MILE_LAT
        fire_lon = lon + r * math.sin(theta) * DEG_PER_MILE_LON
        
        event = {
            "event_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event_id": f"sim_{uuid.uuid4()}",
            "sensor_id": "dashboard_sim",
            "latitude": fire_lat,
            "longitude": fire_lon,
            "temperature": float(live_weather["temperature_f"]),
            "is_fire": True,
            "wind_speed_mph": float(live_weather["wind_speed_mph"]),
            "wind_direction_deg": float(live_weather["wind_direction_deg"]),
            "humidity_percent": float(live_weather["humidity_percent"])
        }
        producer.send(topic, value=event)
    
    producer.flush()
    producer.close()
    return count

# --- Page Config ---
st.set_page_config(layout="wide", page_title="California Essential Buildings")
st.title("California Essential Infrastructure")
st.caption("State-wide fusion of 11.5M Microsoft structural polygons and 79k OpenStreetMap POIs.")

# --- Data Validation ---
check_data_exists()

# --- City Coordinate Registry ---
CITIES = {
    "Riverside": (33.9533, -117.3961),
    "Los Angeles": (34.0522, -118.2437),
    "San Francisco": (37.7749, -122.4194),
    "San Diego": (32.7157, -117.1611),
    "Sacramento": (38.5816, -121.4944),
    "San Jose": (37.3382, -121.8863),
    "Fresno": (36.7378, -119.7871),
    "Bakersfield": (35.3733, -119.0187),
    "Anaheim": (33.8366, -117.9143),
    "Santa Ana": (33.7455, -117.8677),
    "California (Whole State)": (36.7783, -119.4179),
}

# Only the named cities (excluding whole-state entry) for nearest-city lookup
NAMED_CITIES = {k: v for k, v in CITIES.items() if "California" not in k}

def find_nearest_city(lat: float, lon: float) -> tuple:
    """Return (city_lat, city_lon) of the named city closest to the given coordinate."""
    best, best_dist = None, float("inf")
    for city_lat, city_lon in NAMED_CITIES.values():
        dist = (lat - city_lat) ** 2 + (lon - city_lon) ** 2
        if dist < best_dist:
            best_dist = dist
            best = (city_lat, city_lon)
    return best or (34.0522, -118.2437)  # default: Los Angeles

# --- Sidebar: Simulation Viewport Navigation ---
with st.sidebar:
    st.header("Navigation")
    
    selected_city = st.selectbox(
        "Simulation Viewport", list(CITIES.keys()), index=0
    )
    st.caption("Used in the Simulation tab to select your ignition area.")

    st.divider()
    st.header("Mode Selection")
    
    # We'll use Streamlit Tabs in the main view instead of radio buttons for the primary mode
    
# --- Load Buildings (Static, cached) ---
with st.spinner("Processing state-wide assets..."):
    full_gdf = load_and_classify_buildings()

# --- Compute Live Viewport: nearest city to active fires, default LA ---
_live_alerts_early = load_alerts(limit=500, source="live")
if _live_alerts_early:
    fire_lats = [a["fire_lat"] for a in _live_alerts_early if a.get("fire_lat")]
    fire_lons = [a["fire_lon"] for a in _live_alerts_early if a.get("fire_lon")]
    if fire_lats:
        centroid_lat = sum(fire_lats) / len(fire_lats)
        centroid_lon = sum(fire_lons) / len(fire_lons)
        live_center_lat, live_center_lon = find_nearest_city(centroid_lat, centroid_lon)
    else:
        live_center_lat, live_center_lon = NAMED_CITIES["Los Angeles"]
else:
    live_center_lat, live_center_lon = NAMED_CITIES["Los Angeles"]

live_zoom = 12
live_visible_gdf = filter_to_viewport(full_gdf, live_center_lat, live_center_lon)

# --- Compute Simulation Viewport: driven by sidebar city selector ---
sim_center_lat, sim_center_lon = CITIES[selected_city]
if "California" in selected_city:
    sim_zoom = 6
    sim_visible_gdf = full_gdf
else:
    sim_zoom = 12
    sim_visible_gdf = filter_to_viewport(full_gdf, sim_center_lat, sim_center_lon)

# --- Main Content Area: Tabs ---
tab_live, tab_sim = st.tabs(["Live Stream", "Simulation"])

# Define parameterizable fragment for maps
@st.fragment(run_every=5)
def render_map_and_footer(source, map_key, viewport_lat, viewport_lon, zoom, visible_gdf):
    # Load fresh alerts
    alerts = load_alerts(limit=500, source=source)
    
    # Copy visible GDF so we don't mutate the cached layer, then highlight
    gdf_copy = apply_alert_highlighting(visible_gdf.copy(), alerts)
    
    # Build Map Layers
    static_layers = build_static_layers(gdf_copy)
    dynamic_layers = build_dynamic_layers(alerts)
    all_layers = static_layers + dynamic_layers
    
    # Render Map
    view_state = pdk.ViewState(
        latitude=viewport_lat,
        longitude=viewport_lon,
        zoom=zoom,
        pitch=45,
    )
    
    deck = pdk.Deck(
        views=[pdk.View(type="MapView", controller=True)],
        layers=all_layers,
        initial_view_state=view_state,
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        tooltip={
            "text": "Facility: {building_name}\nCategory: {category}\nRaw Type: {building_type}"
        },
    )
    
    st.pydeck_chart(deck, height=600, key=map_key)
    
    # Render Footer
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Category Distribution")
        if not visible_gdf.empty:
            st.dataframe(visible_gdf['category'].value_counts())
    with col2:
        st.subheader("Legend")
        st.markdown("**Medical** (Hospitals)")
        st.markdown("**Education** (Schools)")
        st.markdown("**Emergency** (Fire, Police)")
        st.markdown("**ALERT** (Inside Wind Cone)")
    with col3:
        st.subheader("System Health")
        st.metric("Total Master Buildings", f"{len(full_gdf):,}")
        st.metric(f"Active Alerts ({source.capitalize()})", load_alert_count(source=source))

with tab_live:
    st.subheader("Live Satellite & Sensor Data")
    
    col_trigger, col_info = st.columns([1, 2])
    with col_trigger:
        if st.button("Fetch Live Satellite Data (NASA FIRMS)", use_container_width=True):
            with st.spinner("Triggering NASA FIRMS Ingest..."):
                os.system("start /B powershell -Command \".\wildfire\python.exe producer/nasa_firms_ingest.py\"")
            st.success("FIRMS data ingest triggered!")
            
    with col_info:
        st.info("Showing real-time aggregated alerts from live data feeds.")

    # Live Alert Panel — auto-refreshes from DuckDB every 5 seconds
    @st.fragment(run_every=5)
    def live_alert_panel_live_tab():
        alerts = load_alerts(limit=100, source="live")
        alert_count = len(alerts)

        if alerts:
            st.metric("Active Live Alerts", alert_count)

            # Weather context from most recent alert
            latest = alerts[0]
            st.info(
                f"**Live Weather Context:**\n"
                f"Temp: {latest.get('temperature', '--')}F\n"
                f"Humidity: {latest.get('humidity_percent', '--')}%\n"
                f"Wind: {latest.get('wind_speed_mph', '--')} mph @ "
                f"{latest.get('wind_direction_deg', '--')} degrees"
            )

            # Show the most recent 5 alerts
            for alert in alerts[:5]:
                st.warning(
                    f"**RISK**: {alert.get('building_name', 'Unnamed Facility')}\n"
                    f"Type: {alert.get('building_type')}"
                )
        else:
            st.info("No active live fire threats detected.")

    live_alert_panel_live_tab()
    
    # Render Live Map — auto-centered on nearest city to live fires
    render_map_and_footer("live", f"map_live_{live_center_lat:.2f}", live_center_lat, live_center_lon, live_zoom, live_visible_gdf)

with tab_sim:
    st.subheader("Simulation Mode (What-If Scenarios)")
    
    col_sim_controls, col_sim_alerts = st.columns([1, 1])
    
    with col_sim_controls:
        st.caption("1. Click the map below to choose an ignition point.")
        
        # Folium Mini-Map for coordinate selection
        m = folium.Map(location=[CITIES[selected_city][0], CITIES[selected_city][1]], zoom_start=10)
        m.add_child(folium.LatLngPopup())
        map_data = st_folium(m, height=250, use_container_width=True, returned_objects=["last_clicked"])
        
        sim_lat = CITIES[selected_city][0]
        sim_lon = CITIES[selected_city][1]
        
        if map_data and map_data.get("last_clicked"):
            sim_lat = map_data["last_clicked"]["lat"]
            sim_lon = map_data["last_clicked"]["lng"]

        with st.form("sim_form"):
            st.write(f"**Target Coordinates:** `{sim_lat:.5f}`, `{sim_lon:.5f}`")
            st.caption("2. Set fire parameters and simulate.")
            sim_temp = st.slider("Fallback Temp (F)", min_value=50.0, max_value=120.0, value=85.0)
            sim_count = st.slider("Number of Fire Events", min_value=1, max_value=20, value=1, step=1)
            sim_radius = st.slider("Scatter Radius (miles)", min_value=0.0, max_value=10.0, value=0.0, step=0.5,
                                   help="How far from the clicked point fires can randomly scatter. 0 = exact point.")
            
            if st.form_submit_button("Simulate Fire Here"):
                with st.spinner(f"Publishing {sim_count} fire event(s) to Kafka..."):
                    n = trigger_simulation(sim_lat, sim_lon, sim_temp, count=sim_count, radius_miles=sim_radius)
                st.success(f"{n} fire event(s) triggered within {sim_radius:.1f} mi radius!")

        if st.button("Clear Previous Simulations", use_container_width=True):
            delete_simulations()
            st.toast("All simulated data wiped from metrics.")
            
    with col_sim_alerts:
        @st.fragment(run_every=5)
        def live_alert_panel_sim_tab():
            alerts = load_alerts(limit=100, source="sim")
            alert_count = len(alerts)

            if alerts:
                st.metric("Active Simulated Alerts", alert_count)
                for alert in alerts[:5]:
                    st.warning(
                        f"**RISK**: {alert.get('building_name', 'Unnamed Facility')}\n"
                        f"Type: {alert.get('building_type')}"
                    )
            else:
                st.info("No active simulated threats.")

        live_alert_panel_sim_tab()
        
    # Render Sim Map — viewport driven by sidebar city selector
    render_map_and_footer("sim", f"map_sim_{selected_city}", sim_center_lat, sim_center_lon, sim_zoom, sim_visible_gdf)



