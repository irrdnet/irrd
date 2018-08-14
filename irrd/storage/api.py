import logging
from datetime import datetime, timezone
from typing import List, Set, Iterable, Dict, Any

import sqlalchemy as sa
from IPy import IP
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.sql import Select, ColumnCollection

from irrd.conf import get_setting
from irrd.rpsl.parser import RPSLObject
from irrd.rpsl.rpsl_objects import lookup_field_names
from irrd.utils.validators import parse_as_number, ValidationError
from . import engine
from .models import RPSLDatabaseObject, RPSLDatabaseJournal, DatabaseOperation, RPSLDatabaseStatus

logger = logging.getLogger(__name__)
MAX_RECORDS_CACHE_BEFORE_INSERT = 5


class BaseRPSLObjectDatabaseQuery:
    statement: Select
    table: sa.Table
    columns: ColumnCollection

    def __init__(self):
        self._query_frozen = False
        self._sources_list = []
        self._prioritised_source = None

    def pk(self, pk: str):
        """Filter on an exact object PK (UUID)."""
        return self._filter(self.columns.pk == pk)

    def rpsl_pk(self, rpsl_pk: str):
        """Filter on an exact RPSL PK (e.g. 192.0.2.0/24,AS23456)."""
        return self.rpsl_pks([rpsl_pk])

    def rpsl_pks(self, rpsl_pks: List[str]):
        """Filter on an exact RPSL PK (e.g. 192.0.2.0/24,AS23456) - will match any PK in the list."""
        rpsl_pks = [p.upper().strip() for p in rpsl_pks]
        return self._filter(self.columns.rpsl_pk.in_(rpsl_pks))

    def sources(self, sources: List[str]):
        """
        Filter on one or more sources.

        Sources list must be an iterable. Will match objects from any
        of the mentioned sources. Order is used for sorting of results.
        """
        sources = [s.upper().strip() for s in sources]
        self._sources_list = sources
        fltr = self.columns.source.in_(self._sources_list)
        return self._filter(fltr)

    def prioritise_source(self, source: str):
        """
        Prioritise one particular source in sort order.

        Results from this source will be sorted before all others.
        When combined with first_only(), this allows a query for
        "prefer a result from this source, otherwise look for others".
        """
        self._prioritised_source = source.strip().upper()
        return self

    def object_classes(self, object_classes: List[str]):
        """
        Filter on one or more object classes.

        Classes list must be an iterable. Will match objects from any
        of the mentioned classes.
        """
        fltr = self.columns.object_class.in_(object_classes)
        return self._filter(fltr)

    def first_only(self):
        """Only return the first match."""
        self.statement = self.statement.limit(1)
        return self

    def finalise_statement(self) -> Select:
        """
        Finalise the statement and return it.

        This method does some final work on statements that may be dependent on
        each other - particularly statements that determine the sort order of
        the query, which depends on sources_list() and prioritise_source().
        """
        self._query_frozen = True

        order_by = []
        if 'ip_first' in self.columns:
            order_by.append(self.columns.ip_first.asc())
        if 'asn_first' in self.columns:
            order_by.append(self.columns.asn_first.asc())

        if self._sources_list or self._prioritised_source:
            case_elements = []
            if self._prioritised_source:
                element = (self.columns.source == self._prioritised_source, -1)
                case_elements.append(element)

            for idx, source in enumerate(self._sources_list):
                case_elements.append((self.columns.source == source, idx + 1))

            criterion = sa.case(case_elements, else_=100000)
            order_by.insert(0, criterion)

        self.statement = self.statement.order_by(*order_by)
        return self.statement

    def _filter(self, fltr):
        self._check_query_frozen()
        self.statement = self.statement.where(fltr)
        return self

    def _check_query_frozen(self) -> None:
        if self._query_frozen:
            raise ValueError("This query was frozen - no more filters can be applied.")


class RPSLDatabaseQuery(BaseRPSLObjectDatabaseQuery):
    """
    RPSL data query builder for retrieving RPSL objects.

    Offers various ways to filter, which are always constructed in an AND query.
    For example:
        q = RPSLDatabaseQuery().sources(['NTTCOM']).asn(23456)
    would match all objects that refer or include AS23456 (i.e. aut-num, route,
    as-block, route6) from the NTTCOM source.

    For methods taking a prefix or IP address, this should be an IPy.IP object.
    """
    table = RPSLDatabaseObject.__table__
    columns = RPSLDatabaseObject.__table__.c
    lookup_field_names = lookup_field_names()

    def __init__(self):
        super().__init__()
        self.statement = sa.select([
            self.columns.pk,
            self.columns.object_class,
            self.columns.rpsl_pk,
            self.columns.parsed_data,
            self.columns.object_text,
            self.columns.source,
        ])
        self._lookup_attr_counter = 0

    def lookup_attr(self, attr_name: str, attr_value: str):
        """
        Filter on a lookup attribute, e.g. mnt-by.
        At least one of the values for the lookup attribute must match attr_value.
        Matching is case-insensitive.
        """
        return self.lookup_attrs_in([attr_name], [attr_value])

    def lookup_attrs_in(self, attr_names: List[str], attr_values: List[str]):
        """
        Filter on one or more lookup attributes, e.g. mnt-by, or ['admin-c', 'tech-c']
        At least one of the values for at least one of the lookup attributes must
        match one of the items in attr_values. Matching is case-insensitive.
        """
        attr_names = [attr_name.lower() for attr_name in attr_names]
        for attr_name in attr_names:
            if attr_name not in self.lookup_field_names:
                raise ValueError(f"Invalid lookup attribute: {attr_name}")
        self._check_query_frozen()

        value_filters = []
        statement_params = {}
        for attr_name in attr_names:
            for attr_value in attr_values:
                counter = self._lookup_attr_counter
                self._lookup_attr_counter += 1
                value_filters.append(sa.text(f"parsed_data->:lookup_attr_name{counter} ? :lookup_attr_value{counter}"))
                statement_params[f"lookup_attr_name{counter}"] = attr_name
                statement_params[f"lookup_attr_value{counter}"] = attr_value.upper()
        fltr = sa.or_(*value_filters)
        self.statement = self.statement.where(fltr).params(**statement_params)

        return self

    def ip_exact(self, ip: IP):
        """
        Filter on an exact prefix or address.

        The provided ip should be an IPy.IP class, and can be a prefix or
        an address.
        """
        fltr = sa.and_(
            self.columns.ip_first == str(ip.net()),
            self.columns.ip_last == str(ip.broadcast()),
            self.columns.ip_version == ip.version()
        )
        return self._filter(fltr)

    def ip_less_specific(self, ip: IP):
        """Filter any less specifics or exact matches of a prefix."""
        fltr = sa.and_(
            self.columns.ip_first <= str(ip.net()),
            self.columns.ip_last >= str(ip.broadcast()),
            self.columns.ip_version == ip.version()
        )
        return self._filter(fltr)

    def ip_less_specific_one_level(self, ip: IP):
        """
        Filter one level less specific of a prefix.

        Due to implementation details around filtering, this must
        always be the last call on a query object, or unpredictable
        results may occur.
        """
        self._check_query_frozen()
        # One level less specific could still have multiple objects.
        # A subquery determines the smallest possible size less specific object,
        # and this is then used to filter for any objects with that size.
        fltr = sa.and_(
            self.columns.ip_first <= str(ip.net()),
            self.columns.ip_last >= str(ip.broadcast()),
            self.columns.ip_version == ip.version(),
            sa.not_(sa.and_(self.columns.ip_first == str(ip.net()), self.columns.ip_last == str(ip.broadcast()))),
        )
        self.statement = self.statement.where(fltr)

        size_subquery = self.statement.with_only_columns([self.columns.ip_size])
        size_subquery = size_subquery.order_by(self.columns.ip_size.asc())
        size_subquery = size_subquery.limit(1)

        self.statement = self.statement.where(self.columns.ip_size.in_(size_subquery))
        self._query_frozen = True
        return self

    def ip_more_specific(self, ip: IP):
        """Filter any more specifics of a prefix.

        Note that this only finds full more specifics: objects for which their
        IP range is fully encompassed by the ip parameter.
        """
        fltr = sa.and_(
            self.columns.ip_first >= str(ip.net()),
            self.columns.ip_last <= str(ip.broadcast()),
            self.columns.ip_version == ip.version(),
            sa.not_(sa.and_(self.columns.ip_first == str(ip.net()), self.columns.ip_last == str(ip.broadcast()))),
        )
        return self._filter(fltr)

    def asn(self, asn: int):
        """
        Filter for a specific ASN.

        This will match all objects that refer to this ASN, or a block
        encompassing it - including route, route6, aut-num and as-block.
        For more exact matches, add a filter on object class.
        """
        fltr = sa.and_(self.columns.asn_first <= asn, self.columns.asn_last >= asn)
        return self._filter(fltr)

    def text_search(self, value: str):
        """
        Search the database for a specific free text.

        In order, this attempts:
        - If the value is a valid AS number, return all as-block, as-set, aut-num objects
          relating or including that AS number.
        - If the value is a valid IP address or network, return all objects that relate to
          that resource and any less specifics.
        - Otherwise, return all objects where the RPSL primary key is exactly this value,
          or it matches part of a person/role name (not nic-hdl, their
          actual person/role attribute value).
        """
        self._check_query_frozen()
        try:
            _, asn = parse_as_number(value)
            return self.object_classes(['as-block', 'as-set', 'aut-num']).asn(asn)
        except ValidationError:
            pass

        try:
            ip = IP(value)
            return self.ip_less_specific(ip)
        except ValueError:
            pass

        counter = self._lookup_attr_counter
        self._lookup_attr_counter += 1
        fltr = sa.or_(
            self.columns.rpsl_pk == value.upper(),
            sa.and_(
                self.columns.object_class == 'person',
                sa.text(f"parsed_data->>'person' ILIKE :lookup_attr_text_search{counter}")
            ),
            sa.and_(
                self.columns.object_class == 'role',
                sa.text(f"parsed_data->>'role' ILIKE :lookup_attr_text_search{counter}")
            ),
        )
        self.statement = self.statement.where(fltr).params(
            **{f'lookup_attr_text_search{counter}': '%' + value + '%'}
        )
        return self

    def __repr__(self):
        return f"RPSLDatabaseQuery: {self.statement}\nPARAMS: {self.statement.compile().params}"


class RPSLDatabaseJournalQuery(BaseRPSLObjectDatabaseQuery):
    """
    RPSL data query builder for retrieving the journal,
    analogous to RPSLDatabaseQuery.
    """
    table = RPSLDatabaseJournal.__table__
    columns = RPSLDatabaseJournal.__table__.c

    def __init__(self):
        super().__init__()
        self.statement = sa.select([
            self.columns.pk,
            self.columns.rpsl_pk,
            self.columns.source,
            self.columns.serial_nrtm,
            self.columns.operation,
            self.columns.object_class,
            self.columns.object_text,
            self.columns.timestamp,
        ])

    def __repr__(self):
        return f"RPSLDatabaseJournalQuery: {self.statement}\nPARAMS: {self.statement.compile().params}"


class RPSLDatabaseStatusQuery:
    table = RPSLDatabaseStatus.__table__
    columns = RPSLDatabaseStatus.__table__.c

    def __init__(self):
        self.statement = sa.select([
            self.columns.pk,
            self.columns.source,
            self.columns.serial_oldest,
            self.columns.serial_newest,
            self.columns.serial_last_dump,
            self.columns.last_error,
            self.columns.created,
            self.columns.updated,
        ])

    def sources(self, sources: List[str]):
        """
        Filter on one or more sources.

        Sources list must be an iterable. Will match objects from any
        of the mentioned sources.
        """
        sources = [s.upper().strip() for s in sources]
        self._sources_list = sources
        fltr = self.columns.source.in_(self._sources_list)
        return self._filter(fltr)

    def finalise_statement(self):
        return self.statement

    def _filter(self, fltr):
        self.statement = self.statement.where(fltr)
        return self


class DatabaseHandler:
    """
    Interface for other parts of IRRD to talk to the database.

    Note that no writes to the database are final until commit()
    has been called - and rollback() can be called at any time
    to all submitted changes.
    """

    def __init__(self, journalling_enabled=True):
        self.journalling_enabled = journalling_enabled
        self._rpsl_upsert_cache: List[dict] = []
        self._rpsl_pk_source_seen: Set[str] = set()
        self._connection = engine.connect()
        self._start_transaction()

    def execute_query(self, query: RPSLDatabaseQuery) -> Iterable[Dict[str, Any]]:
        """Execute an RPSLDatabaseQuery within the current transaction."""
        # To be able to query objects that were just created, flush the cache.
        self._flush_rpsl_object_upsert_cache()
        statement = query.finalise_statement()
        logger.debug(f'Executing query: {query}')
        result = self._connection.execute(statement)
        for row in result:
            yield dict(row)
        result.close()

    def upsert_rpsl_object(self, rpsl_object: RPSLObject) -> None:
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

        ip_size = None
        if rpsl_object.ip_first and rpsl_object.ip_last:
            ip_size = rpsl_object.ip_last.int() - rpsl_object.ip_first.int() + 1

        # In some cases, multiple updates may be submitted for the same object.
        # PostgreSQL will not allow rows proposed for insertion to have duplicate
        # contstrained values - so if a second object appears with a pk/source
        # seen before, the cache must be flushed right away, or the two updates
        # will conflict.
        rpsl_pk_source = rpsl_object.pk() + "-" + rpsl_object.parsed_data['source']
        if rpsl_pk_source in self._rpsl_pk_source_seen:
            self._flush_rpsl_object_upsert_cache()

        self._rpsl_upsert_cache.append({
            'rpsl_pk': rpsl_object.pk(),
            'source': rpsl_object.parsed_data['source'],
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
        })
        self._rpsl_pk_source_seen.add(rpsl_pk_source)

        if len(self._rpsl_upsert_cache) > MAX_RECORDS_CACHE_BEFORE_INSERT:
            self._flush_rpsl_object_upsert_cache()

    def delete_rpsl_object(self, rpsl_object: RPSLObject) -> None:
        self._flush_rpsl_object_upsert_cache()
        table = RPSLDatabaseObject.__table__
        source = rpsl_object.parsed_data['source']
        stmt = table.delete(
            sa.and_(table.c.rpsl_pk == rpsl_object.pk(), table.c.source == source),
        ).returning(table.c.pk, table.c.rpsl_pk, table.c.source, table.c.object_class, table.c.object_text)
        results = self._connection.execute(stmt)

        if results.rowcount == 0:
            logger.warning(f'attempted to remove object {rpsl_object.pk()}/{source}, but no database row matched')
            return None
        if results.rowcount > 1:  # pragma: no cover
            # This should not be possible, as rpsl_pk/source are a composite unique value in the database scheme.
            # Therefore, a query should not be able to affect more than one row - and we also can not test this
            # scenario. Due to the possible harm of a bug in this area, we still check for it anyways.
            affected_pks = ','.join([r[0] for r in results.fetchall()])
            msg = f'attempted to remove object {rpsl_object.pk()}/{source}, but multiple objects were affected, '
            msg += f'internal pks affected: {affected_pks}'
            logger.error(msg)
            raise ValueError(msg)

        result = results.fetchone()
        self._record_history(
            operation=DatabaseOperation.delete,
            rpsl_pk=result['rpsl_pk'],
            source=result['source'],
            object_class=result['object_class'],
            object_text=result['object_text'],
        )

    def commit(self) -> None:
        """
        Commit any pending changes to the database and start a fresh transaction.
        """
        self._flush_rpsl_object_upsert_cache()
        self._update_database_status_serials()
        try:
            self.transaction.commit()
            self._start_transaction()
        except Exception:  # pragma: no cover - TODO: log the exception and details and report back an error state
            self.transaction.rollback()
            raise

    def rollback(self) -> None:
        """Roll back the current transaction, discarding all submitted changes."""
        self._rpsl_upsert_cache = []
        self._rpsl_pk_source_seen = set()
        self.transaction.rollback()
        self._start_transaction()

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
        stmt = pg.insert(RPSLDatabaseObject).values(self._rpsl_upsert_cache)
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
        for obj in self._rpsl_upsert_cache:
            self._record_history(
                operation=DatabaseOperation.add_or_update,
                rpsl_pk=obj['rpsl_pk'],
                source=obj['source'],
                object_class=obj['object_class'],
                object_text=obj['object_text'],
            )

        self._rpsl_upsert_cache = []
        self._rpsl_pk_source_seen = set()

    def _record_history(self, operation: DatabaseOperation, rpsl_pk: str, source: str, object_class: str,
                        object_text: str) -> None:
        """
        Make a record in the journal of a change to an object.

        Will only record changes when self.journalling_enabled is set,
        and the database.SOURCE.authoritative or database.SOURCE.keep_journal
        settings are set.

        Note that this method locks the journal table for writing to ensure a
        gapless set of NRTM serials.
        """
        if self.journalling_enabled and (
                get_setting(f'databases.{source}.authoritative') or get_setting(f'databases.{source}.keep_journal')
        ):
            journal_tablename = RPSLDatabaseJournal.__tablename__
            self._connection.execute(f'LOCK TABLE {journal_tablename} IN EXCLUSIVE MODE')

            serial_subquery = sa.select([sa.text(f'COALESCE(MAX(serial_nrtm), 0) + 1')])
            serial_subquery = serial_subquery.where(RPSLDatabaseJournal.__table__.c.source == source)
            serial_subquery = serial_subquery.as_scalar()

            stmt = RPSLDatabaseJournal.__table__.insert().values(
                rpsl_pk=rpsl_pk,
                source=source,
                operation=operation,
                object_class=object_class,
                object_text=object_text,
                serial_nrtm=serial_subquery,
            )
            self._connection.execute(stmt)
            self.sources_journal_updated.add(source)

    def _update_database_status_serials(self):
        """
        Update the status of all database serials, based on the current
        journal. Note that this only correctly updates databases for
        which we have a journal.
        If there is no status object for this database, it is created.
        """
        c_journal = RPSLDatabaseJournal.__table__.c

        for source in self.sources_journal_updated:
            subquery_min = sa.select([sa.func.min(c_journal.serial_nrtm)]).where(c_journal.source == source)
            subquery_max = sa.select([sa.func.max(c_journal.serial_nrtm)]).where(c_journal.source == source)

            stmt = pg.insert(RPSLDatabaseStatus).values(
                serial_oldest=subquery_min,
                serial_newest=subquery_max,
                source=source,
                updated=datetime.now(timezone.utc),
            )
            columns_to_update = {
                c.name: c
                for c in stmt.excluded
                if c.name != 'source'
            }

            stmt = stmt.on_conflict_do_update(
                index_elements=['source'],
                set_=columns_to_update,
            )

            self._connection.execute(stmt)

    def _start_transaction(self) -> None:
        """Start a fresh transaction."""
        self.transaction = self._connection.begin()
        self.sources_journal_updated: Set[str] = set()
