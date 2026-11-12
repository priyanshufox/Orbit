# ADR 0002 — Better Auth for sign-in, JWKS-verified tokens for the API

- **Status:** Accepted (replaces the design's "Auth.js" choice)
- **Date:** 2026-11-13

## Decision

Sign-in uses [Better Auth](https://www.better-auth.com) 1.7 inside the Next.js app: Google plus email magic links. FastAPI never sees cookies. For each API call, the web app gets a 15-minute JWT from Better Auth's `jwt` plugin. FastAPI verifies it against the public keys at `/api/auth/jwks`.

## Context

- Auth.js v5 was still a beta (`5.0.0-beta.32`) with no release since July 2026, and its maintainers now point new projects to Better Auth. Better Auth is stable and releases often.
- Magic links need a token store either way. Better Auth brings its own tables.
- Orbit must store nothing about under-18s (DPDP Rules 2025), so a profile cannot be created at sign-in.

## How it fits together

| Piece | Where | Notes |
|---|---|---|
| Identity (`auth.user`, `session`, `account`, `verification`, `jwks`) | Postgres schema `auth` | Created by Alembic migration 3 from `npx auth@1.7.22 generate` output; autogenerate ignores the schema |
| Orbit profile (`public.users`) | Postgres, accounts module | Created by `POST /me/age` only for adults; `users.id` = `auth.user.id`, FK with cascade |
| Token check | `api/src/orbit/core/auth.py` | EdDSA (Ed25519), issuer and audience = web URL, keys cached for 1 h |
| Profile check | `orbit.modules.accounts.deps.CurrentUserDep` | 403 `onboarding_required` until the age gate is passed |

For under-18s, `POST /me/age` deletes `auth.user`, and sessions and accounts cascade. Only the birth year is stored, but the exact date of birth is checked.

## Consequences

- No secret is shared between web and API. Key rotation is handled by JWKS.
- Upgrading Better Auth means regenerating its SQL and diffing it against migration 3.
- The web app needs Postgres access (`AUTH_DATABASE_URL`) for the `auth` schema.
