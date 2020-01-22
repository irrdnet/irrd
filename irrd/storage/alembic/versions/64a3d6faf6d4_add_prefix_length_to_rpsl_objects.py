"""Add prefix_length to rpsl_objects

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
    op.add_column('rpsl_objects', sa.Column('prefix_length', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('rpsl_objects', 'prefix_length')
