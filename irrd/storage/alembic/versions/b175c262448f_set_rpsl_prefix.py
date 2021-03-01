"""set_rpsl_prefix

Revision ID: b175c262448f
Revises: f4c837d8258c
Create Date: 2021-03-01 15:40:03.546705

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b175c262448f'
down_revision = 'f4c837d8258c'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute("update rpsl_objects set prefix=(host(ip_first) || '/' || prefix_length)::cidr where object_class in ('route', 'route6', 'inet6num');")


def downgrade():
    pass
