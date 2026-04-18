#!/usr/bin/env bash
set -euo pipefail

TOPICS=(messages.sent messages.read presence.changed)

for topic in "${TOPICS[@]}"; do
  docker compose exec -T kafka kafka-topics \
    --bootstrap-server localhost:9092 \
    --create --if-not-exists \
    --topic "$topic" \
    --partitions 1 --replication-factor 1
done

echo "--- Topics existentes ---"
docker compose exec -T kafka kafka-topics \
  --bootstrap-server localhost:9092 --list
