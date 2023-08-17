"""add_setting

Revision ID: 2353e60e63f8
Revises: 50d1a0ef58cb
Create Date: 2023-08-17 11:40:56.122469

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2353e60e63f8"
down_revision = "50d1a0ef58cb"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "setting",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )


def downgrade():
    op.drop_table("setting")
