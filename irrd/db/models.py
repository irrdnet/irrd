import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.declarative import declarative_base, declared_attr

from irrd.rpsl.rpsl_objects import lookup_field_names

Base = declarative_base()

# TODO: run ANALYZE after large inserts?


class RPSLDatabaseObject(Base):  # type: ignore
    """
    SQLAlchemy ORM object for RPSL database objects.

    Note that SQLAlchemy does not require you to use the ORM for ORM
    objects - as that can be slower with large queries.
    """
    __tablename__ = 'rpsl_objects'

    # Requires extension pgcrypto
    # in alembic: op.execute('create EXTENSION if not EXISTS "pgcrypto";')
    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)
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
            sa.UniqueConstraint('rpsl_pk', 'source', name='rpsl_pk_source_unique'),
        ]
        for name in lookup_field_names():
            index_name = 'ix_rpsl_objects_parsed_data_' + name.replace('-', '_')
            index_on = sa.text(f"(parsed_data->'{name}')")
            args.append(sa.Index(index_name, index_on, postgresql_using="gin"))
        return tuple(args)

    def __repr__(self):
        return f"<{self.rpsl_pk}/{self.source}/{self.pk}>"


# Before you update this, please check the documentation for changing lookup fields.
expected_lookup_field_names = {
    'admin-c', 'tech-c', 'zone-c', 'member-of', 'mnt-by', 'role', 'members', 'person',
    'source', 'mp-members', 'origin', 'mbrs-by-ref',
}
if sorted(lookup_field_names()) != sorted(expected_lookup_field_names):  # pragma: no cover
    raise RuntimeError(f"Field names of lookup fields do not match expected set. Indexes may be missing. "
                       f"Expected: {expected_lookup_field_names}, actual: {lookup_field_names()}")
