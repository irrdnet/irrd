import os
import platform

import sqlalchemy as sa
import ujson

from irrd.conf import get_setting

engine: sa.engine.Engine = None


def get_engine():
    global engine
    if engine:
        return engine
    engine = sa.create_engine(
        translate_url(get_setting('database_url')),
        pool_size=2,
        json_deserializer=ujson.loads,
    )

    # https://docs.sqlalchemy.org/en/13/core/pooling.html#using-connection-pools-with-multiprocessing
    @sa.event.listens_for(engine, "connect")
    def connect(dbapi_connection, connection_record):
        connection_record.info['pid'] = os.getpid()

    @sa.event.listens_for(engine, "checkout")
    def checkout(dbapi_connection, connection_record, connection_proxy):
        pid = os.getpid()
        if connection_record.info['pid'] != pid:  # pragma: no cover
            connection_record.connection = connection_proxy.connection = None
            raise sa.exc.DisconnectionError(
                "Connection record belongs to pid %s, "
                "attempting to check out in pid %s" %
                (connection_record.info['pid'], pid)
            )

    return engine


def translate_url(url_str: str) -> sa.engine.url.URL:
    """Translate a url string to a SQLAlchemy URL object with the right driver"""
    url = sa.engine.url.make_url(url_str)
    if url.drivername == 'postgresql' and platform.python_implementation() == 'PyPy':  # pragma: no cover
        url.drivername = 'postgresql+psycopg2cffi'
    return url
