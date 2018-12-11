import sqlalchemy as sa

from irrd.conf import get_setting

database_pool_size = (get_setting('server.whois.max_connections') + len(get_setting('sources', []))) * 3
engine = sa.create_engine(get_setting('database_url'), pool_size=database_pool_size, max_overflow=30)
