#!/usr/bin/env bash
# Regenerate the web app's API types from the FastAPI schema (roadmap 0.5).
# Run after changing any route, request/response model or WebSocket event:
#   ./scripts/gen-api-types.sh
# CI runs this and fails if the committed files differ.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
out="$root/web/src/lib/api"

(cd "$root/api" && uv run --quiet python -m orbit.export_openapi) > "$out/openapi.json"
(cd "$root/web" && npx --no-install openapi-typescript src/lib/api/openapi.json -o src/lib/api/types.ts)
