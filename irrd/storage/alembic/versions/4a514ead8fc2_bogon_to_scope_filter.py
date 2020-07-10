"""bogon_to_scopefilter

Revision ID: 4a514ead8fc2
Revises: 39e4f15ed80c
Create Date: 2020-07-09 20:11:45.873381

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import ProgrammingError

revision = '4a514ead8fc2'
down_revision = '39e4f15ed80c'
branch_labels = None
depends_on = None


def upgrade():
    scopefilter_status = sa.Enum('in_scope', 'out_scope_as', 'out_scope_prefix', name='scopefilterstatus')
    scopefilter_status.create(op.get_bind())

    op.add_column('rpsl_objects', sa.Column('scopefilter_status', sa.Enum('in_scope', 'out_scope_as', 'out_scope_prefix', name='scopefilterstatus'), server_default='in_scope', nullable=False))
    op.create_index(op.f('ix_rpsl_objects_scopefilter_status'), 'rpsl_objects', ['scopefilter_status'], unique=False)

    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = inspector.get_columns('rpsl_objects')

    # This is a somewhat strange migration: the bogon_status column may or may
    # not exist, depending on which version of 39e4f15ed80c people have run.
    # If it does exist, it is deleted.
    # This is also why downgrade() does not recreate this column.
    if 'bogon_status' in columns:
        op.drop_index('ix_rpsl_objects_bogon_status', table_name='rpsl_objects')
        op.drop_column('rpsl_objects', 'bogon_status')
        bogon_status = sa.Enum('unknown', 'not_bogon', 'bogon_as', 'bogon_prefix', name='bogonstatus')
        bogon_status.drop(op.get_bind())

    # downgrade() can't remove this entry from the enum, so if this migration
    # is reverted and then re-applied, altering the enum will fail
    with op.get_context().autocommit_block():
        try:
            op.execute("ALTER TYPE journalentryorigin ADD VALUE 'scope_filter'")
        except ProgrammingError as pe:
            if 'DuplicateObject' not in str(pe):
                raise pe


def downgrade():
    op.drop_index(op.f('ix_rpsl_objects_scopefilter_status'), table_name='rpsl_objects')
    op.drop_column('rpsl_objects', 'scopefilter_status')

    scopefilter_status = sa.Enum('in_scope', 'out_scope_as', 'out_scope_prefix', name='scopefilterstatus')
    scopefilter_status.drop(op.get_bind())
