"""Add bogon_status

Revision ID: 39e4f15ed80c
Revises: 1743f98a456d
Create Date: 2020-04-22 14:43:57.985437

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '39e4f15ed80c'
down_revision = '1743f98a456d'
branch_labels = None
depends_on = None


def upgrade():
    bogon_status = sa.Enum('unknown', 'not_bogon', 'bogon_as', 'bogon_prefix', name='bogonstatus')
    bogon_status.create(op.get_bind())

    op.add_column('rpsl_objects', sa.Column('bogon_status', sa.Enum('unknown', 'not_bogon', 'bogon_as', 'bogon_prefix', name='bogonstatus'), nullable=False, server_default='unknown'))
    op.create_index(op.f('ix_rpsl_objects_bogon_status'), 'rpsl_objects', ['bogon_status'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_rpsl_objects_bogon_status'), table_name='rpsl_objects')
    op.drop_column('rpsl_objects', 'bogon_status')

    bogon_status = sa.Enum('unknown', 'not_bogon', 'bogon_as', 'bogon_prefix', name='bogonstatus')
    bogon_status.create(op.get_bind())
