"""
Testing configuration, used by py.test.
Fixtures defined here are available to all tests.
"""
import os
import pytest
from typing import Dict, Any

import redis
import sqlalchemy
from sqlalchemy.engine import reflection
from sqlalchemy.exc import ProgrammingError

from irrd import conf
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.storage import get_engine
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import RPSLDatabaseObject, JournalEntryOrigin
from irrd.storage.orm_provider import ORMSessionProvider
from irrd.utils.factories import set_factory_session, AuthUserFactory
from irrd.utils.rpsl_samples import SAMPLE_KEY_CERT, SAMPLE_MNTNER, SAMPLE_PERSON, SAMPLE_ROLE
from irrd.vendor.dotted.collection import DottedDict
from irrd.webui.helpers import secret_key_derive


@pytest.fixture()
def config_override(monkeypatch):
    """
    Fixture to override part of the configuration, by providing a dict
    with new config data.

    Note that subsequent calls override previous ones, so the entire
    override dict must be supplied every time.
    """
    def _override(override_data: Dict[Any, Any]):
        monkeypatch.setattr('irrd.conf.testing_overrides', DottedDict(override_data))
    return _override


@pytest.fixture()
def tmp_gpg_dir(tmpdir, monkeypatch):
    """
    Fixture to use a temporary separate gpg dir, to prevent it using your
    user's keyring.

    NOTE: if the gpg keyring name is very long, this introduces a 5 second
    delay in all gpg tests due to gpg incorrectly waiting to find a gpg-agent.
    Default tmpdirs on Mac OS X are affected, to prevent this run pytest with:
        --basetemp=.tmpdirs
    """
    os.environ['IRRD_AUTH_GNUPG_KEYRING'] = str(tmpdir) + "/gnupg"


@pytest.fixture()
def preload_gpg_key():
    """
    Fixture to load a known PGP key into the configured keychain.
    """
    # Simply parsing the key-cert will load it into the GPG keychain
    rpsl_text = SAMPLE_KEY_CERT
    rpsl_object_from_text(rpsl_text)


def pytest_configure(config):
    """
    This function is called by py.test, and will set flags to
    indicate tests are running. This is used by the configuration
    checker to not require a full working config for most tests.
    Can be checked with:
        hasattr(sys, '_called_from_test')
    Note that this function is only called once, not for every test.
    """
    import sys
    sys._called_from_test = True
    os.environ["TESTING"] = "true"


@pytest.fixture(autouse=True)
def reset_config():
    """
    This fixture is called for every test in the project,
    and resets the configuration to default.
    """
    conf.config_init(None)
    conf.testing_overrides = None


@pytest.fixture(scope="package")
def irrd_database_create_destroy():
    """
    Some tests use a live PostgreSQL database, as it's rather complicated
    to mock, and mocking would not make them less useful.
    Using in-memory SQLite is not an option due to using specific
    PostgreSQL features.

    To improve performance, these tests do not run full migrations, but
    the database is only created once per session, and truncated between tests.
    """
    if not conf.is_config_initialised():
        conf.config_init(None)
        conf.testing_overrides = None

    engine = get_engine()
    connection = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    inspector = sqlalchemy.inspect(engine)
    try:
        connection.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    except ProgrammingError as pe:  # pragma: no cover
        print(f"WARNING: unable to create extension pgcrypto on the database. Queries may fail: {pe}")
    table_name = RPSLDatabaseObject.__tablename__
    if inspector.has_table(table_name):  # pragma: no cover
        if engine.url.database not in ["irrd_test", "circle_test"]:
            print(
                f"The database on URL {engine.url} already has a table named {table_name} - "
                "delete existing database and all data in it?"
            )
            confirm = input(f"Type '{engine.url.database}' to confirm deletion\n> ")
            if confirm != engine.url.database:
                pytest.exit("Not overwriting database, terminating test run")
        RPSLDatabaseObject.metadata.drop_all(engine)

    RPSLDatabaseObject.metadata.create_all(engine)
    connection.close()

    yield engine

    engine.dispose()
    RPSLDatabaseObject.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def irrd_db(irrd_database_create_destroy):
    engine = irrd_database_create_destroy
    dh = DatabaseHandler()
    inspector = sqlalchemy.inspect(engine)
    for table in inspector.get_table_names():
        dh.execute_statement(sqlalchemy.text(f"TRUNCATE {table} CASCADE"))
    dh.commit()
    dh.close()


@pytest.fixture(scope="function")
def irrd_db_session_with_user(irrd_db):
    dh = DatabaseHandler()
    dh.upsert_rpsl_object(rpsl_object_from_text(SAMPLE_MNTNER), origin=JournalEntryOrigin.unknown)
    dh.upsert_rpsl_object(rpsl_object_from_text(SAMPLE_PERSON), origin=JournalEntryOrigin.unknown)
    dh.upsert_rpsl_object(rpsl_object_from_text(SAMPLE_ROLE), origin=JournalEntryOrigin.unknown)
    dh.commit()
    dh.close()

    provider = ORMSessionProvider()
    set_factory_session(provider.session)
    user = AuthUserFactory()
    provider.session.commit()
    provider.session.connection().execute(sqlalchemy.text("COMMIT"))

    yield provider, user

    provider.commit_close()
