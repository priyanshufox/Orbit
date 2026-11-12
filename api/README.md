# Orbit API

One codebase, two processes (see [ADR 0001](../docs/adr/0001-modular-monolith.md)):

- `orbit.main`: FastAPI app (REST + WebSocket)
- `orbit.worker`: arq worker (round timer, scoring, expiry, content curator)

Modules live in `src/orbit/modules/`. Each one uses `router.py`, `service.py`, `repo.py`, `models.py` and `schemas.py` as needed, and talks to other modules only through their services.
