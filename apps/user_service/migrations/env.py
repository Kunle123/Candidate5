import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from apps.user_service.app.models import Base

config = context.config

# PATCH: Use USER_DATABASE_URL from environment if sqlalchemy.url is blank
if not config.get_main_option("sqlalchemy.url"):
    user_url = os.environ.get("USER_DATABASE_URL")
    print(f"[DEBUG] USER_DATABASE_URL in env.py: {user_url}")
    if user_url:
        config.set_main_option("sqlalchemy.url", user_url)
print(f"[DEBUG] sqlalchemy.url in config: {config.get_main_option('sqlalchemy.url')}")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
