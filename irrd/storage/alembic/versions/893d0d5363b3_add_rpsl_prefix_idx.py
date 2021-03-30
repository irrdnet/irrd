"""add_rpsl_prefix_idx

Revision ID: 893d0d5363b3
Revises: b175c262448f
Create Date: 2021-03-01 16:11:28.275554

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '893d0d5363b3'
down_revision = 'b175c262448f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_rpsl_objects_prefix_gist', 'rpsl_objects', [sa.text('prefix inet_ops')], unique=False, postgresql_using='gist')


def downgrade():
    op.drop_index('ix_rpsl_objects_prefix_gist', table_name='rpsl_objects')
