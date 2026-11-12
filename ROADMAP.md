# Orbit — Build Roadmap

Source of truth for the design: [Orbit — System Design](https://claude.ai/artifact/TroPBVeD5GJMbLD7iSp7na).
Architecture: modular monolith in a monorepo — see [ADR 0001](docs/adr/0001-modular-monolith.md).

Each task is sized to about half a day to a day and ends in something you can run or test.
Tasks are numbered `phase.step`. Within a phase, do them in order unless marked *(parallel)*.

**Milestones**

| Milestone | Phases | What works at the end |
|---|---|---|
| M1 Walking skeleton | 0–3 | Host creates a room, phones join by QR, host screen shows avatars live |
| M2 Playable round | 4–5 | 5-minute round with questions + facts cards, scores computed |
| M3 MVP | 6–8 | Graph reveal on host and phones, 48 h deletion, snapshots saved |
| M4 Launch-ready | 9–10 | Live memes + news, PWA, deployed, tuned on real rooms |

---

## Phase 0 — Decisions and repo setup

- [x] **0.0 Architecture.** Modular monolith in a monorepo, `api` + `worker` processes from one codebase ([ADR 0001](docs/adr/0001-modular-monolith.md)). Job runner: `arq` on the existing Redis.
- [x] **0.1 Close blocking decisions.** Reveal: everything public (host screen and phones show every pair's score). Graph library: Cytoscape.js. Snapshot: JSON now, PNG export later. Room cap: 20. Recorded in the design doc.
- [x] **0.1b Roots on a public reveal.** Generic "Shared roots" edge reason only; school and city names never leave the server.
- [x] **0.2 Monorepo layout.** `git init`; scaffold the tree from ADR 0001: `web/` (Next.js, `app/(account)`, `app/host/[code]`, `app/play/[code]`, `features/`, `lib/api/`), `api/src/orbit/` (`core/`, the 7 empty modules, `main.py`, `worker.py`), `infra/`, `docs/adr/`; root README and `.env.example`.
- [x] **0.3 Local infra.** `infra/docker-compose.yml` with Postgres, Redis and Neo4j (with the GDS plugin).
  *Done when:* `docker compose up` starts all three and each one answers a ping.
- [x] **0.4 Tooling.** Python 3.13 via `uv`, `ruff`, `pytest`; ADR rules 2–4 checked by `api/tests/test_architecture.py` (grimp import graph; import-linter couldn't express rule 2 or handle not-yet-installed packages). Web: ESLint + Prettier, TypeScript strict plus `noUncheckedIndexedAccess`. GitHub Actions runs lint, format, typecheck, tests and build on push. Known: 7 moderate `npm audit` findings from a `minimatch` pinned inside `eslint-config-next` (lint-time only).
- [ ] **0.5 Type generation.** Script that dumps FastAPI's OpenAPI spec and runs `openapi-typescript` into `web/src/lib/api/types.ts`; CI fails if the generated file is stale.

## Phase 1 — Backend skeleton and database

- [x] **1.1 FastAPI skeleton.** App factory in `main.py`, `core/config.py` (`pydantic-settings`), `GET /health`, structured logging; `worker.py` with an empty arq `WorkerSettings` that starts cleanly.
- [x] **1.1b Event bus.** `core/events.py`: one `publish(redis, room_code, event)` function and the WebSocket event union (Pydantic discriminated union); `core/redis.py` client.
- [x] **1.2 Database layer.** SQLAlchemy 2 (async) + Alembic, session dependency, test database fixture; `GET /health/ready` checks Postgres and Redis.
- [x] **1.3 Persistent tables migration.** `users` (add `consented_at`, `avatar_url`), `user_roots`, `graph_snapshots`, `content`, `questions`.
- [x] **1.4 Ephemeral tables migration.** `rooms`, `room_members`, `answers`, `reactions`, `social`, `scores`. Room-scoped rows reference `room_members (room_code, user_id)` with `ON DELETE CASCADE`, so deleting a room or removing one member (task 3.8) cascades.
  *Done when:* deleting one `rooms` row removes every row for that room (test).
- [x] **1.5 Dev seed script.** 5 fake users, 15 questions, 40 fake fact cards.

## Phase 2 — Auth and accounts

- [ ] **2.1 Next.js app shell.** App Router, Tailwind, basic layout, API client wrapper.
- [ ] **2.2 Dev login stub.** A dev-only "sign in as user N" so later phases are not blocked on OAuth setup.
- [ ] **2.3 Auth.js providers.** Google + email magic link (e.g. Resend for email).
- [ ] **2.4 API auth bridge.** Next.js mints a short-lived signed token from the session; FastAPI verifies it in a `current_user` dependency. Same token authenticates the WebSocket.
  *Done when:* an unauthenticated API call returns 401 and an authenticated one returns the user.
- [ ] **2.5 User upsert on first sign-in.**
- [ ] **2.6 Age gate.** Birth year once at signup; under 18 → no account row, nothing stored (test this).
- [ ] **2.7 Consent notice screen.** Standalone notice before the first room; must say closeness scores are visible to everyone in the room. Stores `consented_at`.
- [ ] **2.8 Roots.** `GET/PUT /me/roots` + form (birth city, school + city, up to 3 childhood cities, all optional). City/school normalisation with an alias table ("Bombay → Mumbai").

## Phase 3 — Rooms, lobby and realtime  → **M1**

- [ ] **3.1 Create room.** `POST /rooms`: 6-character code (no look-alike characters), `expires_at = now + 48 h`, state `CREATED`.
- [ ] **3.2 Room state machine.** One module that owns `CREATED → LOBBY → PLAYING → SCORING → REVEALED → EXPIRED` and rejects illegal transitions (unit tests).
- [ ] **3.3 Join room.** `POST /rooms/{code}/join`, `require_member` dependency, 20-member cap, join rate limit.
- [ ] **3.4 WebSocket endpoint.** `/ws/rooms/{code}` with auth + membership check and a connection manager.
- [ ] **3.5 Redis fan-out.** Publish to `room:{code}`; each worker subscribes and delivers to its sockets.
  *Done when:* an event published on worker A reaches a socket held by worker B (run 2 uvicorn workers).
- [ ] **3.6 Host screen lobby.** Big QR (client-side `qrcode`) with the join URL; avatars appear on `member_joined`.
- [ ] **3.7 Phone join flow.** Scan → sign in → age gate → consent → optional roots → "waiting for host".
- [ ] **3.8 Leave and kick.** `POST /rooms/{code}/leave` ("Leave and delete my data") and host kick. Both are missing from the design's API table; add them there.

## Phase 4 — The game round

- [ ] **4.1 Question bank.** Write about 30 questions (single choice, multi-select, slider) on behaviour, hobbies and interests; load into `questions`. *(parallel with 4.2)*
- [ ] **4.2 Facts bank v1.** 100 facts as JSON with 1–3 tags from the fixed tag list; loader script. Grow to 300+ later. *(parallel with 4.1)*
- [ ] **4.3 Deck builder.** Seeded draw of 10 questions + 15 content cards, max 3 cards per tag; `GET /rooms/{code}/deck` returns the same deck to every member.
- [ ] **4.4 Start round.** `POST /rooms/{code}/start`: state → `PLAYING`, `ends_at`, `game_started` event, schedule the round-end job in `arq`.
- [ ] **4.5 Phone card UI.** Card stack with countdown; question cards for all 3 types; content cards with like / laugh / skip / send.
- [ ] **4.6 Save answers and reactions.** Idempotent `PUT` endpoints; client retry queue so a flaky connection loses nothing.
- [ ] **4.7 Likes and follows.** `POST /rooms/{code}/social` + a player list on the phone.
- [ ] **4.8 Finish and progress.** `POST /rooms/{code}/finish`; `progress` event; progress bar on the host screen.
- [ ] **4.9 Round end.** Timer expiry or all players finished (whichever first, only once) → `SCORING`, `scoring` event, enqueue the scoring job.

## Phase 5 — Closeness scoring  → **M2**

Pure functions first, all unit-tested, no database.

- [ ] **5.1 Answer similarity `S_ans`.** Vectorise answers (one-hot, multi-hot, 0–1 slider), cosine over shared questions; skip below 5 shared.
- [ ] **5.2 Reaction similarity `S_react`.** like/laugh = +1, send = +1.5, skip = −1; cosine rescaled to 0–1; skip below 6 shared items.
- [ ] **5.3 Shared roots `S_roots`.** `min(1, 0.6·school + 0.25·birth city + 0.15·Jaccard(childhood))`; skip if either side is blank.
- [ ] **5.4 Social `S_social`.** 0.4 per follow direction + 0.05 per profile like, capped at 1.
- [ ] **5.5 Combine.** Weights 35/35/15/15, redistribute weight of skipped signals; tests for symmetry and the 0–1 range.
- [ ] **5.6 Explanations.** Top contributing items per pair ("You both laughed at 7 of 9 memes", "Shared roots"). Roots reasons are always the generic label; a test asserts no school or city name appears in any explanation.
- [ ] **5.7 Scoring job.** Load room data → compute all pairs → write `scores` → hand off to Phase 6.

## Phase 6 — Neo4j graph

- [ ] **6.1 Neo4j client.** Driver setup, constraints and indexes on `(room, id)`.
- [ ] **6.2 Projection writer.** `Person`, `FOLLOWS`, `REACTED`, `Place`, `CLOSE_TO`, all tagged with `room`.
- [ ] **6.3 Edge selection.** Draw `CLOSE_TO` when total ≥ 0.4, plus each player's top 3 so nobody is isolated.
- [ ] **6.4 Clusters.** Louvain → `Person.community`. **Risk:** Neo4j Aura Free has no GDS. Build a fallback that runs Louvain in Python (`networkx`) and writes the result back.
- [ ] **6.5 Reveal.** State → `REVEALED`, `reveal` event.
- [ ] **6.6 `GET /rooms/{code}/graph`.** One view for members and the host screen: every edge carries its score and explanations.
- [ ] **6.7 Rebuild command.** Re-project a room from Postgres into Neo4j (proves Neo4j is disposable).

## Phase 7 — Reveal UI  → **M3 (with Phase 8)**

- [ ] **7.1 Cytoscape.js spike.** 20 nodes, all 190 edges on a TV-sized screen with an animated force layout (`fcose` or `cola` extension) and readable score labels. Same component on a phone screen.
- [ ] **7.2 Host reveal.** Animated graph, community colours, names, scores on edges (edge thickness by score).
- [ ] **7.3 Phone reveal.** Same full graph, plus my closeness list (sorted); tap any edge → its score and explanations.
- [ ] **7.4 Live edges after reveal.** `social_added` animates new follow edges (no re-score in MVP).

## Phase 8 — Retention and privacy

- [ ] **8.1 Snapshot writer.** Each player's ego graph + scores as JSON into `graph_snapshots`.
- [ ] **8.2 Expiry job (hourly).** Snapshot → delete room in Postgres → delete Neo4j subgraph by `room` → audit log entry.
- [ ] **8.3 Closing warning.** `room_closing` event 1 h before expiry.
- [ ] **8.4 History page.** `GET /me/snapshots` + re-render saved graphs.
- [ ] **8.5 Delete account.** `DELETE /me` removes account, roots and snapshots within 24 h.
- [ ] **8.6 Deletion tests.** After expiry, no row or node for that room exists in either store.

## Phase 9 — Live content pipeline

- [ ] **9.1 Curator job framework.** Daily `arq` cron; each source is a plugin that returns content items.
- [ ] **9.2 Imgflip memes.** `/get_memes` → LLM captions → `/caption_image`; 20 per day.
- [ ] **9.3 NewsData.io headlines.** About 50 per day, India + world.
- [ ] **9.4 LLM tagging.** Proposes 1–3 tags; the job rejects any tag outside the fixed list.
- [ ] **9.5 Moderation pass.** Drop NSFW, hateful or graphic items before `active = true`.
- [ ] **9.6 Facts bank to 300+.** Generate, review by hand, load.

## Phase 10 — Hardening and launch  → **M4**

- [ ] **10.1 PWA.** Manifest, icons, installable, offline shell.
- [ ] **10.2 Abuse controls.** Rate limits review, room cap, kick, max rooms per host per day.
- [ ] **10.3 Observability.** Error tracking (e.g. Sentry) on web and API, basic metrics per room.
- [ ] **10.4 Load test.** 20 concurrent full rooms (20 players each) through WebSockets.
- [ ] **10.5 Deploy.** Vercel (web) + one container host (API, workers, Redis) + Neo4j + managed Postgres; secrets in the host's vault.
- [ ] **10.6 Playtests.** 3–5 real rooms; tune the 0.4 threshold and reaction values.
- [ ] **10.7 Legal review.** Consent notice and flow reviewed by a lawyer before public launch.

---

## Gaps found in the design while planning

1. **Neo4j GDS on the free tier.** Aura Free does not include Graph Data Science, so Louvain needs the Python fallback in 6.4 (or a paid tier / self-hosted Neo4j).
2. **Job runner not named.** Round timers, scoring, hourly expiry and the daily curator all need one. Decided: `arq` on Redis (ADR 0001).
3. **Auth.js → FastAPI.** The design says "session cookie from Auth.js" but not how FastAPI verifies it; 2.4 proposes a short-lived signed token.
4. **Missing endpoints.** Leave-and-delete and host kick (3.8).
5. **Missing columns.** `users.consented_at` and an avatar field for `member_joined` (1.3).
