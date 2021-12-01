import enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.declarative import declarative_base, declared_attr

from irrd.rpki.status import RPKIStatus
from irrd.rpsl.rpsl_objects import lookup_field_names
from irrd.scopefilter.status import ScopeFilterStatus


class DatabaseOperation(enum.Enum):
    add_or_update = 'ADD'
    delete = 'DEL'


class JournalEntryOrigin(enum.Enum):
    # Legacy journal entries for which the origin is unknown, can be auth_change or mirror
    unknown = 'UNKNOWN'
    # Journal entry received from a mirror by NRTM or importing from a file
    mirror = 'MIRROR'
    # Journal entry generated from synthesized NRTM
    synthetic_nrtm = 'SYNTHETIC_NRTM'
    # Journal entry generated from pseudo IRR
    pseudo_irr = 'PSEUDO_IRR'
    # Journal entry caused by a user-submitted change in an authoritative database
    auth_change = 'AUTH_CHANGE'
    # Journal entry caused by a change in in the RPKI status of an object in an authoritative db
    rpki_status = 'RPKI_STATUS'
    # Journal entry caused by a change in the scope filter status
    scope_filter = 'SCOPE_FILTER'


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
    # Only filled for route/route6
    prefix_length = sa.Column(sa.Integer, nullable=True)
    prefix = sa.Column(pg.CIDR, nullable=True)

    asn_first = sa.Column(sa.BigInteger, index=True)
    asn_last = sa.Column(sa.BigInteger, index=True)

    rpki_status = sa.Column(sa.Enum(RPKIStatus), nullable=False, index=True, server_default=RPKIStatus.not_found.name)
    scopefilter_status = sa.Column(sa.Enum(ScopeFilterStatus), nullable=False, index=True, server_default=ScopeFilterStatus.in_scope.name)

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    @declared_attr
    def __table_args__(cls):  # noqa
        args = [
            sa.UniqueConstraint('rpsl_pk', 'source', 'object_class', name='rpsl_objects_rpsl_pk_source_class_unique'),
            sa.Index('ix_rpsl_objects_ip_first_ip_last', 'ip_first', 'ip_last', ),
            sa.Index('ix_rpsl_objects_ip_last_ip_first', 'ip_last', 'ip_first'),
            sa.Index('ix_rpsl_objects_asn_first_asn_last', 'asn_first', 'asn_last'),
            sa.Index('ix_rpsl_objects_prefix_gist', sa.text('prefix inet_ops'),
                     postgresql_using='gist')
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
    origin = sa.Column(sa.Enum(JournalEntryOrigin), nullable=False, index=True, server_default=JournalEntryOrigin.unknown.name)

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

    # The oldest and newest serials seen, for any reason since the last import
    serial_oldest_seen = sa.Column(sa.Integer)
    serial_newest_seen = sa.Column(sa.Integer)
    # The oldest and newest serials in the current local journal
    serial_oldest_journal = sa.Column(sa.Integer)
    serial_newest_journal = sa.Column(sa.Integer)
    # The serial at which this IRRd last exported
    serial_last_export = sa.Column(sa.Integer)
    # The last serial seen from an NRTM mirror, i.e. resume NRTM query from this serial
    serial_newest_mirror = sa.Column(sa.Integer)

    force_reload = sa.Column(sa.Boolean(), default=False, nullable=False)
    synchronised_serials = sa.Column(sa.Boolean(), default=True, nullable=False)

    last_error = sa.Column(sa.Text)
    last_error_timestamp = sa.Column(sa.DateTime(timezone=True))

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    def __repr__(self):
        return self.source


class ROADatabaseObject(Base):  # type: ignore
    """
    SQLAlchemy ORM object for ROA objects.
    """
    __tablename__ = 'roa_object'

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True)

    prefix = sa.Column(pg.CIDR, nullable=False)
    asn = sa.Column(sa.BigInteger, nullable=False)
    max_length = sa.Column(sa.Integer, nullable=False)
    trust_anchor = sa.Column(sa.String)
    ip_version = sa.Column(sa.Integer, nullable=False, index=True)

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    @declared_attr
    def __table_args__(cls):  # noqa
        args = [
            sa.UniqueConstraint('prefix', 'asn', 'max_length', 'trust_anchor', name='roa_object_prefix_asn_maxlength_unique'),
            sa.Index('ix_roa_objects_prefix_gist', sa.text('prefix inet_ops'), postgresql_using='gist')
        ]
        return tuple(args)

    def __repr__(self):
        return f'<{self.prefix}/{self.asn}>'


# Before you update this, please check the storage documentation for changing lookup fields.
expected_lookup_field_names = {
    'admin-c', 'tech-c', 'zone-c', 'member-of', 'mnt-by', 'role', 'members', 'person',
    'mp-members', 'origin', 'mbrs-by-ref',
}
if sorted(lookup_field_names()) != sorted(expected_lookup_field_names):  # pragma: no cover
    raise RuntimeError(f'Field names of lookup fields do not match expected set. Indexes may be missing. '
                       f'Expected: {expected_lookup_field_names}, actual: {lookup_field_names()}')
