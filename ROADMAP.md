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
- [x] **0.5 Type generation.** `scripts/gen-api-types.sh` exports FastAPI's OpenAPI (plus the WebSocket `RoomEvent` union) and runs `openapi-typescript` into `web/src/lib/api/types.ts`; CI job `api-types` fails if it is stale.

## Phase 1 — Backend skeleton and database

- [x] **1.1 FastAPI skeleton.** App factory in `main.py`, `core/config.py` (`pydantic-settings`), `GET /health`, structured logging; `worker.py` with an empty arq `WorkerSettings` that starts cleanly.
- [x] **1.1b Event bus.** `core/events.py`: one `publish(redis, room_code, event)` function and the WebSocket event union (Pydantic discriminated union); `core/redis.py` client.
- [x] **1.2 Database layer.** SQLAlchemy 2 (async) + Alembic, session dependency, test database fixture; `GET /health/ready` checks Postgres and Redis.
- [x] **1.3 Persistent tables migration.** `users` (add `consented_at`, `avatar_url`), `user_roots`, `graph_snapshots`, `content`, `questions`.
- [x] **1.4 Ephemeral tables migration.** `rooms`, `room_members`, `answers`, `reactions`, `social`, `scores`. Room-scoped rows reference `room_members (room_code, user_id)` with `ON DELETE CASCADE`, so deleting a room or removing one member (task 3.8) cascades.
  *Done when:* deleting one `rooms` row removes every row for that room (test).
- [x] **1.5 Dev seed script.** 5 fake users, 15 questions, 40 fake fact cards.

## Phase 2 — Auth and accounts

- [x] **2.1 Next.js app shell.** App Router, Tailwind, phone-first UI pieces (`components/ui.tsx`), typed API clients (`lib/api/server.ts` for server components and actions, `lib/api/browser.ts` for client components).
- [x] **2.2 Dev login stub.** `/api/dev-login?email=devN@orbit.test` (dev only, `.test` addresses only) runs the real magic-link flow and redirects; buttons on `/signin`.
- [x] **2.3 Sign-in providers.** Better Auth instead of Auth.js ([ADR 0002](docs/adr/0002-better-auth.md)): Google (enabled when `GOOGLE_CLIENT_ID/SECRET` are set) + email magic link (Resend; printed to the console in dev). Identity tables in Postgres schema `auth` (migration 3).
- [x] **2.4 API auth bridge.** Better Auth's `jwt` plugin issues 15-minute EdDSA tokens; FastAPI verifies them against `/api/auth/jwks` (`core/auth.py`, `IdentityDep`); `accounts.deps.CurrentUserDep` requires a profile. Same verifier will authenticate WebSockets.
  *Done when:* an unauthenticated API call returns 401 and an authenticated one returns the user.
- [x] **2.5 Profile creation.** The Orbit `users` row (same id as `auth.user`) is created at the age gate, not at sign-in, so nothing is stored for minors. `GET /me` reports `onboarded` / `consented`.
- [x] **2.6 Age gate.** `POST /me/age` takes the full date of birth for an exact 18+ check and stores only the year; under 18 deletes the sign-in identity (sessions, accounts cascade) and stores nothing (tested in API and in the browser).
- [x] **2.7 Consent notice screen.** `/consent` (draft text; lawyer review is 10.7) says scores are visible to everyone in the room; `POST /me/consent` stores `consented_at`.
- [x] **2.8 Roots.** `GET/PUT /me/roots` + `/roots` form, offered after consent and editable from home. Stored as typed; `accounts/roots.py` normalises for matching (case, accents, punctuation, 21 city aliases).

## Phase 3 — Rooms, lobby and realtime  → **M1**

- [x] **3.1 Create room.** `POST /rooms`: 6-character code (no look-alike characters), `expires_at = now + 48 h`, state `CREATED`. `POST /rooms`; codes from a 31-character alphabet without 0/O/1/I/L; host is not auto-joined (they can also play).
- [x] **3.2 Room state machine.** One module that owns `CREATED → LOBBY → PLAYING → SCORING → REVEALED → EXPIRED` and rejects illegal transitions (unit tests). `rooms/state.py`; every state change is a compare-and-set UPDATE, so timer and last finisher can't both move the room.
- [x] **3.3 Join room.** `POST /rooms/{code}/join`, `require_member` dependency, 20-member cap, join rate limit. 20-member cap (row-locked), 10 joins/min per user, late joiners allowed while PLAYING; `RoomDep`/`MemberRoomDep`/`HostRoomDep`.
- [x] **3.4 WebSocket endpoint.** `/ws/rooms/{code}` with auth + membership check and a connection manager. `/ws/rooms/{code}`: first message authenticates with the Better Auth JWT; close codes 4401/4403/4404/4410.
- [x] **3.5 Redis fan-out.** Publish to `room:{code}`; each worker subscribes and delivers to its sockets. `core/realtime.py`: one `room:*` pattern subscription per process. Tested with two managers on separate connections, and in the load test with 2 uvicorn workers.
  *Done when:* an event published on worker A reaches a socket held by worker B (run 2 uvicorn workers).
- [x] **3.6 Host screen lobby.** Big QR (client-side `qrcode`) with the join URL; avatars appear on `member_joined`. `/host/[code]`: QR, big code, live avatars, kick on hover, start button.
- [x] **3.7 Phone join flow.** Scan → sign in → age gate → consent → optional roots → "waiting for host". `/play/[code]`: `next` carries the room through sign-in, age gate, consent and roots, then back.
- [x] **3.8 Leave and kick.** `POST /rooms/{code}/leave` ("Leave and delete my data") and host kick. Both are missing from the design's API table; add them there. `POST /rooms/{code}/leave` and `/kick`; membership delete cascades all of that player's room data, Neo4j node removed, kicked players blocked from rejoining.

## Phase 4 — The game round

- [x] **4.1 Question bank.** Write about 30 questions (single choice, multi-select, slider) on behaviour, hobbies and interests; load into `questions`. *(parallel with 4.2)* 30 questions (13 single, 9 multi, 8 slider) in `game/data/questions.json`; `python -m orbit.seed --banks`.
- [x] **4.2 Facts bank v1.** 100 facts as JSON with 1–3 tags from the fixed tag list; loader script. Grow to 300+ later. *(parallel with 4.1)* 100 facts across all 9 tags in `content/data/facts.json`. LLM-drafted: review by hand before launch.
- [x] **4.3 Deck builder.** Seeded draw of 10 questions + 15 content cards, max 3 cards per tag; `GET /rooms/{code}/deck` returns the same deck to every member. `game/deck.py`: seeded by room, ≤3 cards per tag, questions interleaved with 2 cards each; frozen into `rooms.deck` at start.
- [x] **4.4 Start round.** `POST /rooms/{code}/start`: state → `PLAYING`, `ends_at`, `game_started` event, schedule the round-end job in `arq`. Start needs the lobby and 2+ players; `end_round` job deferred to `ends_at` with a fixed job id.
- [x] **4.5 Phone card UI.** Card stack with countdown; question cards for all 3 types; content cards with like / laugh / skip / send. Card stack, countdown, single/multi/slider questions, fact/meme/news cards with Haha/Like/Send/Skip; resumes after reload.
- [x] **4.6 Save answers and reactions.** Idempotent `PUT` endpoints; client retry queue so a flaky connection loses nothing. Idempotent upsert PUTs with validation and a 15 s grace; `lib/room/outbox.ts` persists pending writes in localStorage and retries with backoff.
- [x] **4.7 Likes and follows.** `POST /rooms/{code}/social` + a player list on the phone. `POST /rooms/{code}/social` + follow/like list on the phone (lobby and reveal).
- [x] **4.8 Finish and progress.** `POST /rooms/{code}/finish`; `progress` event; progress bar on the host screen. `progress` event drives the host's live progress bar.
- [x] **4.9 Round end.** Timer expiry or all players finished (whichever first, only once) → `SCORING`, `scoring` event, enqueue the scoring job. Last finisher or timer, whichever first, exactly once; `scoring` event; `score_room` job.

## Phase 5 — Closeness scoring  → **M2**

Pure functions first, all unit-tested, no database.

- [x] **5.1 Answer similarity `S_ans`.** Vectorise answers (one-hot, multi-hot, 0–1 slider), cosine over shared questions; skip below 5 shared. Slider encoded as [v, 1-v] so 0.2 vs 0.9 differ.
- [x] **5.2 Reaction similarity `S_react`.** like/laugh = +1, send = +1.5, skip = −1; cosine rescaled to 0–1; skip below 6 shared items.
- [x] **5.3 Shared roots `S_roots`.** `min(1, 0.6·school + 0.25·birth city + 0.15·Jaccard(childhood))`; skip if either side is blank.
- [x] **5.4 Social `S_social`.** 0.4 per follow direction + 0.05 per profile like, capped at 1.
- [x] **5.5 Combine.** Weights 35/35/15/15, redistribute weight of skipped signals; tests for symmetry and the 0–1 range. Property test over random rooms: symmetric, 0-1.
- [x] **5.6 Explanations.** Top contributing items per pair ("You both laughed at 7 of 9 memes", "Shared roots"). Roots reasons are always the generic label; a test asserts no school or city name appears in any explanation. Up to 3 reasons per pair, e.g. “Both picked ‘Chai’ for ‘Chai or coffee?’”, “You both laughed at 7 of 9 memes”; test asserts no school or city name ever appears.
- [x] **5.7 Scoring job.** Load room data → compute all pairs → write `scores` → hand off to Phase 6. `orbit/pipeline.py` composes module services; worker job `score_room`.

## Phase 6 — Neo4j graph

- [x] **6.1 Neo4j client.** Driver setup, constraints and indexes on `(room, id)`. Uniqueness constraints on (room, id); only the graph module imports `neo4j` (others use the `GraphDriver` alias).
- [x] **6.2 Projection writer.** `Person`, `FOLLOWS`, `REACTED`, `Place`, `CLOSE_TO`, all tagged with `room`. Full rewrite per room, idempotent.
- [x] **6.3 Edge selection.** Draw `CLOSE_TO` when total ≥ 0.4, plus each player's top 3 so nobody is isolated. `graph/edges.py`.
- [x] **6.4 Clusters.** Louvain → `Person.community`. **Risk:** Neo4j Aura Free has no GDS. Build a fallback that runs Louvain in Python (`networkx`) and writes the result back. GDS Louvain when installed, networkx Louvain otherwise; a test checks both give the same groups. Stable colour labels.
- [x] **6.5 Reveal.** State → `REVEALED`, `reveal` event.
- [x] **6.6 `GET /rooms/{code}/graph`.** One view for members and the host screen: every edge carries its score and explanations. Rebuilds from Postgres automatically if Neo4j lost the room.
- [x] **6.7 Rebuild command.** Re-project a room from Postgres into Neo4j (proves Neo4j is disposable). `pipeline.project` / `graph_for`; tested by wiping Neo4j mid-reveal.

## Phase 7 — Reveal UI  → **M3 (with Phase 8)**

- [x] **7.1 Cytoscape.js spike.** 20 nodes, all 190 edges on a TV-sized screen with an animated force layout (`fcose` or `cola` extension) and readable score labels. Same component on a phone screen. Cytoscape.js + fcose; same component on TV, phone and history.
- [x] **7.2 Host reveal.** Animated graph, community colours, names, scores on edges (edge thickness by score). Group legend, edge thickness and % by score, tap an edge for reasons.
- [x] **7.3 Phone reveal.** Same full graph, plus my closeness list (sorted); tap any edge → its score and explanations. Graph, “Closest to you” list with top reason, tap for full breakdown.
- [x] **7.4 Live edges after reveal.** `social_added` animates new follow edges (no re-score in MVP). Follows after the reveal are pushed live and drawn as dashed arrows (no re-score).

## Phase 8 — Retention and privacy

- [x] **8.1 Snapshot writer.** Each player's ego graph + scores as JSON into `graph_snapshots`. Ego graph (me, neighbours, my edges and follows) as JSON.
- [x] **8.2 Expiry job (hourly).** Snapshot → delete room in Postgres → delete Neo4j subgraph by `room` → audit log entry. Hourly cron; audit entries hold codes and counts only.
- [x] **8.3 Closing warning.** `room_closing` event 1 h before expiry. Deferred job at `expires_at - 1h`; banner on phones and TV.
- [x] **8.4 History page.** `GET /me/snapshots` + re-render saved graphs. `/history` re-renders saved graphs.
- [x] **8.5 Delete account.** `DELETE /me` removes account, roots and snapshots within 24 h. `DELETE /me` runs immediately: Neo4j nodes, identity (cascades profile, roots, snapshots, every membership); `member_left` sent to their rooms; audit entry. A host's rooms survive (host set to null).
- [x] **8.6 Deletion tests.** After expiry, no row or node for that room exists in either store. End-to-end test: no Postgres row or Neo4j node left for an expired room.

## Phase 9 — Live content pipeline

- [x] **9.1 Curator job framework.** Daily `arq` cron; each source is a plugin that returns content items. `content/curator.py`, daily cron 03:30 UTC; each source optional by key.
- [x] **9.2 Imgflip memes.** `/get_memes` → LLM captions → `/caption_image`; 20 per day. Built and tested with a mocked Imgflip API. **Needs your `IMGFLIP_USERNAME`/`PASSWORD` and `ANTHROPIC_API_KEY` to run for real.**
- [x] **9.3 NewsData.io headlines.** About 50 per day, India + world. Built and tested with a mocked API. **Needs your `NEWSDATA_API_KEY`.**
- [x] **9.4 LLM tagging.** Proposes 1–3 tags; the job rejects any tag outside the fixed list. One Claude call (Opus 5.5, low effort, structured JSON output, server-side refusal fallback) tags and moderates each batch; tags outside the fixed list are dropped.
- [x] **9.5 Moderation pass.** Drop NSFW, hateful or graphic items before `active = true`. Same review call; no verdict or unsafe = not stored. Without `ANTHROPIC_API_KEY` nothing new is stored.
- [ ] **9.6 Facts bank to 300+.** `python -m orbit.modules.content.draft_facts` drafts candidates into a review file (needs `ANTHROPIC_API_KEY`). **Left for you:** run it, review by hand, move good facts into `facts.json`.

## Phase 10 — Hardening and launch  → **M4**

- [x] **10.1 PWA.** Manifest, icons, installable, offline shell. Manifest, generated icons (incl. maskable and Apple), service worker with offline page; registered in production builds.
- [x] **10.2 Abuse controls.** Rate limits review, room cap, kick, max rooms per host per day. Join rate (10/min), rooms per host per day (10), room cap (20), host kick with rejoin block — all env-tunable.
- [x] **10.3 Observability.** Error tracking (e.g. Sentry) on web and API, basic metrics per room. Sentry for API and worker when `SENTRY_DSN` is set (no PII); token-protected `GET /health/metrics`; browser errors posted to `/api/client-error` and logged as JSON.
- [x] **10.4 Load test.** 20 concurrent full rooms (20 players each) through WebSockets. `api/loadtest/run.py`: 20 rooms × 20 players on a laptop, 2 API processes: 20/20 revealed, 0 failures, 9,200 events delivered, reveal 0.8 s after the last finisher (details in docs/playtest.md).
- [ ] **10.5 Deploy.** `api/Dockerfile` (one image: API, worker, migrations), built in CI and smoke-tested locally; step-by-step guide in [docs/deploy.md](docs/deploy.md). **Left for you:** create the accounts (Vercel, container host, Postgres, Neo4j Aura) and deploy.
- [ ] **10.6 Playtests.** **Left for you:** 3–5 real rooms. All knobs are env vars; method in [docs/playtest.md](docs/playtest.md).
- [ ] **10.7 Legal review.** **Left for you:** consent notice and flow reviewed by a lawyer before public launch.

---

## Gaps found in the design while planning

1. **Neo4j GDS on the free tier.** Aura Free does not include Graph Data Science, so Louvain needs the Python fallback in 6.4 (or a paid tier / self-hosted Neo4j).
2. **Job runner not named.** Round timers, scoring, hourly expiry and the daily curator all need one. Decided: `arq` on Redis (ADR 0001).
3. **Auth.js → FastAPI.** Resolved by [ADR 0002](docs/adr/0002-better-auth.md): Better Auth issues JWTs, FastAPI verifies them via JWKS.
4. **Missing endpoints.** Leave-and-delete and host kick (3.8).
5. **Missing columns.** `users.consented_at` and an avatar field for `member_joined` (1.3).
