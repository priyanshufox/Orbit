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

Web:

```bash
cd web && npm install && npm run dev
```

API and local infra setup arrive with tasks 0.3, 0.4 and 1.1.
