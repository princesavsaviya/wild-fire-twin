"""
Populate Simulation DB for Latency Measurement
-----------------------------------------------
Fires 1000+ simulation events across all 10 major California cities
in batches to exercise the full Spark -> DuckDB pipeline.
Run AFTER the full pipeline (Kafka + Spark + alert_sink) is up.
"""

import os
import sys
import json
import uuid
import time
import math
import random
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kafka import KafkaProducer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC     = os.getenv("KAFKA_TOPIC_INPUT", "fire_events")

CITIES = {
    "Riverside":     (33.9533, -117.3961),
    "Los Angeles":   (34.0522, -118.2437),
    "San Francisco": (37.7749, -122.4194),
    "San Diego":     (32.7157, -117.1611),
    "Sacramento":    (38.5816, -121.4944),
    "San Jose":      (37.3382, -121.8863),
    "Fresno":        (36.7378, -119.7871),
    "Bakersfield":   (35.3733, -119.0187),
    "Anaheim":       (33.8366, -117.9143),
    "Santa Ana":     (33.7455, -117.8677),
}

TOTAL_EVENTS  = 1000
SCATTER_MILES = 5.0  # scatter within 5-mile radius of each city center

def scatter(lat, lon, radius_miles):
    lat_deg = 1.0 / 69.0
    lon_deg = 1.0 / (69.0 * math.cos(math.radians(lat)))
    r     = radius_miles * math.sqrt(random.random())
    theta = random.uniform(0, 2 * math.pi)
    return lat + r * math.cos(theta) * lat_deg, lon + r * math.sin(theta) * lon_deg

def main():
    print(f"Connecting to Kafka at {BOOTSTRAP}...")
    producer = KafkaProducer(
        bootstrap_servers=[BOOTSTRAP],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
        linger_ms=5,
        batch_size=16384 * 4,
    )

    city_names  = list(CITIES.keys())
    events_sent = 0
    per_city    = TOTAL_EVENTS // len(city_names)
    extra       = TOTAL_EVENTS % len(city_names)

    print(f"Firing {TOTAL_EVENTS} events across {len(city_names)} cities...")
    start = time.time()

    for i, (city, (lat, lon)) in enumerate(CITIES.items()):
        count = per_city + (1 if i < extra else 0)
        for _ in range(count):
            fire_lat, fire_lon = scatter(lat, lon, SCATTER_MILES)
            event = {
                "event_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "event_id":   f"sim_{uuid.uuid4()}",
                "sensor_id":  f"populate_{city.lower().replace(' ', '_')}",
                "latitude":   fire_lat,
                "longitude":  fire_lon,
                "temperature": round(random.uniform(80, 115), 1),
                "is_fire":    True,
                "wind_speed_mph":      round(random.uniform(5, 35), 1),
                "wind_direction_deg":  round(random.uniform(0, 360), 1),
                "humidity_percent":    round(random.uniform(10, 40), 1),
            }
            producer.send(TOPIC, value=event)
            events_sent += 1

        print(f"  [{city}] Sent {count} events  (total: {events_sent})")

    producer.flush()
    producer.close()
    elapsed = time.time() - start

    print(f"\nDone. {events_sent} events published in {elapsed:.2f}s "
          f"({events_sent / elapsed:.0f} ev/s)")
    print("Give Spark 20-30s to process, then run:  tests/measure_latency.py")

if __name__ == "__main__":
    main()
