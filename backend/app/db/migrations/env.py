"""
app/db/migrations/env.py
=========================
Alembic environment configuration — run context and database URL injection.

Design decisions:
- The database URL is read from `get_settings().db.sync_url` at runtime.
  It is NEVER hardcoded or sourced from alembic.ini, which ensures that
  credentials are kept out of version control.
- Both `run_migrations_offline()` (for generating SQL scripts) and
  `run_migrations_online()` (for applying migrations against a live DB) are
  implemented with the sync psycopg2 driver, which is the standard Alembic
  approach.
- `include_schemas=False` keeps all tables in the default `public` schema.
- `compare_type=True` enables Alembic to detect column type changes
  (e.g. VARCHAR(255) → VARCHAR(512)) and include them in auto-generated
  migration scripts.
- `compare_server_default=True` enables detection of server_default changes,
  important for our timestamp columns.
- All ORM models are imported via `app.models` so that `Base.metadata` is
  fully populated before `autogenerate` runs.

Usage::

    # Apply pending migrations
    alembic upgrade head

    # Auto-generate a new migration after model changes
    alembic revision --autogenerate -m "add_column_foo_to_bar"

    # Downgrade one step
    alembic downgrade -1

    # Generate SQL without applying (for review)
    alembic upgrade head --sql > migration.sql
"""

from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Alembic config object — gives access to values in alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# ---------------------------------------------------------------------------
# Logging — configure from alembic.ini [loggers] section
# ---------------------------------------------------------------------------
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# ---------------------------------------------------------------------------
# Inject database URL from application settings
# ---------------------------------------------------------------------------
# Import settings AFTER fileConfig so logging is initialised first
from app.core.config import get_settings  # noqa: E402
from app.shared.models_registry import Base  # noqa: E402, F401 — populates Base.metadata

_settings = get_settings()
config.set_main_option("sqlalchemy.url", _settings.db.sync_url)

# ---------------------------------------------------------------------------
# Target metadata — Alembic compares this against the live DB
# ---------------------------------------------------------------------------
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline migration (--sql mode)
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    In this mode Alembic does not connect to the database but instead
    writes the SQL DDL statements to stdout or a file. Useful for:
    - Reviewing changes before applying
    - Generating migration scripts for a DBA to apply manually
    - CI pipelines that must not connect to production

    Example::

        alembic upgrade head --sql > migration_review.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
        # Render AS UUID for PostgreSQL-specific column types
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migration (live database connection)
# ---------------------------------------------------------------------------


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode — connects to the database and applies
    DDL statements within a transaction.

    Uses `NullPool` to avoid holding an idle connection open after the
    migration script exits. This is the recommended Alembic pattern for
    scripts that run and then exit.
    """
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
            compare_server_default=True,
            include_schemas=False,
            render_as_batch=False,
            # Transactional DDL — all statements in one transaction
            transaction_per_migration=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    logger.info("Migrations applied successfully.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
