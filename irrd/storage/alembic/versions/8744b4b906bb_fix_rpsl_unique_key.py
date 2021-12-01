"""fix_rpsl_unique_key

https://github.com/irrdnet/irrd/issues/560
runtime of this migration on full database in order of a few minutes

Revision ID: 8744b4b906bb
Revises: 893d0d5363b3
Create Date: 2021-11-30 19:46:01.195353

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '8744b4b906bb'
down_revision = '893d0d5363b3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        constraint_name='rpsl_objects_rpsl_pk_source_class_unique',
        table_name='rpsl_objects',
        columns=['rpsl_pk', 'source', 'object_class'],
    )
    op.drop_constraint(
        constraint_name='rpsl_objects_rpsl_pk_source_unique',
        table_name='rpsl_objects',
    )


def downgrade():
    op.create_unique_constraint(
        name='rpsl_objects_rpsl_pk_source_unique',
        table_name='rpsl_objects',
        columns=['rpsl_pk', 'source'],
    )
    op.drop_constraint(
        constraint_name='rpsl_objects_rpsl_pk_source_class_unique',
        table_name='rpsl_objects',
    )
