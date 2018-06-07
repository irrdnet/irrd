from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func, UniqueConstraint, Index, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import sessionmaker

from irrd.rpsl.parser import RPSLObject
from irrd.rpsl.rpsl_objects import lookup_field_names

MAX_RECORDS_CACHE_BEFORE_INSERT = 5000

engine = create_engine('postgresql:///irrd', echo=True)
Base = declarative_base()
Session = sessionmaker()
Session.configure(bind=engine)


class RPSLDatabaseObject(Base):  # type: ignore
    __tablename__ = 'rpsl_objects'

    # TODO: reconsider having a UUID pk
    # Requires extension pgcrypto
    #     op.execute('create EXTENSION if not EXISTS "pgcrypto";')
    # pk = Column(UUID(as_uuid=True), server_default=sqlalchemy.text("gen_random_uuid()"), primary_key=True)
    rpsl_pk = Column(String, index=True, nullable=False, primary_key=True)
    source = Column(String, index=True, nullable=False, primary_key=True)

    object_class = Column(String, nullable=False, index=True)
    parsed_data = Column(JSONB, nullable=False)
    # TODO: how often do we need internal object data? Could just reparse from object_txt
    internal_object_data = Column(JSONB, nullable=False)
    object_txt = Column(Text, nullable=False)

    ip_version = Column(Integer, index=True)
    # TODO: Index for ip_first/ip_last should be gist inet_ops
    ip_first = Column(INET, index=True)
    ip_last = Column(INET, index=True)
    asn_first = Column(Integer, index=True)
    asn_last = Column(Integer, index=True)

    created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # TODO: is updated actually updated when storing objects? probably not
    updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    @declared_attr
    def __table_args__(cls):  # noqa
        args = [
            UniqueConstraint('rpsl_pk', 'source', name='rpsl_pk_source_unique'),
        ]
        for name in lookup_field_names():
            index_name = 'ix_rpsl_objects_parsed_data_' + name.replace('-', '_')
            index_on = text(f"({cls.__tablename__}->'{name}')")
            args.append(Index(index_name, index_on, postgresql_using="gin"))
        return tuple(args)

    def __repr__(self):
        return f"<{self.rpsl_pk}/{self.source}/{self.pk}>"


class RPSLDatabaseObjectWriter:
    # TODO: the database size seems to grow on multiple runs? Shouldn't happen...
    def __init__(self):
        self.records = []
        self._start_transaction()

    def add_object(self, rpsl_object: RPSLObject):
        ip_first = str(rpsl_object.ip_first) if rpsl_object.ip_first else None
        ip_last = str(rpsl_object.ip_last) if rpsl_object.ip_last else None

        # noinspection PyArgumentList
        self.records.append({
            'rpsl_pk': rpsl_object.pk(),
            'source': rpsl_object.parsed_data['source'],
            'object_class': rpsl_object.rpsl_object_class,
            'parsed_data': rpsl_object.parsed_data,
            'internal_object_data': rpsl_object._object_data,
            'object_txt': rpsl_object.render_rpsl_text(),
            'ip_version': rpsl_object.ip_version(),
            'ip_first': ip_first,
            'ip_last': ip_last,
            'asn_first': rpsl_object.asn_first,
            'asn_last': rpsl_object.asn_last,
        })

        if len(self.records) > MAX_RECORDS_CACHE_BEFORE_INSERT:
            self.save()

    def save(self):
        rpsl_composite_key = ['rpsl_pk', 'source']
        stmt = postgresql.insert(RPSLDatabaseObject).values(self.records)
        columns_to_update = {
            c.name: c
            for c in stmt.excluded
            if c.name not in rpsl_composite_key
        }

        update_stmt = stmt.on_conflict_do_update(
            index_elements=rpsl_composite_key,
            set_=columns_to_update,
        )

        try:
            self.connection.execute(update_stmt)
        except Exception:
            self.transaction.rollback()
            raise
        self.records = []

    def commit(self):
        self.save()
        try:
            self.transaction.commit()
        except Exception:
            self.transaction.rollback()
            raise

    def _start_transaction(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()


expected_lookup_field_names = {
    'zone-c', 'member-of', 'mnt-by', 'role', 'members', 'person', 'source', 'mp-members'}
if sorted(lookup_field_names()) != sorted(expected_lookup_field_names):
    raise Exception(f"Field names of lookup fields do not match expected set. Indexes may be missing. "
                    f"Expected: {expected_lookup_field_names}, actual: {lookup_field_names()}")
