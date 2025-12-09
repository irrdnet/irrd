"""add_nrtm4_server

Revision ID: b7b3c367f9ba
Revises: 44ceb7efbcde
Create Date: 2024-01-09 16:42:46.992091

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b7b3c367f9ba"
down_revision = "44ceb7efbcde"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "database_status", sa.Column("nrtm4_server_session_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("database_status", sa.Column("nrtm4_server_version", sa.Integer(), nullable=True))
    op.add_column(
        "database_status",
        sa.Column(
            "nrtm4_server_last_update_notification_file_update", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "database_status", sa.Column("nrtm4_server_last_snapshot_version", sa.Integer(), nullable=True)
    )
    op.add_column(
        "database_status", sa.Column("nrtm4_server_last_snapshot_global_serial", sa.Integer(), nullable=True)
    )
    op.add_column(
        "database_status",
        sa.Column("nrtm4_server_last_snapshot_timestamp", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "database_status", sa.Column("nrtm4_server_last_snapshot_filename", sa.Text(), nullable=True)
    )
    op.add_column("database_status", sa.Column("nrtm4_server_last_snapshot_hash", sa.Text(), nullable=True))
    op.add_column(
        "database_status",
        sa.Column("nrtm4_server_previous_deltas", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade():
    op.drop_column("database_status", "nrtm4_server_previous_deltas")
    op.drop_column("database_status", "nrtm4_server_last_snapshot_hash")
    op.drop_column("database_status", "nrtm4_server_last_snapshot_filename")
    op.drop_column("database_status", "nrtm4_server_last_snapshot_timestamp")
    op.drop_column("database_status", "nrtm4_server_last_snapshot_global_serial")
    op.drop_column("database_status", "nrtm4_server_last_snapshot_version")
    op.drop_column("database_status", "nrtm4_server_last_update_notification_file_update")
    op.drop_column("database_status", "nrtm4_server_version")
    op.drop_column("database_status", "nrtm4_server_session_id")
