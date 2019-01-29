import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Set, Dict, Any, Tuple, Optional, Iterator, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from irrd.conf import get_setting
from irrd.rpsl.parser import RPSLObject
from irrd.rpsl.rpsl_objects import OBJECT_CLASS_MAPPING
from .preload import get_preloader
from .queries import (BaseRPSLObjectDatabaseQuery, DatabaseStatusQuery,
                      RPSLDatabaseObjectStatisticsQuery)
from . import get_engine
from .models import RPSLDatabaseObject, RPSLDatabaseJournal, DatabaseOperation, RPSLDatabaseStatus

logger = logging.getLogger(__name__)
MAX_RECORDS_CACHE_BEFORE_INSERT = 5000


class DatabaseHandler:
    """
    Interface for other parts of IRRD to talk to the database.

    Note that no writes to the database are final until commit()
    has been called - and rollback() can be called at any time
    to all submitted changes.
    """
    journaling_enabled: bool
    _transaction: sa.engine.base.Transaction
    _rpsl_pk_source_seen: Set[str]
    # The RPSL upsert cache is a list of tuples. Each tuple first has a dict
    # with all database column names and their values, and then an optional int
    # with a forced serial. The forced serial is used for mirrored sources,
    # where this basically means: this call was triggered by an NRTM operation
    # with this serial.
    _rpsl_upsert_cache: List[Tuple[dict, Optional[int]]]

    def __init__(self, enable_preload_update=True):
        """
        Create a new database handler.

        If enable_preload is True (default), the Preloader will be notified
        of changed objects after every committed transaction. This should
        be disabled in tasks that do not run in the IRRd server process,
        such as the submit_email script.
        """
        self.journaling_enabled = True
        self._connection = get_engine().connect()
        self._start_transaction()
        self.preloader = None
        if enable_preload_update:
            self.preloader = get_preloader()

    def _start_transaction(self) -> None:
        """Start a fresh transaction."""
        self._transaction = self._connection.begin()
        self._rpsl_upsert_cache = []
        self._rpsl_pk_source_seen: Set[str] = set()
        self._object_classes_modified: Set[str] = set()
        self.status_tracker = DatabaseStatusTracker(self, journaling_enabled=self.journaling_enabled)

    def disable_journaling(self):
        self.journaling_enabled = False
        self.status_tracker.journaling_enabled = False

    def commit(self) -> None:
        """
        Commit any pending changes to the database and start a fresh transaction.
        """
        self._flush_rpsl_object_upsert_cache()
        self.status_tracker.finalise_transaction()
        try:
            self._transaction.commit()
            if self.preloader:
                self.preloader.reload(self._object_classes_modified)
            self._start_transaction()
        except Exception as exc:  # pragma: no cover
            self._transaction.rollback()
            logger.error('Exception occurred while committing changes, rolling back', exc_info=exc)
            raise

    def rollback(self) -> None:
        """Roll back the current transaction, discarding all submitted changes."""
        self._rpsl_upsert_cache = []
        self._rpsl_pk_source_seen = set()
        self._transaction.rollback()
        self._start_transaction()

    def execute_query(self, query: Union[BaseRPSLObjectDatabaseQuery, DatabaseStatusQuery, RPSLDatabaseObjectStatisticsQuery]) -> Iterator[Dict[str, Any]]:
        """Execute an RPSLDatabaseQuery within the current transaction."""
        # To be able to query objects that were just created, flush the cache.
        self._flush_rpsl_object_upsert_cache()
        statement = query.finalise_statement()
        result = self._connection.execute(statement)
        for row in result.fetchall():
            yield dict(row)
        result.close()

    def execute_statement(self, statement):
        """Execute a raw SQLAlchemy statement, without flushing the upsert cache."""
        return self._connection.execute(statement)

    def upsert_rpsl_object(self, rpsl_object: RPSLObject, forced_serial: Optional[int]=None) -> None:
        """
        Schedule an RPSLObject for insertion/updating.

        This method will insert the object, or overwrite an existing object
        if it has the same RPSL primary key and source. No other checks are
        applied before overwriting.

        Writes may not be issued to the database immediately for performance
        reasons, but commit() will ensure all writes are flushed to the DB first.

        The forced serial is needed for mirrored sources, where this basically means:
        this call was triggered by an NRTM operation with this serial.
        """
        ip_first = str(rpsl_object.ip_first) if rpsl_object.ip_first else None
        ip_last = str(rpsl_object.ip_last) if rpsl_object.ip_last else None

        ip_size = None
        if rpsl_object.ip_first and rpsl_object.ip_last:
            ip_size = rpsl_object.ip_last.int() - rpsl_object.ip_first.int() + 1

        # In some cases, multiple updates may be submitted for the same object.
        # PostgreSQL will not allow rows proposed for insertion to have duplicate
        # constrained values - so if a second object appears with a pk/source
        # seen before, the cache must be flushed right away, or the two updates
        # will conflict.
        source = rpsl_object.parsed_data['source']
        rpsl_pk_source = rpsl_object.pk() + '-' + source
        if rpsl_pk_source in self._rpsl_pk_source_seen:
            self._flush_rpsl_object_upsert_cache()

        self._rpsl_upsert_cache.append((
            {
                'rpsl_pk': rpsl_object.pk(),
                'source': source,
                'object_class': rpsl_object.rpsl_object_class,
                'parsed_data': rpsl_object.parsed_data,
                'object_text': rpsl_object.render_rpsl_text(),
                'ip_version': rpsl_object.ip_version(),
                'ip_first': ip_first,
                'ip_last': ip_last,
                'ip_size': ip_size,
                'asn_first': rpsl_object.asn_first,
                'asn_last': rpsl_object.asn_last,
                'updated': datetime.now(timezone.utc),
            },
            forced_serial,
        ))
        self._rpsl_pk_source_seen.add(rpsl_pk_source)
        self._object_classes_modified.add(rpsl_object.rpsl_object_class)

        if len(self._rpsl_upsert_cache) > MAX_RECORDS_CACHE_BEFORE_INSERT:
            self._flush_rpsl_object_upsert_cache()

    def delete_rpsl_object(self, rpsl_object: RPSLObject, forced_serial: Optional[int]=None) -> None:
        """
        Delete an RPSL object from the database.

        The forced serial is needed for mirrored sources, where this basically means:
        this call was triggered by an NRTM operation with this serial.
        """
        self._flush_rpsl_object_upsert_cache()
        table = RPSLDatabaseObject.__table__
        source = rpsl_object.parsed_data['source']
        stmt = table.delete(
            sa.and_(table.c.rpsl_pk == rpsl_object.pk(), table.c.source == source),
        ).returning(table.c.pk, table.c.rpsl_pk, table.c.source, table.c.object_class, table.c.object_text)
        results = self._connection.execute(stmt)

        if results.rowcount == 0:
            logger.error(f'Attempted to remove object {rpsl_object.pk()}/{source}, but no database row matched')
            return None
        if results.rowcount > 1:  # pragma: no cover
            # This should not be possible, as rpsl_pk/source are a composite unique value in the database scheme.
            # Therefore, a query should not be able to affect more than one row - and we also can not test this
            # scenario. Due to the possible harm of a bug in this area, we still check for it anyways.
            affected_pks = ','.join([r[0] for r in results.fetchall()])
            msg = f'Attempted to remove object {rpsl_object.pk()}/{source}, but multiple objects were affected, '
            msg += f'internal pks affected: {affected_pks}'
            logger.critical(msg)
            raise ValueError(msg)

        result = results.fetchone()
        self.status_tracker.record_operation(
            operation=DatabaseOperation.delete,
            rpsl_pk=result['rpsl_pk'],
            source=result['source'],
            object_class=result['object_class'],
            object_text=result['object_text'],
            forced_serial=forced_serial,
        )
        self._object_classes_modified.add(result['object_class'])

    def _flush_rpsl_object_upsert_cache(self) -> None:
        """
        Flush the current upsert cache to the database.

        This happens in one large INSERT .. ON CONFLICT DO UPDATE ..
        statement, which is more performant than individual queries
        in case of large datasets.
        """
        if not self._rpsl_upsert_cache:
            return

        rpsl_composite_key = ['rpsl_pk', 'source']
        stmt = pg.insert(RPSLDatabaseObject).values([x[0] for x in self._rpsl_upsert_cache])
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
        except Exception as exc:  # pragma: no cover
            self._transaction.rollback()
            logger.error(f'Exception occurred while executing statement: {update_stmt}, rolling back', exc_info=exc)
            raise

        for obj, forced_serial in self._rpsl_upsert_cache:
            self.status_tracker.record_operation(
                operation=DatabaseOperation.add_or_update,
                rpsl_pk=obj['rpsl_pk'],
                source=obj['source'],
                object_class=obj['object_class'],
                object_text=obj['object_text'],
                forced_serial=forced_serial,
            )

        self._rpsl_upsert_cache = []
        self._rpsl_pk_source_seen = set()

    def delete_all_rpsl_objects_with_journal(self, source):
        """
        Delete all RPSL objects for a source from the database,
        all journal entries and the database status.
        This is intended for cases where a full re-import is done.
        Note that no journal records are kept of this change itself.
        """
        self._flush_rpsl_object_upsert_cache()
        table = RPSLDatabaseObject.__table__
        stmt = table.delete(table.c.source == source)
        self._connection.execute(stmt)
        table = RPSLDatabaseJournal.__table__
        stmt = table.delete(table.c.source == source)
        self._connection.execute(stmt)
        table = RPSLDatabaseStatus.__table__
        stmt = table.delete(table.c.source == source)
        self._connection.execute(stmt)
        # All objects are presumed to have been changed.
        self._object_classes_modified.update(OBJECT_CLASS_MAPPING.keys())

    def force_record_serial_seen(self, source: str, serial: int) -> None:
        """
        Forcibly record that a serial was seen for a source.

        This is used when receiving NRTM streams in which some objects are
        ignored or have errors. Because their operations are never saved, the
        serial needs to be manually advanced, to prevent re-querying the
        same objects all the time.
        """
        self.status_tracker.force_record_serial_seen(source, serial)

    def record_mirror_error(self, source: str, error: str) -> None:
        """
        Record an error seen in a mirrored database.
        Only the most recent error is stored in the DB status.
        """
        self.status_tracker.record_mirror_error(source, error)

    def record_serial_exported(self, source: str, serial: int) -> None:
        """
        Record an export of a source at a particular serial.
        """
        self.status_tracker.record_serial_exported(source, serial)

    def close(self) -> None:
        self._connection.close()


class DatabaseStatusTracker:
    """
    Keep track of the status of sources, and their journal, if enabled.
    Changes to the database should always call record_operation() on this object,
    and finalise_transaction() before committing.

    If journaling is enabled, a new entry in the journal will be made.
    If a journal entry was made, or forced_serial was set, a record is kept in
    memory with all serials encountered/created for this source.

    When finalising, the RPSLDatabaseStatus table is updated to correctly
    reflect the range of serials known for a particular source.
    """
    journaling_enabled: bool
    _new_serials_per_source: Dict[str, Set[int]]
    _sources_seen: Set[str]
    _mirroring_error: Dict[str, str]
    _exported_serials: Dict[str, int]

    c_journal = RPSLDatabaseJournal.__table__.c
    c_status = RPSLDatabaseStatus.__table__.c

    def __init__(self, database_handler: DatabaseHandler, journaling_enabled=True) -> None:
        self.database_handler = database_handler
        self.journaling_enabled = journaling_enabled
        self._reset()

    def force_record_serial_seen(self, source: str, serial: int):
        """
        Forcibly record that a serial was seen for a source.
        See DatabaseHandler.force_record_serial_seen for more info.
        """
        self._sources_seen.add(source)
        self._new_serials_per_source[source].add(serial)

    def record_mirror_error(self, source: str, error: str) -> None:
        """
        Record an error seen in a mirrored database.
        Only the most recent error is stored in the DB status.
        """
        self._sources_seen.add(source)
        self._mirroring_error[source] = error

    def record_serial_exported(self, source: str, serial: int) -> None:
        """
        Record an export of a source at a particular serial.
        Only the most recent serial is stored in the DB status.
        """
        self._sources_seen.add(source)
        self._exported_serials[source] = serial

    def record_operation(self, operation: DatabaseOperation, rpsl_pk: str, source: str, object_class: str,
                         object_text: str, forced_serial: Optional[int]) -> None:
        """
        Make a record in the journal of a change to an object.

        Will only record changes when self.journaling_enabled is set,
        and the database.SOURCE.keep_journal is set.
        The source will always be added to _sources_seen.

        Note that this method locks the journal table for writing to ensure a
        gapless set of NRTM serials.
        """
        self._sources_seen.add(source)
        if self.journaling_enabled and get_setting(f'sources.{source}.keep_journal'):
            journal_tablename = RPSLDatabaseJournal.__tablename__

            if forced_serial is None:
                self.database_handler.execute_statement(f'LOCK TABLE {journal_tablename} IN EXCLUSIVE MODE')
                serial_nrtm = sa.select([sa.text(f'COALESCE(MAX(serial_nrtm), 0) + 1')])
                serial_nrtm = serial_nrtm.where(RPSLDatabaseJournal.__table__.c.source == source)
                serial_nrtm = serial_nrtm.as_scalar()
            else:
                serial_nrtm = forced_serial
            stmt = RPSLDatabaseJournal.__table__.insert().values(
                rpsl_pk=rpsl_pk,
                source=source,
                operation=operation,
                object_class=object_class,
                object_text=object_text,
                serial_nrtm=serial_nrtm,
            ).returning(self.c_journal.serial_nrtm)

            insert_result = self.database_handler.execute_statement(stmt)
            inserted_serial = insert_result.fetchone()['serial_nrtm']
            self._new_serials_per_source[source].add(inserted_serial)
        elif forced_serial is not None:
            self._new_serials_per_source[source].add(forced_serial)

    def finalise_transaction(self):
        """
        - Create a new status object for all seen sources if it does not exist.
        - Reset the force_reload flag.
        - If new serials were recorded for a source, update the database
          serial stats in the status object.
        - Update the latest source errors.
        """
        for source in self._sources_seen:
            stmt = pg.insert(RPSLDatabaseStatus).values(
                source=source,
                force_reload=False,
                updated=datetime.now(timezone.utc),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['source'],
                set_={'force_reload': False},
            )
            self.database_handler.execute_statement(stmt)

        for source, serials in self._new_serials_per_source.items():
            serial_oldest_seen = sa.select([
                sa.func.least(sa.func.min(self.c_status.serial_oldest_seen), min(serials))
            ]).where(self.c_status.source == source)
            serial_newest_seen = sa.select([
                sa.func.greatest(sa.func.max(self.c_status.serial_newest_seen), max(serials))
            ]).where(self.c_status.source == source)

            serial_oldest_journal = sa.select([
                sa.func.min(self.c_journal.serial_nrtm)
            ]).where(self.c_journal.source == source)
            serial_newest_journal = sa.select([
                sa.func.max(self.c_journal.serial_nrtm)
            ]).where(self.c_journal.source == source)

            stmt = RPSLDatabaseStatus.__table__.update().where(self.c_status.source == source).values(
                serial_oldest_seen=serial_oldest_seen,
                serial_newest_seen=serial_newest_seen,
                serial_oldest_journal=serial_oldest_journal,
                serial_newest_journal=serial_newest_journal,
                updated=datetime.now(timezone.utc),
            )
            self.database_handler.execute_statement(stmt)

        for source, error in self._mirroring_error.items():
            stmt = RPSLDatabaseStatus.__table__.update().where(self.c_status.source == source).values(
                last_error=error,
                last_error_timestamp=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc),
            )
            self.database_handler.execute_statement(stmt)

        for source, serial in self._exported_serials.items():
            stmt = RPSLDatabaseStatus.__table__.update().where(self.c_status.source == source).values(
                serial_last_export=serial,
            )
            self.database_handler.execute_statement(stmt)

        self._reset()

    def _reset(self):
        self._new_serials_per_source = defaultdict(set)
        self._sources_seen = set()
        self._mirroring_error = dict()
        self._exported_serials = dict()
