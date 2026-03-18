# Wildfire-Twin (Real-Time Digital Twin)

A real-time "digital twin" prototype for wildfire monitoring and predictive risk analysis.
It ingests simulated or live high-velocity IoT sensor events (fire/temperature/wind points) through Kafka, processes them in real-time using Apache Spark Structured Streaming with Apache Sedona for spatial joins against static infrastructure data (building footprints), and stores alerts in DuckDB. A Streamlit dashboard provides live visualization of at-risk buildings based on dynamic wind-cone projections.

This project is being implemented by Prince Savsaviya, Viswanadh Rahul Challa, Anish A. Kale, and Ali Rezayi Nejad at UC Riverside.

---

## Current Status (Phases 1-3 Complete)

**Kafka Data Ingestion**: Robust message brokering via local Docker stack.  
**Apache Spark & Sedona Spatial Engine**: Real-time evaluation of fire sensor data against a master building dataset. Constructs predictive wind cones using native SQL optimizations.   
**DuckDB Alert Sink**: High-performance, low-latency persistent storage for active fire threats.  
**Live Streamlit Dashboard**: PyDeck-accelerated 3D mapping of live alerts, infrastructure distribution, and a "What-If" simulation mode for dropping localized fires.  
**Latency Optimized**: Sustains < 30s p95 end-to-end latency (tested at 6-18s) using native expressions and optimized micro-batch triggers.

---

## Tech Stack

- **Python:** 3.11
- **Message Broker:** Kafka (via Docker Compose)
- **Stream Processor:** Apache Spark 3.4.1 (PySpark)
- **Spatial Engine:** Apache Sedona 1.7.0
- **Storage/Sink:** DuckDB
- **Dashboard:** Streamlit + PyDeck
- **Java Environment:** OpenJDK 11 (required for Spark)

---

## Prerequisites

1.  **Docker & Docker Compose**: Required for running the Kafka broker.
2.  **Python 3.11**: Conda environment highly recommended.
3.  **Java 11**: `JAVA_HOME` must be set properly for Spark execution.
4.  **Hadoop/Winutils (Windows Only)**: Required by Spark on Windows. The pipeline attempts to auto-resolve this if `infra/hadoop` exists, but setting `HADOOP_HOME` manually is safest.

---

## How to Run from Scratch

### 1. Environment Setup
```bash
# Create and activate a conda environment
conda create -n wildfire python=3.11 -y
conda activate wildfire

# Install dependencies
pip install -r requirements.txt
```

### 2. Start Kafka
```bash
# From the project root
cd infra
docker-compose up -d
cd ..

# Create the required Kafka topics (fire_events, at_risk_assets)
./infra/create_topics.sh
```

### 3. Launch the Unified Pipeline (Recommended)
On Windows, you can launch all components simultaneously using the provided PowerShell script:
```powershell
.\run_all.ps1
```
This script sequentially starts Kafka, the Alert Sink Consumer, the Spark Spatial Engine, and the Streamlit Dashboard in separate windows.

### Manual Launch (Alternative)
If you prefer starting services manually, use separate terminal windows (ensure the `wildfire` conda env is active in each):

**Terminal 1: Alert Sink Consumer**
```bash
python alert_sink/consumer.py
```

**Terminal 2: Spark Spatial Engine**
```bash
python spark_processor/spatial_engine.py
```

**Terminal 3: Streamlit Dashboard**
```bash
streamlit run dashboard/backend/app.py
```

### 4. Triggering Simulations
The system requires data to visualize. You can trigger data in two ways:
1.  **Via Dashboard**: Open the Streamlit dashboard (`localhost:8501`), navigate to the "Simulation" tab, select a target city, click on the map, and set the parameters to trigger a localized fire.
2.  **Via Full-Scale Script**: For load/latency testing across multiple cities, run:
    ```bash
    python scripts/populate_for_latency_test.py
    ```

---

## How to Use a Different Dataset

By default, the project uses a California Essential Buildings dataset located at `data/california_essential_buildings.parquet`. To swap this out for your own spatial dataset:

### Step 1: Prepare Your Data
Your dataset must be saved as a `.parquet` file and contain, at minimum, a geometry column (WKB format is standard) and identifiers (e.g., `building_type`, `building_name`). 

### Step 2: Update Data Paths
You must update the file paths in two core components:

1.  **Spark Spatial Engine (`spark_processor/spatial_engine.py`)**:
    Change the `BUILDING_DATA_PATH` variable (around line 30) to point to your new `.parquet` file.
    ```python
    BUILDING_DATA_PATH = os.path.join(os.getcwd(), "data", "your_custom_dataset.parquet")
    ```
    *Note: Adjust the Spark SQL query on line 99 if your column names differ from `building_type`, `building_name`, and `geometry`.*

2.  **Dashboard Data Loader (`dashboard/backend/data_loader.py`)**:
    Change the `DATA_PATH` variable (around line 19) to match your new file.
    ```python
    DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "your_custom_dataset.parquet")
    ```

### Step 3: Update Dashboard Styling (Optional)
If your new dataset uses different values for `building_type`, you may want to update the semantic categorization logic in `dashboard/backend/data_loader.py` `categorize()` function to ensure the PyDeck map colors your assets correctly.

---

## Measuring Performance & Latency

End-to-end pipeline latency (the time from an event entering Kafka to being queryable in DuckDB after spatial joining) is heavily optimized. To verify the <30s SLA:

1. Ensure the pipeline is running (`run_all.ps1`).
2. Run the load generator: `python scripts/populate_for_latency_test.py`
3. Wait approximately 20-30 seconds.
4. Measure latency: `python tests/measure_latency.py`

This will print a statistical report and generate a `latency_distribution.png` CDF/Histogram chart.
