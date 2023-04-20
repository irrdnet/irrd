"""add_internal_auth

Revision ID: 5bbbc2989aa6
Revises: fd4473bc1a10
Create Date: 2023-04-25 20:31:13.641738

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "5bbbc2989aa6"
down_revision = "fd4473bc1a10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_user",
        sa.Column(
            "pk", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("password", sa.String(), nullable=False),
        sa.Column("totp_secret", sa.String(), nullable=True),
        sa.Column("totp_last_used", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("override", sa.Boolean(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("pk"),
    )
    op.create_index(op.f("ix_auth_user_email"), "auth_user", ["email"], unique=True)
    op.create_table(
        "auth_mntner",
        sa.Column(
            "pk", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("rpsl_mntner_pk", sa.String(), nullable=False),
        sa.Column("rpsl_mntner_obj_id", postgresql.UUID(), nullable=False),
        sa.Column("rpsl_mntner_source", sa.String(), nullable=False),
        sa.Column("migration_token", sa.String(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["rpsl_mntner_obj_id"], ["rpsl_objects.pk"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint(
            "rpsl_mntner_obj_id", "rpsl_mntner_source", name="auth_mntner_rpsl_mntner_obj_id_source_unique"
        ),
    )
    op.create_index(
        op.f("ix_auth_mntner_rpsl_mntner_obj_id"), "auth_mntner", ["rpsl_mntner_obj_id"], unique=True
    )
    op.create_index(op.f("ix_auth_mntner_rpsl_mntner_pk"), "auth_mntner", ["rpsl_mntner_pk"], unique=False)
    op.create_index(
        op.f("ix_auth_mntner_rpsl_mntner_source"), "auth_mntner", ["rpsl_mntner_source"], unique=False
    )
    op.create_table(
        "auth_webauthn",
        sa.Column(
            "pk", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("user_id", postgresql.UUID(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False),
        sa.Column("credential_public_key", sa.LargeBinary(), nullable=False),
        sa.Column("credential_sign_count", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth_user.pk"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("pk"),
    )
    op.create_index(op.f("ix_auth_webauthn_user_id"), "auth_webauthn", ["user_id"], unique=False)
    op.create_table(
        "auth_permission",
        sa.Column(
            "pk", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("user_id", postgresql.UUID(), nullable=True),
        sa.Column("mntner_id", postgresql.UUID(), nullable=True),
        sa.Column("user_management", sa.Boolean(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["mntner_id"], ["auth_mntner.pk"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["auth_user.pk"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("user_id", "mntner_id", name="auth_permission_user_mntner_unique"),
    )
    op.create_index(op.f("ix_auth_permission_mntner_id"), "auth_permission", ["mntner_id"], unique=False)
    op.create_index(op.f("ix_auth_permission_user_id"), "auth_permission", ["user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_auth_permission_user_id"), table_name="auth_permission")
    op.drop_index(op.f("ix_auth_permission_mntner_id"), table_name="auth_permission")
    op.drop_table("auth_permission")
    op.drop_index(op.f("ix_auth_webauthn_user_id"), table_name="auth_webauthn")
    op.drop_table("auth_webauthn")
    op.drop_index(op.f("ix_auth_mntner_rpsl_mntner_source"), table_name="auth_mntner")
    op.drop_index(op.f("ix_auth_mntner_rpsl_mntner_pk"), table_name="auth_mntner")
    op.drop_index(op.f("ix_auth_mntner_rpsl_mntner_obj_id"), table_name="auth_mntner")
    op.drop_table("auth_mntner")
    op.drop_index(op.f("ix_auth_user_email"), table_name="auth_user")
    op.drop_table("auth_user")
    # ### end Alembic commands ###
