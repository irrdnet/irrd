"""Add nrtm_client_previous_file_hashes field to database_status

Revision ID: e1e649b5f8bb
Revises: a635d2217a48
Create Date: 2024-11-08 17:39:40.872329

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e1e649b5f8bb"
down_revision = "a635d2217a48"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "database_status",
        sa.Column(
            "nrtm4_client_previous_file_hashes", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade():
    op.drop_column("database_status", "nrtm4_client_previous_file_hashes")
