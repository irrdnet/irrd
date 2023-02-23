"""add_rpsl_objects_suspended

Revision ID: 0548f1aa4f10
Revises: 8744b4b906bb
Create Date: 2021-12-02 14:34:10.566178

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import ProgrammingError

# revision identifiers, used by Alembic.
revision = "0548f1aa4f10"
down_revision = "8744b4b906bb"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rpsl_objects_suspended",
        sa.Column(
            "pk", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("rpsl_pk", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("object_class", sa.String(), nullable=False),
        sa.Column("object_text", sa.Text(), nullable=False),
        sa.Column("mntners", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "original_created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "original_updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("pk"),
    )
    op.create_index(
        op.f("ix_rpsl_objects_suspended_mntners"), "rpsl_objects_suspended", ["mntners"], unique=False
    )
    op.create_index(
        op.f("ix_rpsl_objects_suspended_object_class"),
        "rpsl_objects_suspended",
        ["object_class"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rpsl_objects_suspended_rpsl_pk"), "rpsl_objects_suspended", ["rpsl_pk"], unique=False
    )
    op.create_index(
        op.f("ix_rpsl_objects_suspended_source"), "rpsl_objects_suspended", ["source"], unique=False
    )

    # downgrade() can't remove this entry from the enum, so if this migration
    # is reverted and then re-applied, altering the enum will fail
    with op.get_context().autocommit_block():
        try:
            op.execute("ALTER TYPE journalentryorigin ADD VALUE 'suspension'")
        except ProgrammingError as pe:
            if "DuplicateObject" not in str(pe):
                raise pe


def downgrade():
    op.drop_index(op.f("ix_rpsl_objects_suspended_source"), table_name="rpsl_objects_suspended")
    op.drop_index(op.f("ix_rpsl_objects_suspended_rpsl_pk"), table_name="rpsl_objects_suspended")
    op.drop_index(op.f("ix_rpsl_objects_suspended_object_class"), table_name="rpsl_objects_suspended")
    op.drop_index(op.f("ix_rpsl_objects_suspended_mntners"), table_name="rpsl_objects_suspended")
    op.drop_table("rpsl_objects_suspended")
