"""add_journal_serial

Revision ID: 8b8357acd333
Revises: 0548f1aa4f10
Create Date: 2022-10-07 13:43:46.598866

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8b8357acd333'
down_revision = '0548f1aa4f10'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy.schema import Sequence, CreateSequence
    op.execute(CreateSequence(Sequence('rpsl_database_journal_serial_global_seq')))
    op.add_column('rpsl_database_journal', sa.Column('serial_global', sa.BigInteger(), nullable=True))

    op.execute("""UPDATE rpsl_database_journal SET
        serial_global = rpsl_database_journal_new.serial_global_new
        FROM rpsl_database_journal AS rpsl_database_journal_old
        LEFT JOIN (
            SELECT *, nextval('rpsl_database_journal_serial_global_seq') AS serial_global_new
            FROM rpsl_database_journal
            ORDER BY timestamp,source, serial_nrtm
        ) AS rpsl_database_journal_new USING (pk)
        WHERE rpsl_database_journal.pk = rpsl_database_journal_old.pk
    """)

    op.alter_column('rpsl_database_journal', 'serial_global', server_default=sa.text("nextval('rpsl_database_journal_serial_global_seq')"), nullable=False)
    op.create_index(op.f('ix_rpsl_database_journal_serial_global'), 'rpsl_database_journal', ['serial_global'], unique=True)


def downgrade():
    from sqlalchemy.schema import Sequence, DropSequence
    op.drop_index(op.f('ix_rpsl_database_journal_serial_global'), table_name='rpsl_database_journal')
    op.drop_column('rpsl_database_journal', 'serial_global')
    op.execute(DropSequence(Sequence('rpsl_database_journal_serial_global_seq')))
