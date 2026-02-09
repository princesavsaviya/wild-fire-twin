# PROJECT_STATE — Wildfire-Twin (Real-Time Digital Twin)

Last updated: 2026-02-09

This file is the “restart button” for the project. It captures what is working right now (Phase 0), the system contract (Kafka topic + message schema), and the exact commands to reproduce the full demo.

---

## 1) Current Phase

### Phase 0 (DONE): Local real-time pipeline (Kafka → Python Producer → Streamlit Dashboard)

**Working end-to-end:**
- Dockerized **Kafka + Zookeeper** starts via `./infra/start.sh`
- Kafka topic created via `./infra/create_topics.sh`
- Python producer publishes JSON events to Kafka topic **`fire_events`**
- Streamlit dashboard consumes Kafka and shows **live points + table**

---

## 2) Architecture (Phase 0)

```
+------------------+        +-------------------------+        +----------------------+
| Python Producer  |  JSON  | Kafka (Docker)          |  JSON  | Streamlit Dashboard  |
| data_generator.py+------->+ topic: fire_events      +------->+ dashboard/app.py     |
| localhost client |        | broker: localhost:9092  |        | localhost:8501       |
+------------------+        +-------------------------+        +----------------------+
```

**Kafka endpoints**
- Host access (Python apps on your machine): `localhost:9092`
- Internal Docker access (containers talking to Kafka): `kafka:29092` (if configured)

---

## 3) Repository layout (expected)

```
wild-fire-twin/
  infra/
    docker-compose.yml
    start.sh
    stop.sh
    create_topics.sh
    reset.sh            # optional
  producer/
    data_generator.py
  dashboard/
    app.py
  docs/
    PROJECT_STATE.md
  requirements.txt
  README.md
```

---

## 4) Runbook: “from zero to live dashboard”

### Step 1 — Start Kafka
```bash
./infra/start.sh
```

### Step 2 — Create topic
```bash
./infra/create_topics.sh
# or: ./infra/create_topics.sh fire_events
```

### Step 3 — Run producer
```bash
python producer/data_generator.py
```

### Step 4 — Run dashboard
```bash
streamlit run dashboard/app.py
```

Open: `http://localhost:8501`

---

## 5) Verification (ground truth)

### A) Confirm Kafka is receiving messages
```bash
docker-compose -f infra/docker-compose.yml exec -T kafka   kafka-console-consumer --bootstrap-server kafka:29092   --topic fire_events --max-messages 5
```

### B) Confirm Streamlit is receiving messages
In the dashboard:
- “Buffered events” should increase (or stay at max buffer)
- “Latest Events” table should not be empty
- Map should show points near Riverside, CA

---

## 6) Kafka Topic Contract

### Topic
- **Topic name:** `fire_events`
- **Message format:** JSON (UTF-8)

### Required fields
| Field | Type | Example |
|------|------|---------|
| event_time | string (ISO-8601, UTC) | `"2026-02-09T23:02:58.734757Z"` |
| event_id | string UUID | `"bed97026-8ef5-4ab7-9165-08b406d86b74"` |
| sensor_id | string | `"sensor_005"` |
| latitude | float | `33.9832781661` |
| longitude | float | `-117.3686247466` |
| temperature | float (°C) | `22.58` |
| is_fire | boolean | `false` |

### Example message
```json
{
  "event_time": "2026-02-09T23:02:58.734757Z",
  "event_id": "bed97026-8ef5-4ab7-9165-08b406d86b74",
  "sensor_id": "sensor_005",
  "latitude": 33.983278166104576,
  "longitude": -117.36862474657333,
  "temperature": 22.58,
  "is_fire": false
}
```

---

## 7) Configuration knobs

### Producer (`producer/data_generator.py`)
Common CLI flags (example):
```bash
python producer/data_generator.py --rate 10 --sensors 25 --fire-prob 0.03
```

Environment variables (if used):
- `KAFKA_BOOTSTRAP` (default `localhost:9092`)
- `KAFKA_TOPIC` (default `fire_events`)
- `EVENTS_PER_SEC`, `NUM_SENSORS`, `CENTER_LAT`, `CENTER_LON`, etc.

### Dashboard (`dashboard/app.py`)
- Kafka bootstrap (default `localhost:9092`)
- Topic (default `fire_events`)
- Start offset: `latest` / `earliest` (UI setting)
- Show all buffered events: ignore time window (UI setting)
- Map style: Carto basemap (no token needed)

---

## 8) Known issues + fixes

### Docker permission denied
If Docker commands require `sudo`, add user to docker group:
```bash
sudo groupadd docker 2>/dev/null || true
sudo usermod -aG docker $USER
newgrp docker
docker ps
```
If it still fails, log out and log back in.

### Port already allocated (2181 / 9092)
A previous Kafka/Zookeeper may already be running. Stop/remove it:
```bash
docker ps
docker stop <container_id>
docker rm <container_id>
```
Then restart:
```bash
./infra/start.sh
```

### Streamlit shows empty table/map even though Kafka has data
Most common causes:
- wrong topic/bootstrap in sidebar
- time window filter excludes old events → enable “Show all buffered events”
- consumer offset/group behavior → switch to `earliest` or reset group id (if implemented)

### “generator already executing” warning in Streamlit
If Kafka polling uses an iterator (`for msg in consumer:`), Streamlit reruns can collide.
Fix by using `consumer.poll()` pattern instead of generator iteration.

---

## 9) What’s next (Phase 1)

### Phase 1 goal: Spatial join (Fire stream × Building footprints)
- Load static building footprints (GeoJSON / Parquet) into Spark
- Spark Structured Streaming reads Kafka topic `fire_events`
- Apache Sedona spatial ops:
  - Convert points → `ST_Point(lon, lat)`
  - Buffer risk zone → `ST_Buffer(point, radius)`
  - Join risk zones with building polygons: `ST_Intersects(buffer, building_geom)`
- Output at-risk buildings to a sink (Kafka topic / Parquet / DB) for dashboard consumption

### Phase 2 goal: Real-time dashboard with at-risk buildings
- Streamlit reads risk results
- Map overlays:
  - live fire points
  - risk zones
  - highlighted “at-risk” buildings

### Phase 3 (optional): Predictive twin
- Add wind vector + short-horizon forecast polygon
- Show projected risk over next 10 minutes

---

## 10) Resume prompt (copy/paste for a new chat)

I am working on **Wildfire-Twin**. Phase 0 is working: Dockerized Kafka is running, topic **fire_events** exists, Python producer publishes JSON events with fields (event_time, sensor_id, lat/lon, temperature, is_fire), and Streamlit dashboard consumes Kafka and shows live points. Next is Phase 1: Spark 3.4.1 + Sedona spatial join between the live fire stream and building footprints to output “at-risk” structures.