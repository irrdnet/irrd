import enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.declarative import declarative_base, declared_attr

from irrd.rpsl.rpsl_objects import lookup_field_names


class DatabaseOperation(enum.Enum):
    add_or_update = 'ADD'
    delete = 'DEL'


Base = declarative_base()


class RPSLDatabaseObject(Base):  # type: ignore
    """
    SQLAlchemy ORM object for RPSL database objects.

    Note that SQLAlchemy does not require you to use the ORM for ORM
    objects - as that can be slower with large queries.
    """
    __tablename__ = 'rpsl_objects'

    # Requires extension pgcrypto
    # in alembic: op.execute('create EXTENSION if not EXISTS 'pgcrypto';')
    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True)
    rpsl_pk = sa.Column(sa.String, index=True, nullable=False)
    source = sa.Column(sa.String, index=True, nullable=False)

    object_class = sa.Column(sa.String, nullable=False, index=True)
    parsed_data = sa.Column(pg.JSONB, nullable=False)
    object_text = sa.Column(sa.Text, nullable=False)

    ip_version = sa.Column(sa.Integer, index=True)
    ip_first = sa.Column(pg.INET, index=True)
    ip_last = sa.Column(pg.INET, index=True)
    ip_size = sa.Column(sa.DECIMAL(scale=0))
    asn_first = sa.Column(sa.BigInteger, index=True)
    asn_last = sa.Column(sa.BigInteger, index=True)

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    @declared_attr
    def __table_args__(cls):  # noqa
        args = [
            sa.UniqueConstraint('rpsl_pk', 'source', name='rpsl_objects_rpsl_pk_source_unique'),
            sa.Index('ix_rpsl_objects_ip_first_ip_last', 'ip_first', 'ip_last', ),
            sa.Index('ix_rpsl_objects_ip_last_ip_first', 'ip_last', 'ip_first'),
            sa.Index('ix_rpsl_objects_asn_first_asn_last', 'asn_first', 'asn_last'),
        ]
        for name in lookup_field_names():
            index_name = 'ix_rpsl_objects_parsed_data_' + name.replace('-', '_')
            index_on = sa.text(f"(parsed_data->'{name}')")
            args.append(sa.Index(index_name, index_on, postgresql_using='gin'))
        return tuple(args)

    def __repr__(self):
        return f'<{self.rpsl_pk}/{self.source}/{self.pk}>'


class RPSLDatabaseJournal(Base):  # type: ignore
    """
    SQLAlchemy ORM object for change history of RPSL database objects.
    """
    __tablename__ = 'rpsl_database_journal'

    # Requires extension pgcrypto
    # in alembic: op.execute('create EXTENSION if not EXISTS 'pgcrypto';')
    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True)
    rpsl_pk = sa.Column(sa.String, index=True, nullable=False)
    source = sa.Column(sa.String, index=True, nullable=False)

    serial_nrtm = sa.Column(sa.Integer, index=True, nullable=False)
    operation = sa.Column(sa.Enum(DatabaseOperation), nullable=False)

    object_class = sa.Column(sa.String, nullable=False, index=True)
    object_text = sa.Column(sa.Text, nullable=False)

    # These objects are not mutable, so creation time is sufficient.
    timestamp = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    @declared_attr
    def __table_args__(cls):  # noqa
        return (
            sa.UniqueConstraint('serial_nrtm', 'source', name='rpsl_objects_history_serial_nrtm_source_unique'),
        )

    def __repr__(self):
        return f'<{self.source}/{self.serial}/{self.operation}/{self.rpsl_pk}>'


class RPSLDatabaseStatus(Base):  # type: ignore
    """
    SQLAlchemy ORM object for the status of authoritative and mirrored DBs.

    Note that this database is for keeping status, and is not the source
    of configuration parameters.
    """
    __tablename__ = 'database_status'

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True)
    source = sa.Column(sa.String, index=True, nullable=False, unique=True)

    serial_oldest_seen = sa.Column(sa.Integer)
    serial_newest_seen = sa.Column(sa.Integer)
    serial_oldest_journal = sa.Column(sa.Integer)
    serial_newest_journal = sa.Column(sa.Integer)
    serial_last_export = sa.Column(sa.Integer)

    force_reload = sa.Column(sa.Boolean(), default=False, nullable=False)

    last_error = sa.Column(sa.Text)
    last_error_timestamp = sa.Column(sa.DateTime(timezone=True))

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    def __repr__(self):
        return self.source


# Before you update this, please check the storage documentation for changing lookup fields.
expected_lookup_field_names = {
    'admin-c', 'tech-c', 'zone-c', 'member-of', 'mnt-by', 'role', 'members', 'person',
    'mp-members', 'origin', 'mbrs-by-ref',
}
if sorted(lookup_field_names()) != sorted(expected_lookup_field_names):  # pragma: no cover
    raise RuntimeError(f'Field names of lookup fields do not match expected set. Indexes may be missing. '
                       f'Expected: {expected_lookup_field_names}, actual: {lookup_field_names()}')
