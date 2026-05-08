import os
import json
import time
import uuid
import random
import argparse
from datetime import datetime, timezone

from kafka import KafkaProducer


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def generate_event(sensor_id: str, center_lat: float, center_lon: float, jitter_meters: float,
                   base_temp_c: float, fire_prob: float) -> dict:
    """
    Generate a single sensor event near (center_lat, center_lon).

    jitter_meters is converted to an approximate degree jitter.
    This is fine for Phase 0 simulation; Phase 1 will handle accurate spatial ops.
    """
    # Rough conversion: 1 deg lat ~ 111,000 m; 1 deg lon ~ 111,000 m * cos(lat)
    lat_m_per_deg = 111_000.0
    lon_m_per_deg = 111_000.0 * max(0.2, abs(math_cos_deg(center_lat)))  # avoid tiny values

    dlat = random.uniform(-jitter_meters, jitter_meters) / lat_m_per_deg
    dlon = random.uniform(-jitter_meters, jitter_meters) / lon_m_per_deg

    lat = center_lat + dlat
    lon = center_lon + dlon

    # Determine if this event is a "fire spike"
    is_fire = random.random() < fire_prob
    temp_c = base_temp_c + random.uniform(-2.0, 2.0) + (random.uniform(20.0, 60.0) if is_fire else 0.0)

    return {
        "event_time": utc_now_iso(),
        "event_id": str(uuid.uuid4()),
        "sensor_id": sensor_id,
        "latitude": float(lat),
        "longitude": float(lon),
        "temperature": round(float(temp_c), 2),
        "is_fire": bool(is_fire),
    }


def math_cos_deg(deg: float) -> float:
    # small helper to avoid importing numpy
    import math
    return math.cos(math.radians(deg))


def build_producer(bootstrap: str) -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=[bootstrap],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
        acks="all",
        linger_ms=50,
        retries=5,
        request_timeout_ms=30_000,
    )


def main():
    parser = argparse.ArgumentParser(description="Wildfire-Twin Kafka Producer (sensor simulator)")
    parser.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"))
    parser.add_argument("--topic", default=os.getenv("KAFKA_TOPIC", "fire_events"))
    parser.add_argument("--rate", type=float, default=float(os.getenv("EVENTS_PER_SEC", "10")),
                        help="Events per second (approx).")
    parser.add_argument("--sensors", type=int, default=int(os.getenv("NUM_SENSORS", "25")))
    parser.add_argument("--center-lat", type=float, default=float(os.getenv("CENTER_LAT", "33.9806")))
    parser.add_argument("--center-lon", type=float, default=float(os.getenv("CENTER_LON", "-117.3755")))
    parser.add_argument("--jitter-m", type=float, default=float(os.getenv("JITTER_METERS", "1500")),
                        help="Max random displacement from center (meters).")
    parser.add_argument("--base-temp-c", type=float, default=float(os.getenv("BASE_TEMP_C", "24")))
    parser.add_argument("--fire-prob", type=float, default=float(os.getenv("FIRE_PROB", "0.03")),
                        help="Probability that an event is a fire spike.")
    parser.add_argument("--print-every", type=int, default=int(os.getenv("PRINT_EVERY", "50")))
    args = parser.parse_args()

    if args.rate <= 0:
        raise ValueError("--rate must be > 0")
    if not (0.0 <= args.fire_prob <= 1.0):
        raise ValueError("--fire-prob must be between 0 and 1")

    producer = build_producer(args.bootstrap)

    # Pre-generate sensor IDs
    sensor_ids = [f"sensor_{i:03d}" for i in range(args.sensors)]

    interval = 1.0 / args.rate
    sent = 0
    started = time.time()

    print("=== Wildfire-Twin Producer ===")
    print(f"Bootstrap : {args.bootstrap}")
    print(f"Topic     : {args.topic}")
    print(f"Rate      : {args.rate} events/sec")
    print(f"Sensors   : {args.sensors}")
    print(f"Center    : ({args.center_lat}, {args.center_lon})  jitter={args.jitter_m}m")
    print(f"Fire prob : {args.fire_prob}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            sensor_id = random.choice(sensor_ids)

            event = generate_event(
                sensor_id=sensor_id,
                center_lat=args.center_lat,
                center_lon=args.center_lon,
                jitter_meters=args.jitter_m,
                base_temp_c=args.base_temp_c,
                fire_prob=args.fire_prob,
            )

            # Use sensor_id as key to keep per-sensor ordering (helpful later)
            producer.send(args.topic, key=sensor_id, value=event)
            sent += 1

            if sent % args.print_every == 0:
                elapsed = time.time() - started
                eps = sent / elapsed if elapsed > 0 else 0.0
                print(f"[sent={sent}] avg_rate={eps:.2f} events/sec  last_event={event}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopping producer...")

    finally:
        try:
            producer.flush(10)
        except Exception:
            pass
        try:
            producer.close(10)
        except Exception:
            pass
        print("Producer stopped.")


if __name__ == "__main__":
    main()
