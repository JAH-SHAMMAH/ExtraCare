#!/usr/bin/env bash
# One-shot: migrate + smoke-test a deployed ExtraCare backend.
#
# Usage (from backend/):
#   BASE_URL=https://staging-api.extracare.app \
#   DATABASE_URL=... \
#   EMAIL=admin@... PASSWORD=... \
#   TEACHER_EMAIL=... TEACHER_PASSWORD=... \
#   STUDENT_EMAIL=... STUDENT_PASSWORD=... \
#   scripts/deploy_smoke.sh
#
# Fails fast on any missing env, migration failure, or smoke failure.
set -euo pipefail

require() {
    local name="$1"
    if [[ -z "${!name:-}" ]]; then
        echo "ERROR: $name is required" >&2
        exit 2
    fi
}

require BASE_URL
require DATABASE_URL
require EMAIL
require PASSWORD

# Teacher/student are optional but strongly recommended — warn if missing.
for v in TEACHER_EMAIL TEACHER_PASSWORD STUDENT_EMAIL STUDENT_PASSWORD; do
    if [[ -z "${!v:-}" ]]; then
        echo "WARN: $v unset — that role's checks will be skipped" >&2
    fi
done

cd "$(dirname "$0")/.."

PY="${PYTHON:-python}"

echo "== 1/3  alembic upgrade head =================================="
$PY -m alembic upgrade head

echo
echo "== 2/3  sanity: /health ======================================="
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
if [[ "$code" != "200" ]]; then
    echo "ERROR: /health returned $code" >&2
    exit 1
fi
echo "  health ok"

echo
echo "== 3/3  staging_smoke.py ======================================"
$PY scripts/staging_smoke.py

echo
echo "ALL GREEN — safe to promote this build."
