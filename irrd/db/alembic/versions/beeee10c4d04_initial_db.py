"""initial db

Revision ID: beeee10c4d04
Revises:
Create Date: 2018-06-08 14:16:50.336752

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'beeee10c4d04'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('rpsl_objects',
                    sa.Column('rpsl_pk', sa.String(), nullable=False),
                    sa.Column('source', sa.String(), nullable=False),
                    sa.Column('object_class', sa.String(), nullable=False),
                    sa.Column('parsed_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
                    sa.Column('internal_object_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
                    sa.Column('object_txt', sa.Text(), nullable=False),
                    sa.Column('ip_version', sa.Integer(), nullable=True),
                    sa.Column('ip_first', postgresql.INET(), nullable=True),
                    sa.Column('ip_last', postgresql.INET(), nullable=True),
                    sa.Column('asn_first', sa.Integer(), nullable=True),
                    sa.Column('asn_last', sa.Integer(), nullable=True),
                    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
                    sa.Column('updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
                    sa.PrimaryKeyConstraint('rpsl_pk', 'source'),
                    sa.UniqueConstraint('rpsl_pk', 'source', name='rpsl_pk_source_unique')
                    )
    op.create_index(op.f('ix_rpsl_objects_asn_first'), 'rpsl_objects', ['asn_first'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_asn_last'), 'rpsl_objects', ['asn_last'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_ip_first'), 'rpsl_objects', ['ip_first'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_ip_last'), 'rpsl_objects', ['ip_last'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_ip_version'), 'rpsl_objects', ['ip_version'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_object_class'), 'rpsl_objects', ['object_class'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_rpsl_pk'), 'rpsl_objects', ['rpsl_pk'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_source'), 'rpsl_objects', ['source'], unique=False)

    # Manually added
    op.create_index(op.f('ix_rpsl_objects_parsed_data_zone_c'), 'rpsl_objects', [sa.text("((parsed_data->'zone-c'))")],
                    unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_rpsl_objects_parsed_data_role'), 'rpsl_objects', [sa.text("((parsed_data->'role'))")],
                    unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_rpsl_objects_parsed_data_members'), 'rpsl_objects',
                    [sa.text("((parsed_data->'members'))")], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_rpsl_objects_parsed_data_person'), 'rpsl_objects', [sa.text("((parsed_data->'person'))")],
                    unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_rpsl_objects_parsed_data_mnt_by'), 'rpsl_objects', [sa.text("((parsed_data->'mnt-by'))")],
                    unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_rpsl_objects_parsed_data_member_of'), 'rpsl_objects',
                    [sa.text("((parsed_data->'member-of'))")], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_rpsl_objects_parsed_data_mp_members'), 'rpsl_objects',
                    [sa.text("((parsed_data->'mp-members'))")], unique=False, postgresql_using='gin')


def downgrade():
    op.drop_index(op.f('ix_rpsl_objects_source'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_rpsl_pk'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_object_class'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_ip_version'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_ip_last'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_ip_first'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_asn_last'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_asn_first'), table_name='rpsl_objects')

    # Manually added
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_zone_c'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_role'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_members'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_person'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_mnt_by'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_member_of'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_mp_members'), table_name='rpsl_objects')

    op.drop_table('rpsl_objects')
