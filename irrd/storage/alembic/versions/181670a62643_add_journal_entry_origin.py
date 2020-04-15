"""Add journal entry origin

Revision ID: 181670a62643
Revises: a8609af97aa3
Create Date: 2020-04-15 10:19:09.146000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '181670a62643'
down_revision = 'a8609af97aa3'
branch_labels = None
depends_on = None


def upgrade():
    rpki_status = sa.Enum('unknown', 'mirror', 'synthetic_nrtm', 'pseudo_irr', 'auth_change', 'rpki_status', 'bogon_status', name='journalentryorigin')
    rpki_status.create(op.get_bind())

    op.add_column('rpsl_database_journal', sa.Column('origin', sa.Enum('unknown', 'mirror', 'synthetic_nrtm', 'auth_change', 'pseudo_irr', 'rpki_status', 'bogon_status', name='journalentryorigin'), server_default='unknown', nullable=False))
    op.create_index(op.f('ix_rpsl_database_journal_origin'), 'rpsl_database_journal', ['origin'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_rpsl_database_journal_origin'), table_name='rpsl_database_journal')
    op.drop_column('rpsl_database_journal', 'origin')

    rpki_status = sa.Enum('unknown', 'mirror', 'synthetic_nrtm', 'auth_change', 'pseudo_irr', 'rpki_status', 'bogon_status', name='journalentryorigin')
    rpki_status.drop(op.get_bind())
