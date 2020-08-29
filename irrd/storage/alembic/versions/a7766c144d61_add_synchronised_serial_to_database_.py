"""Add synchronised_serial to database status

Revision ID: a7766c144d61
Revises: 4a514ead8fc2
Create Date: 2020-08-29 19:14:41.800696

"""
import sqlalchemy as sa
from alembic import op

from irrd.storage.database_handler import is_serial_synchronised
from irrd.storage.models import RPSLDatabaseStatus

# revision identifiers, used by Alembic.
revision = 'a7766c144d61'
down_revision = '4a514ead8fc2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('database_status', sa.Column('synchronised_serials', sa.Boolean(), nullable=False, server_default='f'))

    connection = op.get_bind()
    t_db_status = RPSLDatabaseStatus.__table__

    for row in connection.execute(t_db_status.select()):
        synchronised_serials = is_serial_synchronised(None, row['source'], settings_only=True)
        connection.execute(t_db_status.update().where(
            t_db_status.c.source == row['source']
        ).values(
            synchronised_serials=synchronised_serials,
        ))


def downgrade():
    op.drop_column('database_status', 'synchronised_serials')
