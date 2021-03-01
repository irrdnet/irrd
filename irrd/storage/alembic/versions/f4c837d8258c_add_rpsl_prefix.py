"""add_rpsl_prefix

Revision ID: f4c837d8258c
Revises: a7766c144d61
Create Date: 2021-03-01 15:38:26.513071

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f4c837d8258c'
down_revision = 'a7766c144d61'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('rpsl_objects', sa.Column('prefix', postgresql.CIDR(), nullable=True))


def downgrade():
    op.drop_column('rpsl_objects', 'prefix')
