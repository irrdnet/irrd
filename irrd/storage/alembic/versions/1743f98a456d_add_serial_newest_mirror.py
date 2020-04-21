"""Add serial_newest_mirror

Revision ID: 1743f98a456d
Revises: 181670a62643
Create Date: 2020-04-15 20:08:59.925809

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1743f98a456d'
down_revision = '181670a62643'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('database_status', sa.Column('serial_newest_mirror', sa.Integer(), nullable=True))
    op.execute('UPDATE database_status SET serial_newest_mirror = serial_newest_seen')


def downgrade():
    op.drop_column('database_status', 'serial_newest_mirror')
