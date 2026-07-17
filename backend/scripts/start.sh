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

if [ -n "${BOOTSTRAP_TEST_PASSWORD:-}" ]; then
  INIT_USER_PASSWORD="$BOOTSTRAP_TEST_PASSWORD" python scripts/init_user.py \
    --username "${BOOTSTRAP_TEST_USERNAME:-tester}" \
    --email "${BOOTSTRAP_TEST_EMAIL:-tester@local.invalid}" \
    --update-password
fi

if [ -n "${BOOTSTRAP_TEST2_PASSWORD:-}" ]; then
  INIT_USER_PASSWORD="$BOOTSTRAP_TEST2_PASSWORD" python scripts/init_user.py \
    --username "${BOOTSTRAP_TEST2_USERNAME:-tester2}" \
    --email "${BOOTSTRAP_TEST2_EMAIL:-tester2@local.invalid}" \
    --update-password
fi

if [ -n "${BOOTSTRAP_TEST3_PASSWORD:-}" ]; then
  INIT_USER_PASSWORD="$BOOTSTRAP_TEST3_PASSWORD" python scripts/init_user.py \
    --username "${BOOTSTRAP_TEST3_USERNAME:-tester3}" \
    --email "${BOOTSTRAP_TEST3_EMAIL:-tester3@local.invalid}" \
    --update-password
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" ${UVICORN_RELOAD:+--reload}
