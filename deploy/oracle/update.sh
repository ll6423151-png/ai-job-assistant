#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="${CAREERPILOT_DOMAIN:?CAREERPILOT_DOMAIN is required}"
BRANCH="${CAREERPILOT_BRANCH:-main}"
APP_DIR="/opt/careerpilot"

cd "$APP_DIR"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
test -f deploy/oracle/.env.oracle || { echo "Missing deploy/oracle/.env.oracle" >&2; exit 1; }
sudo docker compose --env-file deploy/oracle/.env.oracle -f deploy/oracle/docker-compose.yml up -d --build --remove-orphans
sudo docker image prune -f
curl -fsS "https://$DOMAIN/api/health"
echo "CareerPilot updated"
