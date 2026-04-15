"""Alembic environment.

Reads the database URL from the DATABASE_URL environment variable so the
same migration tree works against dev (Docker Postgres), staging (Neon), and
prod (Neon paid). Falls back to the project default for local SQLite.

Usage::

    DATABASE_URL=postgresql://... alembic upgrade head
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make backend/ importable so we can import models.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models import Base  # noqa: E402  (after sys.path mutation)
import models  # noqa: F401  (ensure all model classes are imported & registered)

config = context.config

# Pull DATABASE_URL from env, falling back to alembic.ini's value.
db_url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if not db_url:
    raise RuntimeError(
        "DATABASE_URL is not set. Export it before running alembic, e.g.\n"
        "  export DATABASE_URL=postgresql://user:pass@host/oltmanager_dev"
    )
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without connecting to a database."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
