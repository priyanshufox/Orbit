# Deploying Orbit (task 10.5)

Four pieces, as in the design: **Vercel** for the web app, **one container host** for the API, worker and Redis, **Neo4j Aura**, and **managed Postgres**. Nothing here has been deployed yet. Each step needs your own account, so do them in this order.

## 1. Postgres (managed)

Any Postgres 16+ works; the schema uses `gen_random_uuid()`. Good options in India: Neon, Supabase or Render Postgres (Mumbai or Singapore region).

- Create a database `orbit`. Note two URLs:
  - `DATABASE_URL` for the API: `postgresql+asyncpg://USER:PASS@HOST:5432/orbit?ssl=require` (asyncpg takes `ssl=`, not `sslmode=`)
  - `AUTH_DATABASE_URL` for the web app: `postgresql://USER:PASS@HOST:5432/orbit?sslmode=require`
- Encryption at rest is on by default on these hosts (design: breach basics).

## 2. Neo4j

Neo4j Aura Free works. It has no Graph Data Science library, so clustering falls back to Python Louvain automatically (task 6.4); `GRAPH_USE_GDS` can stay `true`. Note `NEO4J_URI` (`neo4j+s://...`), `NEO4J_USER` and `NEO4J_PASSWORD`.

## 3. API, worker and Redis (one container host)

Render, Railway or Fly.io all fit. Build from `api/Dockerfile` (CI builds it on every push).

| Service | Command | Notes |
|---|---|---|
| API (web service) | image default (`uvicorn ...`) | Port 8000, health check `/health`, readiness `/health/ready`. WebSockets must be allowed. Scale out freely: events fan out through Redis. |
| Worker (background) | `arq orbit.worker.WorkerSettings` | Runs the round timer, scoring, hourly expiry and the daily content curator. One instance. |
| Release step | `alembic upgrade head` then `python -m orbit.seed --banks` | Before each deploy. Loads the question and facts banks (never dev users). |
| Redis | the host's managed Redis | Note `REDIS_URL`. |

Environment for both API and worker (put secrets in the host's secret store):

```
APP_ENV=production
DATABASE_URL=...            REDIS_URL=...
NEO4J_URI=...               NEO4J_USER=...   NEO4J_PASSWORD=...
WEB_URL=https://<your web domain>             # CORS allows only this origin
AUTH_JWKS_URL=https://<your web domain>/api/auth/jwks
AUTH_ISSUER=https://<your web domain>
SENTRY_DSN=...              # optional, error tracking
METRICS_TOKEN=...           # optional, enables GET /health/metrics
ANTHROPIC_API_KEY=...       # content curator: tagging, moderation, meme captions
IMGFLIP_USERNAME=...  IMGFLIP_PASSWORD=...   NEWSDATA_API_KEY=...   # optional sources
```

## 4. Web (Vercel)

- Import the repo with **root directory `web`**. The framework is detected as Next.js.
- Environment variables:

```
NEXT_PUBLIC_API_URL=https://<your api domain>
BETTER_AUTH_URL=https://<your web domain>
BETTER_AUTH_SECRET=<openssl rand -base64 32>
AUTH_DATABASE_URL=postgresql://...?sslmode=require
GOOGLE_CLIENT_ID=...  GOOGLE_CLIENT_SECRET=...  # redirect URI: https://<web>/api/auth/callback/google
RESEND_API_KEY=...    EMAIL_FROM="Orbit <login@your-domain>"   # required in production
```

- Pick the Vercel region closest to the API and database (e.g. `bom1`, Mumbai).
- There is no dev login; in production, email sign-in fails without `RESEND_API_KEY`.

## 5. After the first deploy

1. Open `https://<web>/signin`, sign in by email, and finish sign-up (name, birth date, hobbies) and consent.
2. Host a room on a laptop and join from two phones. Play a round.
3. Check: the reveal appears; `/health/ready` reports ok; Sentry receives a test error if configured.
4. Next day: check the worker logs for `content.curated` (needs `ANTHROPIC_API_KEY`) and `room.expired`.
