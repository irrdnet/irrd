"""initial db

Revision ID: 28dc1cd85bdc
Revises:
Create Date: 2018-06-11 14:37:13.472465

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '28dc1cd85bdc'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Creating this extension requires extra permissions.
    # However, if it is already created, this command succeeds
    # even if this user does not have sufficient permissions.
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    op.create_table('database_status',
                    sa.Column('pk', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'),
                              nullable=False),
                    sa.Column('source', sa.String(), nullable=False),
                    sa.Column('serial_oldest_seen', sa.Integer(), nullable=True),
                    sa.Column('serial_newest_seen', sa.Integer(), nullable=True),
                    sa.Column('serial_oldest_journal', sa.Integer(), nullable=True),
                    sa.Column('serial_newest_journal', sa.Integer(), nullable=True),
                    sa.Column('serial_last_export', sa.Integer(), nullable=True),
                    sa.Column('force_reload', sa.Boolean(), nullable=False),
                    sa.Column('last_error', sa.Text(), nullable=True),
                    sa.Column('last_error_timestamp', sa.DateTime(timezone=True), nullable=True),
                    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
                    sa.Column('updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
                    sa.PrimaryKeyConstraint('pk')
                    )
    op.create_index(op.f('ix_database_status_source'), 'database_status', ['source'], unique=True)

    op.create_table('rpsl_database_journal',
                    sa.Column('pk', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'),
                              nullable=False),
                    sa.Column('rpsl_pk', sa.String(), nullable=False),
                    sa.Column('source', sa.String(), nullable=False),
                    sa.Column('serial_nrtm', sa.Integer(), nullable=False),
                    sa.Column('operation', sa.Enum('add_or_update', 'delete', name='databaseoperation'),
                              nullable=False),
                    sa.Column('object_class', sa.String(), nullable=False),
                    sa.Column('object_text', sa.Text(), nullable=False),
                    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
                    sa.PrimaryKeyConstraint('pk'),
                    sa.UniqueConstraint('serial_nrtm', 'source', name='rpsl_objects_history_serial_nrtm_source_unique')
                    )
    op.create_index(op.f('ix_rpsl_database_journal_object_class'), 'rpsl_database_journal', ['object_class'],
                    unique=False)
    op.create_index(op.f('ix_rpsl_database_journal_rpsl_pk'), 'rpsl_database_journal', ['rpsl_pk'], unique=False)
    op.create_index(op.f('ix_rpsl_database_journal_serial_nrtm'), 'rpsl_database_journal', ['serial_nrtm'],
                    unique=False)
    op.create_index(op.f('ix_rpsl_database_journal_source'), 'rpsl_database_journal', ['source'], unique=False)

    op.create_table('rpsl_objects',
                    sa.Column('pk', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'),
                              nullable=False),
                    sa.Column('rpsl_pk', sa.String(), nullable=False),
                    sa.Column('source', sa.String(), nullable=False),
                    sa.Column('object_class', sa.String(), nullable=False),
                    sa.Column('parsed_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
                    sa.Column('object_text', sa.Text(), nullable=False),
                    sa.Column('ip_version', sa.Integer(), nullable=True),
                    sa.Column('ip_first', postgresql.INET(), nullable=True),
                    sa.Column('ip_last', postgresql.INET(), nullable=True),
                    sa.Column('ip_size', sa.DECIMAL(scale=0), nullable=True),
                    sa.Column('asn_first', sa.BigInteger(), nullable=True),
                    sa.Column('asn_last', sa.BigInteger(), nullable=True),
                    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
                    sa.Column('updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
                    sa.PrimaryKeyConstraint('pk'),
                    sa.UniqueConstraint('rpsl_pk', 'source', name='rpsl_objects_rpsl_pk_source_unique')
                    )
    op.create_index(op.f('ix_rpsl_objects_ip_first'), 'rpsl_objects', ['ip_first'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_ip_last'), 'rpsl_objects', ['ip_last'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_asn_first'), 'rpsl_objects', ['asn_first'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_asn_last'), 'rpsl_objects', ['asn_last'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_ip_version'), 'rpsl_objects', ['ip_version'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_object_class'), 'rpsl_objects', ['object_class'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_rpsl_pk'), 'rpsl_objects', ['rpsl_pk'], unique=False)
    op.create_index(op.f('ix_rpsl_objects_source'), 'rpsl_objects', ['source'], unique=False)
    op.create_index('ix_rpsl_objects_asn_first_asn_last', 'rpsl_objects', ['asn_first', 'asn_last'], unique=False)
    op.create_index('ix_rpsl_objects_ip_first_ip_last', 'rpsl_objects', ['ip_first', 'ip_last'], unique=False)
    op.create_index('ix_rpsl_objects_ip_last_ip_first', 'rpsl_objects', ['ip_last', 'ip_first'], unique=False)

    # Manually added
    op.create_index(op.f('ix_rpsl_objects_parsed_data_admin_c'), 'rpsl_objects',
                    [sa.text("((parsed_data->'admin-c'))")],
                    unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_rpsl_objects_parsed_data_tech_c'), 'rpsl_objects', [sa.text("((parsed_data->'tech-c'))")],
                    unique=False, postgresql_using='gin')
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
                    [sa.text("((parsed_data->'mp-members'))")], unique=False,
                    postgresql_using='gin')
    op.create_index(op.f('ix_rpsl_objects_parsed_data_origin'), 'rpsl_objects', [sa.text("((parsed_data->'origin'))")],
                    unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_rpsl_objects_parsed_data_mbrs_by_ref'), 'rpsl_objects',
                    [sa.text("((parsed_data->'mbrs-by-ref'))")],
                    unique=False, postgresql_using='gin')


def downgrade():
    # Manually added
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_mbrs_by_ref'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_ip_first'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_ip_last'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_zone_c'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_role'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_members'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_person'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_mnt_by'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_member_of'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_parsed_data_mp_members'), table_name='rpsl_objects')

    # Autogenerated
    op.drop_index('ix_rpsl_objects_ip_last_ip_first', table_name='rpsl_objects')
    op.drop_index('ix_rpsl_objects_ip_first_ip_last', table_name='rpsl_objects')
    op.drop_index('ix_rpsl_objects_asn_first_asn_last', table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_source'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_rpsl_pk'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_object_class'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_ip_version'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_asn_last'), table_name='rpsl_objects')
    op.drop_index(op.f('ix_rpsl_objects_asn_first'), table_name='rpsl_objects')
    op.drop_table('rpsl_objects')

    op.drop_index(op.f('ix_rpsl_database_journal_source'), table_name='rpsl_database_journal')
    op.drop_index(op.f('ix_rpsl_database_journal_serial_nrtm'), table_name='rpsl_database_journal')
    op.drop_index(op.f('ix_rpsl_database_journal_rpsl_pk'), table_name='rpsl_database_journal')
    op.drop_index(op.f('ix_rpsl_database_journal_object_class'), table_name='rpsl_database_journal')
    op.drop_table('rpsl_database_journal')

    op.drop_index(op.f('ix_database_status_source'), table_name='database_status')
    op.drop_table('database_status')
