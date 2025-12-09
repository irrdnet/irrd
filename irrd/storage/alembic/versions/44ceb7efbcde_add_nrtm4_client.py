"""add-nrtm4-client

Revision ID: 44ceb7efbcde
Revises: 2353e60e63f8
Create Date: 2023-08-23 20:16:36.038631

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "44ceb7efbcde"
down_revision = "2353e60e63f8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "database_status", sa.Column("nrtm4_client_session_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("database_status", sa.Column("nrtm4_client_version", sa.Integer(), nullable=True))
    op.add_column("database_status", sa.Column("nrtm4_client_current_key", sa.Text(), nullable=True))
    op.add_column("database_status", sa.Column("nrtm4_client_next_key", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("database_status", "nrtm4_client_next_key")
    op.drop_column("database_status", "nrtm4_client_current_key")
    op.drop_column("database_status", "nrtm4_client_version")
    op.drop_column("database_status", "nrtm4_client_session_id")
