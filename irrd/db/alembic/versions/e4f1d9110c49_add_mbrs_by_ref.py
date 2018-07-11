"""add_mbrs_by_ref

Revision ID: e4f1d9110c49
Revises: 28dc1cd85bdc
Create Date: 2018-07-10 16:39:11.582319

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4f1d9110c49'
down_revision = '28dc1cd85bdc'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_rpsl_objects_parsed_data_mbrs_by_ref'), 'rpsl_objects', [sa.text("((parsed_data->'mbrs-by-ref'))")],
                    unique=False, postgresql_using='gin')


def downgrade():
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_mbrs_by_ref'), table_name='rpsl_objects')
