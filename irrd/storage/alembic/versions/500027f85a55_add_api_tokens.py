"""add_api_tokens

Revision ID: 500027f85a55
Revises: 5bbbc2989aa6
Create Date: 2023-05-05 13:21:43.915949

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "500027f85a55"
down_revision = "5bbbc2989aa6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_api_token",
        sa.Column(
            "pk", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "token", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=True
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("creator_id", postgresql.UUID(), nullable=True),
        sa.Column("mntner_id", postgresql.UUID(), nullable=True),
        sa.Column("ip_restriction", sa.String(), nullable=True),
        sa.Column("enabled_webapi", sa.Boolean(), nullable=False),
        sa.Column("enabled_email", sa.Boolean(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["auth_user.pk"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["mntner_id"], ["auth_mntner.pk"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("pk"),
    )
    op.create_index(op.f("ix_auth_api_token_creator_id"), "auth_api_token", ["creator_id"], unique=False)
    op.create_index(op.f("ix_auth_api_token_mntner_id"), "auth_api_token", ["mntner_id"], unique=False)
    op.create_index(op.f("ix_auth_api_token_token"), "auth_api_token", ["token"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_auth_api_token_token"), table_name="auth_api_token")
    op.drop_index(op.f("ix_auth_api_token_mntner_id"), table_name="auth_api_token")
    op.drop_index(op.f("ix_auth_api_token_creator_id"), table_name="auth_api_token")
    op.drop_table("auth_api_token")
