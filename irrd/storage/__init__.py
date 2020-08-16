import os
import sqlalchemy as sa
import ujson

from irrd.conf import get_setting

engine = None


def get_engine():
    global engine
    if engine:
        return engine
    engine = sa.create_engine(
        get_setting('database_url'),
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
