#!/usr/bin/env bash
# Staging gate: build the image exactly as it ships, bring up the compose stack, run the suite
# in staging/ against it, then tear everything down (containers, network, volume, built images).
# Usage: scripts/staging.sh   (needs Docker running and the .venv from the README; CI sets PYTEST=pytest)
set -uo pipefail
cd "$(dirname "$0")/.."
export COMPOSE_PROJECT_NAME=mlplatform-staging

docker compose up --build -d || { docker compose down -v --rmi local; exit 1; }
${PYTEST:-.venv/bin/pytest} staging -v -p no:cacheprovider
status=$?
echo "staging commit: $(git rev-parse --short HEAD)"
docker compose down -v --rmi local
left=$(docker ps -a --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME" -q | wc -l | tr -d ' ')
echo "containers left behind: $left"
exit $status
