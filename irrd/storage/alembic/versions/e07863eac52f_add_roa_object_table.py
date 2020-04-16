"""Add roa_object table.

Revision ID: e07863eac52f
Revises: 28dc1cd85bdc
Create Date: 2019-02-28 16:03:57.797697

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e07863eac52f'
down_revision = '28dc1cd85bdc'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('roa_object',
                    sa.Column('pk', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'),
                              nullable=False),
                    sa.Column('prefix', postgresql.CIDR(), nullable=False),
                    sa.Column('asn', sa.BigInteger(), nullable=False),
                    sa.Column('max_length', sa.Integer(), nullable=False),
                    sa.Column('trust_anchor', sa.String(), nullable=True),
                    sa.Column('ip_version', sa.Integer(), nullable=False),
                    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
                    sa.PrimaryKeyConstraint('pk'),
                    sa.UniqueConstraint('prefix', 'asn', 'max_length', 'trust_anchor', name='roa_object_prefix_asn_maxlength_unique')
                    )
    op.create_index(op.f('ix_roa_object_ip_version'), 'roa_object', ['ip_version'], unique=False)
    op.create_index('ix_roa_objects_prefix_gist', 'roa_object', [sa.text('prefix inet_ops')], unique=False,
                    postgresql_using='gist')


def downgrade():
    op.drop_index(op.f('ix_roa_objects_prefix_gist'), table_name='roa_object')
    op.drop_index(op.f('ix_roa_object_ip_version'), table_name='roa_object')
    op.drop_table('roa_object')
