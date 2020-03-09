"""Add prefix_length and rpki_status to rpsl_objects

Revision ID: 64a3d6faf6d4
Revises: e07863eac52f
Create Date: 2019-03-04 14:39:14.711874

"""
# revision identifiers, used by Alembic.
import sqlalchemy as sa
from alembic import op

revision = '64a3d6faf6d4'
down_revision = 'e07863eac52f'
branch_labels = None
depends_on = None


def upgrade():
    rpki_status = sa.Enum('valid', 'invalid', 'not_found', name='rpkistatus')
    rpki_status.create(op.get_bind())

    op.add_column('rpsl_objects', sa.Column('rpki_status', sa.Enum('valid', 'invalid', 'not_found', name='rpkistatus'), nullable=False, server_default='not_found'))
    op.create_index(op.f('ix_rpsl_objects_rpki_status'), 'rpsl_objects', ['rpki_status'], unique=False)

    op.add_column('rpsl_objects', sa.Column('prefix_length', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('rpsl_objects', 'prefix_length')
    op.drop_index(op.f('ix_rpsl_objects_rpki_status'), table_name='rpsl_objects')
    op.drop_column('rpsl_objects', 'rpki_status')

    rpki_status = sa.Enum('valid', 'invalid', 'not_found', name='rpkistatus')
    rpki_status.drop(op.get_bind())
