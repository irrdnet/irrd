from datetime import datetime
from typing import List, Set

from sqlalchemy.dialects import postgresql as pg

from irrd.db import engine
from irrd.db.models import RPSLDatabaseObject
from irrd.rpsl.parser import RPSLObject

MAX_RECORDS_CACHE_BEFORE_INSERT = 5000


class DatabaseHandler:
    """
    Interface for other parts of IRRD to talk to the database.

    Note that no writes to the database are final until commit()
    has been called - and rollback() can be called at any time
    to all submitted changes.
    """
    def __init__(self):
        self._records: List[dict] = []
        self._rpsl_pk_source_seen: Set[str] = set()
        self._connection = engine.connect()
        self._start_transaction()

    def upsert_object(self, rpsl_object: RPSLObject):
        """
        Schedule an RPSLObject for insertion/updating.

        This method will insert the object, or overwrite an existing object
        if it has the same RPSL primary key and source. No other checks are
        applied before overwriting.

        Writes may not be issued to the database immediately for performance
        reasons, but commit() will ensure all writes are flushed to the DB first.
        """
        ip_first = str(rpsl_object.ip_first) if rpsl_object.ip_first else None
        ip_last = str(rpsl_object.ip_last) if rpsl_object.ip_last else None

        # In some cases, multiple updates may be submitted for the same object.
        # PostgreSQL will not allow rows proposed for insertion to have duplicate
        # contstrained values - so if a second object appears with a pk/source
        # seen before, the cache must be flushed right away, or the two updates
        # will conflict.
        rpsl_pk_source = rpsl_object.pk() + "-" + rpsl_object.parsed_data['source']
        if rpsl_pk_source in self._rpsl_pk_source_seen:
            self._flush_upsert_cache()

        self._records.append({
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
        self._rpsl_pk_source_seen.add(rpsl_pk_source)

        if len(self._records) > MAX_RECORDS_CACHE_BEFORE_INSERT:
            self._flush_upsert_cache()

    def commit(self):
        """
        Commit any pending changes to the database and start a fresh transaction.
        """
        if self._records:
            self._flush_upsert_cache()
        try:
            self.transaction.commit()
            self._start_transaction()
        except Exception:  # pragma: no cover - TODO: log the exception and details and report back an error state
            self.transaction.rollback()
            raise

    def rollback(self):
        """Roll back the current transaction, discarding all submitted changes."""
        self.transaction.rollback()

    def _flush_upsert_cache(self):
        """
        Flush the current upsert cache to the database.

        This happens in one large INSERT .. ON CONFLICT DO UPDATE ..
        statement, which is more performant than individual queries
        in case of large datasets.
        """
        rpsl_composite_key = ['rpsl_pk', 'source']
        stmt = pg.insert(RPSLDatabaseObject).values(self._records)
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
            self._connection.execute(update_stmt)
        except Exception:  # pragma: no cover - TODO: log the exception and details and report back an error state
            self.transaction.rollback()
            raise

        self._records = []
        self._rpsl_pk_source_seen = set()

    def _start_transaction(self):
        """Start a fresh transaction."""
        self.transaction = self._connection.begin()
