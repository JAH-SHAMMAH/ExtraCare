#!/bin/sh
# Container entrypoint for the Fairview School Portal API.
#
# In production/staging the schema is managed by Alembic (AUTO_CREATE_SCHEMA is
# false there), so run migrations to head BEFORE the app accepts traffic. In
# development we skip this and rely on AUTO_CREATE_SCHEMA. Either way we then
# exec the container's CMD (uvicorn), so signals/PID 1 behave correctly.
set -e

if [ "$ENVIRONMENT" = "production" ] || [ "$ENVIRONMENT" = "staging" ]; then
  echo "[entrypoint] ENVIRONMENT=$ENVIRONMENT — running 'alembic upgrade head'..."
  alembic upgrade head
  echo "[entrypoint] migrations complete."
else
  echo "[entrypoint] ENVIRONMENT=${ENVIRONMENT:-development} — skipping migrations (AUTO_CREATE_SCHEMA handles dev)."
fi

exec "$@"
