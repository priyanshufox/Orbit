"""auth schema and identity link

Better Auth (web app) keeps sign-in identity in schema "auth". The tables below are the SQL that
`npx auth@1.7.22 generate --config src/lib/auth.ts` printed for our config (uuid ids, magic link,
jwt plugins), qualified with the schema. Regenerate and diff when upgrading Better Auth.

public.users.id becomes a foreign key to auth.user.id, so deleting an identity deletes the
Orbit profile (and through it roots, snapshots and room data).

Revision ID: 62585c9c74a1
Revises: f5b1ee6c9b26
Create Date: 2026-11-13 00:11:42.559950

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "62585c9c74a1"
down_revision: str | Sequence[str] | None = "f5b1ee6c9b26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUTH_TABLES_SQL = """
create schema if not exists auth;

create table auth."user" (
    "id" uuid default pg_catalog.gen_random_uuid() not null primary key,
    "name" text not null,
    "email" text not null unique,
    "emailVerified" boolean not null,
    "image" text,
    "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
    "updatedAt" timestamptz default CURRENT_TIMESTAMP not null
);

create table auth."session" (
    "id" uuid default pg_catalog.gen_random_uuid() not null primary key,
    "expiresAt" timestamptz not null,
    "token" text not null unique,
    "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
    "updatedAt" timestamptz not null,
    "ipAddress" text,
    "userAgent" text,
    "userId" uuid not null references auth."user" ("id") on delete cascade
);

create table auth."account" (
    "id" uuid default pg_catalog.gen_random_uuid() not null primary key,
    "accountId" text not null,
    "providerId" text not null,
    "userId" uuid not null references auth."user" ("id") on delete cascade,
    "accessToken" text,
    "refreshToken" text,
    "idToken" text,
    "accessTokenExpiresAt" timestamptz,
    "refreshTokenExpiresAt" timestamptz,
    "scope" text,
    "password" text,
    "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
    "updatedAt" timestamptz not null
);

create table auth."verification" (
    "id" uuid default pg_catalog.gen_random_uuid() not null primary key,
    "identifier" text not null,
    "value" text not null,
    "expiresAt" timestamptz not null,
    "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
    "updatedAt" timestamptz default CURRENT_TIMESTAMP not null
);

create table auth."jwks" (
    "id" uuid default pg_catalog.gen_random_uuid() not null primary key,
    "publicKey" text not null,
    "privateKey" text not null,
    "createdAt" timestamptz not null,
    "expiresAt" timestamptz,
    "alg" text,
    "crv" text
);

create index "session_userId_idx" on auth."session" ("userId");
create index "account_userId_idx" on auth."account" ("userId");
create index "verification_identifier_idx" on auth."verification" ("identifier");
"""


def upgrade() -> None:
    # asyncpg runs one statement per call.
    for statement in AUTH_TABLES_SQL.split(";"):
        if statement.strip():
            op.execute(statement)

    # Existing profiles (e.g. dev seed data) get a matching identity so the link can be added.
    op.execute(
        'insert into auth."user" ("id", "name", "email", "emailVerified") '
        "select id, name, email, true from public.users on conflict do nothing"
    )
    op.alter_column("users", "id", server_default=None)
    op.create_foreign_key(
        op.f("fk_users_id_user"),
        "users",
        "user",
        ["id"],
        ["id"],
        referent_schema="auth",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_users_id_user"), "users", type_="foreignkey")
    op.alter_column("users", "id", server_default=sa.text("gen_random_uuid()"))
    op.execute("drop schema auth cascade")
