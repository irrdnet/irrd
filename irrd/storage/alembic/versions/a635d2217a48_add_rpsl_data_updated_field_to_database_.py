"""Add rpsl_data_updated field to database_status

Revision ID: a635d2217a48
Revises: b7b3c367f9ba
Create Date: 2024-11-08 16:11:21.101990

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a635d2217a48"
down_revision = "b7b3c367f9ba"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "database_status",
        sa.Column(
            "rpsl_data_updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )


def downgrade():
    op.drop_column("database_status", "rpsl_data_updated")
