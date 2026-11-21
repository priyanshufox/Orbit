# Orbit

See who's in your orbit. Friends join a room by QR, play a 5-minute round of questions and shared content, and see a live graph of how close everyone is.

- Design: [Orbit — System Design](https://claude.ai/artifact/TroPBVeD5GJMbLD7iSp7na)
- Plan: [ROADMAP.md](ROADMAP.md)
- Architecture: [ADR 0001 — Modular monolith](docs/adr/0001-modular-monolith.md), [ADR 0002 — Better Auth sign-in](docs/adr/0002-better-auth.md)
- Run it for real: [Deploy](docs/deploy.md) · [Playtests and tuning](docs/playtest.md)

## How a round works

1. The host taps **Host a room** and opens the host screen on a TV. Friends scan the QR code.
2. Everyone signs in (Google or an email link), creates a profile (name, date of birth for the 18+ check, up to 6 hobbies) and agrees to the data notice, once per account.
3. The host starts a 5-minute round. Each phone gets the same deck: 10 questions and 15 cards (facts, memes, headlines).
4. When everyone finishes, or time runs out, the worker scores every pair, writes the graph to Neo4j and reveals it on the TV and on every phone.
5. 48 hours later the room is deleted from Postgres and Neo4j; each player keeps a snapshot of their own part of the graph.

## Layout

| Path | What |
|---|---|
| `web/` | Next.js PWA: host big screen (`app/host/[code]`), phone play (`app/play/[code]`), account pages |
| `api/` | FastAPI codebase, run as two processes: `api` (REST + WebSocket) and `worker` (arq jobs) |
| `api/loadtest/` | Load test: N rooms x M players through the real stack |
| `infra/` | Docker Compose for Postgres, Redis, Neo4j |
| `docs/` | Architecture decisions, deploy guide, playtest guide |

## Getting started

```bash
cp .env.example .env
```

Then set `BETTER_AUTH_SECRET` in `.env` (`openssl rand -base64 32`). Both apps read this one root file.

Local infra (Postgres 18, Redis 8, Neo4j 2026.10 with Graph Data Science), needs Docker running:

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d --wait
```

| Service | Address | Local credentials |
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

Sign-in at http://localhost:3000/signin:

- **Email link:** without `RESEND_API_KEY`, the link is printed in the web server's console (local runs only; production needs Resend). There is no dev login: test with real sign-in.
- **Google:** create an OAuth client in Google Cloud Console with redirect URI `http://localhost:3000/api/auth/callback/google`, then set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. The button appears once both are set.

After changing an API route, model or WebSocket event, regenerate the web app's types (CI checks they are current):

```bash
./scripts/gen-api-types.sh
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

The worker runs the round timer, scoring and reveal, the hourly room expiry, and the daily content curator; rounds don't finish without it. Alternatively set `RUN_WORKER_IN_PROCESS=true` and the API runs the worker itself (used on Render's free plan).

Content: `uv run python -m orbit.seed --banks` loads the question bank (`api/src/orbit/modules/game/data/questions.json`) and facts bank (`api/src/orbit/modules/content/data/facts.json`). Live memes and headlines need `ANTHROPIC_API_KEY` plus the Imgflip or NewsData keys. To draft more facts for review: `uv run python -m orbit.modules.content.draft_facts`.

The API serves `GET /health`, `GET /health/ready` (Postgres + Redis) and interactive docs at http://localhost:8000/docs (hidden when `APP_ENV=production`). Logs are readable console lines in development and JSON lines in production.

## Checks (same as CI)

| | Lint | Format | Types | Tests |
|---|---|---|---|---|
| `api/` | `uv run ruff check .` | `uv run ruff format --check .` | | `uv run alembic check`, `uv run pytest` (needs local infra; includes the ADR module-boundary rules) |
| `web/` | `npm run lint` | `npm run format:check` | `npm run typecheck` | `npm run build` |
