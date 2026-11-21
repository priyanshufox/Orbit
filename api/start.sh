#!/bin/sh
# Start the API for hosts without a pre-deploy step (e.g. Render's free plan): migrate, load the
# question and facts banks, then serve. Idempotent, so it is safe on every start.
set -e
alembic upgrade head
python -m orbit.seed --banks
exec uvicorn orbit.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips '*'
