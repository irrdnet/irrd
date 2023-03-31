"""add_global_serial

Revision ID: 8b8357acd333
Revises: 0548f1aa4f10
Create Date: 2022-10-07 13:43:46.598866

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8b8357acd333"
down_revision = "0548f1aa4f10"
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy.schema import CreateSequence, Sequence

    op.execute(CreateSequence(Sequence("rpsl_database_journal_serial_global_seq", start=1000000)))
    op.add_column("rpsl_database_journal", sa.Column("serial_global", sa.BigInteger(), nullable=True))

    op.execute(
        """
    UPDATE rpsl_database_journal SET
        serial_global = rpsl_database_journal_new.serial_global_new
        FROM rpsl_database_journal AS rpsl_database_journal_old
        RIGHT JOIN (
            SELECT *, nextval('rpsl_database_journal_serial_global_seq') AS serial_global_new
            FROM rpsl_database_journal
            WHERE timestamp IN (
                SELECT MAX(timestamp)
                FROM rpsl_database_journal
                GROUP BY source
            ) ORDER BY timestamp
        ) AS rpsl_database_journal_new USING (pk)
        WHERE rpsl_database_journal.pk = rpsl_database_journal_old.pk
    """
    )

    op.alter_column(
        "rpsl_database_journal",
        "serial_global",
        server_default=sa.text("nextval('rpsl_database_journal_serial_global_seq')"),
    )
    op.create_index(
        op.f("ix_rpsl_database_journal_serial_global"),
        "rpsl_database_journal",
        ["serial_global"],
        unique=True,
    )
    op.create_index(
        op.f("ix_rpsl_database_journal_timestamp"), "rpsl_database_journal", ["timestamp"], unique=False
    )


def downgrade():
    from sqlalchemy.schema import DropSequence, Sequence

    op.drop_index(op.f("ix_rpsl_database_journal_timestamp"), table_name="rpsl_database_journal")
    op.drop_index(op.f("ix_rpsl_database_journal_serial_global"), table_name="rpsl_database_journal")
    op.drop_column("rpsl_database_journal", "serial_global")
    op.execute(DropSequence(Sequence("rpsl_database_journal_serial_global_seq")))
