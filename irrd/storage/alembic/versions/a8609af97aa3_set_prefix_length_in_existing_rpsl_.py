"""Set prefix_length in existing RPSL objects

Revision ID: a8609af97aa3
Revises: 64a3d6faf6d4
Create Date: 2019-03-04 16:14:17.862510

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.declarative import declarative_base


# revision identifiers, used by Alembic.
revision = 'a8609af97aa3'
down_revision = '64a3d6faf6d4'
branch_labels = None
depends_on = None
Base = declarative_base()


class RPSLDatabaseObject(Base):  # type:ignore
    __tablename__ = 'rpsl_objects'

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True)
    object_class = sa.Column(sa.String, nullable=False, index=True)
    ip_size = sa.Column(sa.DECIMAL(scale=0))
    prefix_length = sa.Column(sa.Integer, nullable=True)


def upgrade():
    connection = op.get_bind()
    t_rpsl_objects = RPSLDatabaseObject.__table__

    for length in range(33):
        ip_size = pow(2, 32-length)
        connection.execute(t_rpsl_objects.update().where(
            sa.and_(t_rpsl_objects.c.ip_size == ip_size, t_rpsl_objects.c.object_class == 'route')
        ).values(
            prefix_length=length,
        ))

    for length in range(129):
        ip_size = pow(2, 128-length)
        connection.execute(t_rpsl_objects.update().where(
            sa.and_(t_rpsl_objects.c.ip_size == ip_size, t_rpsl_objects.c.object_class == 'route6')
        ).values(
            prefix_length=length,
        ))


def downgrade():
    pass
