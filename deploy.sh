#!/bin/bash
set -e

echo "=== Building and starting IAR stack ==="
docker compose up -d --build

echo "=== Waiting for iar-api ==="
until curl -sf http://localhost:8010/health > /dev/null 2>&1; do
  echo "  waiting..."
  sleep 3
done
echo "  iar-api is up"

echo "=== Deploying BPMN to ZorroBPM ==="
BPMN_XML=$(cat bpmn/iar-routing.bpmn | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
RESPONSE=$(curl -sf -X POST https://bpm.zorro.kt/process-definitions \
  -H 'Content-Type: application/json' \
  -d "{\"bpmn\": $BPMN_XML}")
echo "  Deployed: $RESPONSE"
echo "=== Done. Frontend: https://iar.zorro.kt ==="
