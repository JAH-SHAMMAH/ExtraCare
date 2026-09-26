#!/bin/sh
# Container entrypoint for the Fairview School Portal API.
#
# ############################################################################
# ## RENDER DOES NOT RUN THIS FILE. Fairview's production backend does NOT   ##
# ## get its migrations from here.                                           ##
# ############################################################################
#
# This script is reached only via the Dockerfile's ENTRYPOINT — i.e. under
# docker-compose (local dev, or a self-hosted deployment). Render's backend
# service is not built from backend/Dockerfile, so ENTRYPOINT is never invoked
# and the `alembic upgrade head` below never executes in production.
#
# Confirmed the hard way on 2026-09-26: a Render deploy put new code live (new
# routes answering, /health reporting environment=production) while
# alembic_version did not move. Two separate deploys were attempted, and a day
# lost, chasing "why didn't the migration run" — because this file exists and
# looks like the answer. Hence the banner.
#
# ON RENDER, migrations are applied EITHER by hand:
#     cd backend
#     DATABASE_URL="postgresql+asyncpg://<prod-dsn>" python -m alembic upgrade head
# OR by a Render Pre-Deploy Command of `alembic upgrade head`
# (dashboard -> the backend service -> Settings -> Build & Deploy).
# See DEPLOYMENT.md §0 and §7.
#
# Verify a migration by reading alembic_version in the database, never by
# probing the API — the old instance keeps answering while nothing has shipped.
#
# Under Docker, the behaviour below is the intended one: in production/staging
# the schema is managed by Alembic (AUTO_CREATE_SCHEMA is false there), so run
# migrations to head BEFORE the app accepts traffic; in development skip that and
# rely on AUTO_CREATE_SCHEMA. Either way exec the container's CMD (uvicorn), so
# signals/PID 1 behave correctly.
set -e

if [ "$ENVIRONMENT" = "production" ] || [ "$ENVIRONMENT" = "staging" ]; then
  echo "[entrypoint] ENVIRONMENT=$ENVIRONMENT — running 'alembic upgrade head'..."
  alembic upgrade head
  echo "[entrypoint] migrations complete."
else
  echo "[entrypoint] ENVIRONMENT=${ENVIRONMENT:-development} — skipping migrations (AUTO_CREATE_SCHEMA handles dev)."
fi

exec "$@"
