#!/usr/bin/env bash
set -e

TOPIC=${1:-fire_events}

docker-compose -f infra/docker-compose.yml exec -T kafka \
  kafka-topics --bootstrap-server kafka:29092 \
  --create --if-not-exists --topic "$TOPIC" --partitions 1 --replication-factor 1

echo "✅ Topic ready: $TOPIC"
