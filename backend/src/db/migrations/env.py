# =============================================================================
# PH Agent Hub — Alembic Environment Configuration
# =============================================================================
# Phase 0: No ORM models exist yet. This file reads DATABASE_URL from the
# environment and configures Alembic. With no migration files in versions/,
# `alembic upgrade head` simply reports "nothing to do" and exits 0.
# =============================================================================

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

# Alembic Config object
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Phase 0: No declarative Base or metadata yet.
# When models are added, import Base and set:
#   target_metadata = Base.metadata
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the SQL to the script output.
    """
    url = os.environ["DATABASE_URL"]
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine from the DATABASE_URL environment variable
    and associates a connection with the context.

    Note: We use pymysql (sync) here instead of aiomysql because Alembic
    runs synchronously. The DATABASE_URL is rewritten to use pymysql.
    """
    url = os.environ["DATABASE_URL"]
    # Alembic runs synchronously, so replace async driver with sync driver
    url = url.replace("aiomysql", "pymysql")
    connectable = create_engine(url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
