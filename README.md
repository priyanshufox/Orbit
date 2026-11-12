# Orbit

See who's in your orbit. Friends join a room by QR, play a 5-minute round of questions and shared content, and see a live graph of how close everyone is.

- Design: [Orbit — System Design](https://claude.ai/artifact/TroPBVeD5GJMbLD7iSp7na)
- Plan: [ROADMAP.md](ROADMAP.md)
- Architecture: [ADR 0001 — Modular monolith](docs/adr/0001-modular-monolith.md)

## Layout

| Path | What |
|---|---|
| `web/` | Next.js PWA: host big screen (`app/host/[code]`), phone play (`app/play/[code]`), account pages |
| `api/` | FastAPI codebase, run as two processes: `api` (REST + WebSocket) and `worker` (arq jobs) |
| `infra/` | Docker Compose for Postgres, Redis, Neo4j |
| `docs/adr/` | Architecture decision records |

## Getting started

```bash
cp .env.example .env
```

Local infra (Postgres 18, Redis 8, Neo4j 2026.10 with Graph Data Science), needs Docker running:

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d --wait
```

| Service | Address | Dev login |
|---|---|---|
| Postgres | `localhost:5432` | `orbit` / `orbit`, database `orbit` |
| Redis | `localhost:6379` | none |
| Neo4j bolt | `localhost:7687` | `neo4j` / `NEO4J_PASSWORD` from `.env` |
| Neo4j browser | http://localhost:7474 | same |

Stop with `docker compose -f infra/docker-compose.yml down`; add `-v` to also wipe the data volumes. The first Neo4j start downloads the GDS plugin, so it takes about a minute.

Web:

```bash
cd web && npm install && npm run dev
```

API (needs [uv](https://docs.astral.sh/uv/) and the local infra running). First time, create the tables and load dev data:

```bash
cd api && uv sync && uv run alembic upgrade head && uv run python -m orbit.seed
```

Then two processes, two terminals:

```bash
cd api && uv sync && uv run uvicorn orbit.main:app --reload
```

```bash
cd api && uv run arq orbit.worker.WorkerSettings
```

New migration after changing a `models.py`: `uv run alembic revision --autogenerate -m "what changed"`, then review the file.

The API serves `GET /health`, `GET /health/ready` (Postgres + Redis) and interactive docs at http://localhost:8000/docs (hidden when `APP_ENV=production`). Logs are readable console lines in development and JSON lines in production.

## Checks (same as CI)

| | Lint | Format | Types | Tests |
|---|---|---|---|---|
| `api/` | `uv run ruff check .` | `uv run ruff format --check .` | | `uv run alembic check`, `uv run pytest` (needs local infra; includes the ADR module-boundary rules) |
| `web/` | `npm run lint` | `npm run format:check` | `npm run typecheck` | `npm run build` |
