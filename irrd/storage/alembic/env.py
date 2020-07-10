# flake8: noqa: E402
import os
import sys

from alembic import context
from pathlib import Path
from sqlalchemy import create_engine

sys.path.append(str(Path(__file__).resolve().parents[3]))

from irrd.conf import get_setting, config_init, is_config_initialised
from irrd.storage.models import Base

target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    if not is_config_initialised():
        config_init(os.environ['IRRD_CONFIG_FILE'])
    url = get_setting('database_url')
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        transaction_per_migration=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    if not is_config_initialised():
        config_init(os.environ['IRRD_CONFIG_FILE'])
    engine = create_engine(get_setting('database_url'))

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
