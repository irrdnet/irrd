import sqlalchemy as sa
import ujson

from sqlalchemy.pool import NullPool

from irrd.conf import get_setting


def get_engine():
    return sa.create_engine(
        get_setting('database_url'),
        poolclass=NullPool,
        json_deserializer=ujson.loads,
    )
