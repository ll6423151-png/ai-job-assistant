#!/usr/bin/env sh
set -eu

echo "Applying database migrations..."
alembic upgrade head

if [ "${BOOTSTRAP_ADMIN_ENABLED:-true}" = "true" ] && [ -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then
  INIT_USER_PASSWORD="$BOOTSTRAP_ADMIN_PASSWORD" python scripts/init_user.py \
    --username "${BOOTSTRAP_ADMIN_USERNAME:-admin}" \
    --email "${BOOTSTRAP_ADMIN_EMAIL:-admin@local.invalid}" \
    --admin --legacy-owner
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" ${UVICORN_RELOAD:+--reload}
