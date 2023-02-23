"""add_route_preference_status

Revision ID: fd4473bc1a10
Revises: 8b8357acd333
Create Date: 2022-12-24 16:25:59.648631

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import ProgrammingError

# revision identifiers, used by Alembic.
revision = "fd4473bc1a10"
down_revision = "8b8357acd333"
branch_labels = None
depends_on = None


def upgrade():
    route_preference_status = sa.Enum("visible", "suppressed", name="routepreferencestatus")
    route_preference_status.create(op.get_bind())

    op.add_column(
        "rpsl_objects",
        sa.Column(
            "route_preference_status",
            sa.Enum("visible", "suppressed", name="routepreferencestatus"),
            server_default="visible",
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_rpsl_objects_route_preference_status"),
        "rpsl_objects",
        ["route_preference_status"],
        unique=False,
    )

    # downgrade() can't remove this entry from the enum, so if this migration
    # is reverted and then re-applied, altering the enum will fail
    with op.get_context().autocommit_block():
        try:
            op.execute("ALTER TYPE journalentryorigin ADD VALUE 'route_preference'")
        except ProgrammingError as pe:
            if "DuplicateObject" not in str(pe):
                raise pe


def downgrade():
    op.drop_index(op.f("ix_rpsl_objects_route_preference_status"), table_name="rpsl_objects")
    op.drop_column("rpsl_objects", "route_preference_status")

    route_preference_status = sa.Enum("visible", "suppressed", name="routepreferencestatus")
    route_preference_status.drop(op.get_bind())
