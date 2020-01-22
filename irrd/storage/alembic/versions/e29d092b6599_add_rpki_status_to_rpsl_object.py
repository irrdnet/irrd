"""Add rpki status to rpsl_object

Revision ID: e29d092b6599
Revises: a8609af97aa3
Create Date: 2019-03-08 14:59:25.938638

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e29d092b6599'
down_revision = 'a8609af97aa3'
branch_labels = None
depends_on = None


def upgrade():
    rpki_status = sa.Enum('valid', 'invalid', 'unknown', name='rpkistatus')
    rpki_status.create(op.get_bind())

    op.add_column('rpsl_objects', sa.Column('rpki_status', sa.Enum('valid', 'invalid', 'unknown', name='rpkistatus'), nullable=False, server_default='unknown'))
    op.create_index(op.f('ix_rpsl_objects_rpki_status'), 'rpsl_objects', ['rpki_status'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_rpsl_objects_rpki_status'), table_name='rpsl_objects')
    op.drop_column('rpsl_objects', 'rpki_status')

    rpki_status = sa.Enum('valid', 'invalid', 'unknown', name='rpkistatus')
    rpki_status.drop(op.get_bind())
