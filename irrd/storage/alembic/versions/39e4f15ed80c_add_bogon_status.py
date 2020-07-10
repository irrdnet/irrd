"""Add bogon_status

Revision ID: 39e4f15ed80c
Revises: 1743f98a456d
Create Date: 2020-04-22 14:43:57.985437

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.

revision = '39e4f15ed80c'
down_revision = '1743f98a456d'
branch_labels = None
depends_on = None


# This is a very strange migration.
# The bogon_status column was added at some point, but was never used.
# Some people's deployments have this migration already deployed, so
# this migration can't be removed. For anyone upgrading from earlier,
# we don't want to re-add it to then remove it in the next migration,
# because it takes a lot of time.
#
# Therefore, this migration does nothing to upgrade, and on downgrade
# removes the column, but only if it exists.
# It assumes the existence of the bogonstatus enum matches that of
# the bogon_status column.

def upgrade():
    pass


def downgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = inspector.get_columns('rpsl_objects')

    if 'bogon_status' in columns:
        op.drop_index(op.f('ix_rpsl_objects_bogon_status'), table_name='rpsl_objects')
        op.drop_column('rpsl_objects', 'bogon_status')
        bogon_status = sa.Enum('unknown', 'not_bogon', 'bogon_as', 'bogon_prefix', name='bogonstatus')
        bogon_status.drop(op.get_bind())
