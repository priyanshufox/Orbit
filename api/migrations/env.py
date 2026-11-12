"""Alembic environment. The database URL comes from app settings (or `config.attributes["url"]`
when called from tests), never from alembic.ini."""

import asyncio
import importlib
import pkgutil
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import orbit.modules
from orbit.core.config import get_settings
from orbit.core.db import Base

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)


def load_all_models() -> None:
    """Import every module's `models.py` so its tables register on Base.metadata."""
    for info in pkgutil.iter_modules(orbit.modules.__path__):
        name = f"orbit.modules.{info.name}.models"
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as e:
            if e.name != name:
                raise


load_all_models()
target_metadata = Base.metadata

# Better Auth's tables (schema "auth") are written by hand in migration 3 from the SQL that its
# CLI generates; autogenerate must not try to manage them.
UNMANAGED_SCHEMAS = {"auth"}


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    table = obj if type_ == "table" else getattr(obj, "table", None)
    return getattr(table, "schema", None) not in UNMANAGED_SCHEMAS


def database_url() -> str:
    return config.attributes.get("url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(database_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
