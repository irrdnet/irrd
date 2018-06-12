import sqlalchemy as sa

from ..conf import get_setting

engine = sa.create_engine(get_setting('database_url'))
