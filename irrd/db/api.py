from datetime import datetime

from sqlalchemy.dialects import postgresql as pg

from irrd.db import engine
from irrd.db.models import RPSLDatabaseObject
from irrd.rpsl.parser import RPSLObject

MAX_RECORDS_CACHE_BEFORE_INSERT = 5000


class DatabaseHandler:
    def __init__(self):
        self._start_transaction()
        self.records = []
        self.rpsl_pk_source_seen = set()

    def upsert_object(self, rpsl_object: RPSLObject):
        ip_first = str(rpsl_object.ip_first) if rpsl_object.ip_first else None
        ip_last = str(rpsl_object.ip_last) if rpsl_object.ip_last else None

        # In some cases, multiple updates may be submitted for the same object.
        # PostgreSQL will not allow rows proposed for insertion to have duplicate
        # contstrained values - so if a second object appears with a pk/source
        # seen before, the cache must be flushed right away, or the two updates
        # will conflict.
        rpsl_pk_source = rpsl_object.pk() + "-" + rpsl_object.parsed_data['source']
        if rpsl_pk_source in self.rpsl_pk_source_seen:
            self.flush_upsert_cache()

        self.records.append({
            'rpsl_pk': rpsl_object.pk(),
            'source': rpsl_object.parsed_data['source'],
            'object_class': rpsl_object.rpsl_object_class,
            'parsed_data': rpsl_object.parsed_data,
            'object_txt': rpsl_object.render_rpsl_text(),
            'ip_version': rpsl_object.ip_version(),
            'ip_first': ip_first,
            'ip_last': ip_last,
            'asn_first': rpsl_object.asn_first,
            'asn_last': rpsl_object.asn_last,
            'updated': datetime.utcnow(),
        })
        self.rpsl_pk_source_seen.add(rpsl_pk_source)

        if len(self.records) > MAX_RECORDS_CACHE_BEFORE_INSERT:
            self.flush_upsert_cache()

    def flush_upsert_cache(self):
        rpsl_composite_key = ['rpsl_pk', 'source']
        stmt = pg.insert(RPSLDatabaseObject).values(self.records)
        columns_to_update = {
            c.name: c
            for c in stmt.excluded
            if c.name not in rpsl_composite_key and c.name != 'pk'
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
        self.rpsl_pk_source_seen = set()

    def commit(self):
        if self.records:
            self.flush_upsert_cache()
        try:
            self.transaction.commit()
            self._start_transaction()
        except Exception:
            self.transaction.rollback()
            raise

    def rollback(self):
        self.transaction.rollback()

    def _start_transaction(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
