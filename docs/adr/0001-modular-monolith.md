# ADR 0001 — Modular monolith in a monorepo

- **Status:** Accepted
- **Date:** 2026-11-12

## Decision

Orbit is one repository holding one Next.js app (`web/`) and one FastAPI codebase (`api/`) split into strict feature modules. The API codebase runs as two processes from the same Docker image: `api` (REST + WebSocket) and `worker` (arq jobs).

## Context

- Small team; Next.js PWA + FastAPI + Postgres + Neo4j + Redis are already locked (see the [system design](https://claude.ai/artifact/TroPBVeD5GJMbLD7iSp7na)).
- The domain already splits into clear areas: accounts, rooms, game, scoring, graph, content, privacy.
- Background work (round timer, scoring, hourly expiry, daily content curator) needs a job runner; `arq` reuses the existing Redis.

## Layout

```
orbit/
├── web/                         Next.js PWA
│   └── src/
│       ├── app/
│       │   ├── (account)/       sign-in, age gate, consent, roots, history
│       │   ├── host/[code]/     big screen: lobby → progress → reveal
│       │   └── play/[code]/     phone: join → deck → my results
│       ├── features/            rooms, game, reveal, account (components + hooks)
│       └── lib/api/             generated types, fetch client, WebSocket client
├── api/
│   ├── src/orbit/
│   │   ├── core/                config, db, redis, auth, event bus
│   │   ├── modules/
│   │   │   ├── accounts/        users, age gate, consent, roots
│   │   │   ├── rooms/           create/join/leave, state machine, WebSocket
│   │   │   ├── game/            questions, deck, answers, reactions, social
│   │   │   ├── scoring/         domain/ (pure maths) + job
│   │   │   ├── graph/           Neo4j driver, projection, clustering, /graph view
│   │   │   ├── content/         sources, tagging, moderation, curator
│   │   │   └── privacy/         snapshots, expiry, account deletion
│   │   ├── pipeline.py          cross-module flows: reveal, expire, delete account
│   │   ├── main.py              API process entry
│   │   └── worker.py            arq worker entry
│   └── tests/
├── infra/                       docker-compose, Dockerfiles
└── docs/adr/                    architecture decisions
```

Each module uses the same files (omit any it doesn't need): `router.py` (HTTP), `service.py` (logic), `repo.py` (database access), `models.py` (SQLAlchemy tables), `schemas.py` (Pydantic request/response models).

## Rules

1. **Routers are thin.** They parse input and call a service; no logic.
2. **Modules talk through services only.** A module never imports another module's `models.py` or `repo.py`. Enforced in CI by `api/tests/test_architecture.py`.
3. **Scoring maths is pure.** `scoring/domain/` has no database, network or framework imports.
4. **Only `graph` talks to Neo4j.** It owns the driver too. Postgres is the source of truth; Neo4j can always be rebuilt from it. The Python Louvain fallback lives here too.
5. **Types are generated, never copied.** Frontend types come from FastAPI's OpenAPI spec via `openapi-typescript`. WebSocket events are one Pydantic discriminated union, exported the same way.
6. **Flows that span modules live in `orbit/pipeline.py`.** It calls each module's service in turn (score → project → reveal; snapshot → delete → audit). Modules never import each other's internals to do this.
7. **One event bus.** All realtime events go through `core/events.py` → Redis channel `room:{code}`. Modules never touch sockets directly.

## Alternatives rejected

- **Microservices:** separate deploys and network contracts with no team or scale to justify them. A module (most likely `content`) can be extracted later if needed.
- **Next.js-only full stack:** simpler, but reverses the locked FastAPI WebSocket decision.
- **Full hexagonal / clean architecture:** too much ceremony; rules 3 and 4 give its benefits where they matter.

## Consequences

- One CI pipeline, one API image, one place to change contracts.
- Module boundaries depend on discipline plus an architecture test (`grimp` import graph) that checks rules 2–4; a broken rule fails CI.
- Scaling is per process (`api` vs `worker`), not per module, which is fine for the MVP.
