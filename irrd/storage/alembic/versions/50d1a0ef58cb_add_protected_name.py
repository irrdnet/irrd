"""add_protected_name

Revision ID: 50d1a0ef58cb
Revises: 5d942647566e
Create Date: 2023-07-17 20:24:35.527045

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "50d1a0ef58cb"
down_revision = "5d942647566e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "protected_rpsl_name",
        sa.Column(
            "pk", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("rpsl_pk", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("object_class", sa.String(), nullable=False),
        sa.Column("protected_name", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("pk"),
    )
    op.create_index(
        op.f("ix_protected_rpsl_name_object_class"), "protected_rpsl_name", ["object_class"], unique=False
    )
    op.create_index(
        op.f("ix_protected_rpsl_name_protected_name"),
        "protected_rpsl_name",
        ["protected_name"],
        unique=False,
    )
    op.create_index(op.f("ix_protected_rpsl_name_rpsl_pk"), "protected_rpsl_name", ["rpsl_pk"], unique=False)
    op.create_index(op.f("ix_protected_rpsl_name_source"), "protected_rpsl_name", ["source"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_protected_rpsl_name_source"), table_name="protected_rpsl_name")
    op.drop_index(op.f("ix_protected_rpsl_name_rpsl_pk"), table_name="protected_rpsl_name")
    op.drop_index(op.f("ix_protected_rpsl_name_protected_name"), table_name="protected_rpsl_name")
    op.drop_index(op.f("ix_protected_rpsl_name_object_class"), table_name="protected_rpsl_name")
    op.drop_table("protected_rpsl_name")
