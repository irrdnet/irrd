"""add_change_log

Revision ID: 05b41bcc8b6b
Revises: 500027f85a55
Create Date: 2023-06-13 15:36:21.889426

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "05b41bcc8b6b"
down_revision = "500027f85a55"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "change_log",
        sa.Column(
            "pk", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("auth_by_user_id", postgresql.UUID(), nullable=True),
        sa.Column("auth_by_user_email", sa.String(), nullable=True),
        sa.Column("auth_by_api_key_id", postgresql.UUID(), nullable=True),
        sa.Column("auth_by_api_key_id_fixed", postgresql.UUID(), nullable=True),
        sa.Column("auth_through_mntner_id", postgresql.UUID(), nullable=True),
        sa.Column("auth_through_rpsl_mntner_pk", sa.String(), nullable=True),
        sa.Column("auth_by_rpsl_mntner_password", sa.Boolean(), nullable=True),
        sa.Column("auth_by_rpsl_mntner_pgp_key", sa.String(), nullable=True),
        sa.Column("auth_by_override", sa.Boolean(), nullable=True),
        sa.Column("from_email", sa.String(), nullable=True),
        sa.Column("from_ip", postgresql.INET(), nullable=True),
        # sa.Column("journal_entry", postgresql.UUID(), nullable=True),
        # sa.Column("journal_serial_nrtm", sa.Integer(), nullable=True),
        sa.Column("auth_change_descr", sa.String(), nullable=True),
        sa.Column("auth_affected_user", postgresql.UUID(), nullable=True),
        sa.Column("auth_affected_mntner", postgresql.UUID(), nullable=True),
        sa.Column(
            "rpsl_target_operation",
            sa.Enum("add_or_update", "delete", name="databaseoperation"),
            nullable=True,
        ),
        sa.Column("rpsl_target_obj_id", postgresql.UUID(), nullable=True),
        sa.Column("rpsl_target_pk", sa.String(), nullable=True),
        sa.Column("rpsl_target_source", sa.String(), nullable=True),
        sa.Column("rpsl_target_object_class", sa.String(), nullable=True),
        sa.Column("rpsl_target_object_text", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["auth_affected_mntner"], ["auth_mntner.pk"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["auth_affected_user"], ["auth_user.pk"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["auth_by_api_key_id"], ["auth_api_token.pk"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["auth_by_user_id"], ["auth_user.pk"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["auth_through_mntner_id"], ["auth_mntner.pk"], ondelete="SET NULL"),
        # sa.ForeignKeyConstraint(["journal_entry"], ["rpsl_database_journal.pk"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rpsl_target_obj_id"], ["rpsl_objects.pk"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("pk"),
    )
    op.create_index(
        op.f("ix_change_log_auth_affected_mntner"), "change_log", ["auth_affected_mntner"], unique=False
    )
    op.create_index(
        op.f("ix_change_log_auth_through_mntner_id"), "change_log", ["auth_through_mntner_id"], unique=False
    )
    op.create_index(op.f("ix_change_log_rpsl_target_pk"), "change_log", ["rpsl_target_pk"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_change_log_rpsl_target_pk"), table_name="change_log")
    op.drop_index(op.f("ix_change_log_auth_through_mntner_id"), table_name="change_log")
    op.drop_index(op.f("ix_change_log_auth_affected_mntner"), table_name="change_log")
    op.drop_table("change_log")
