import logging
from typing import List, Optional

import sqlalchemy as sa
from IPy import IP
from sqlalchemy.sql import Select, ColumnCollection

from irrd.rpki.status import RPKIStatus
from irrd.rpsl.rpsl_objects import lookup_field_names
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.storage.models import (RPSLDatabaseObject, RPSLDatabaseJournal, RPSLDatabaseStatus,
                                 ROADatabaseObject)
from irrd.utils.validators import parse_as_number, ValidationError

logger = logging.getLogger(__name__)


class BaseRPSLObjectDatabaseQuery:
    statement: Select
    table: sa.Table
    columns: ColumnCollection

    def __init__(self, ordered_by_sources=True, enable_ordering=True):
        self._query_frozen = False
        self._sources_list = []
        self._ordered_by_sources = ordered_by_sources
        self._enable_ordering = enable_ordering

    def pk(self, pk: str):
        """Filter on an exact object PK (UUID)."""
        return self._filter(self.columns.pk == pk)

    def rpsl_pk(self, rpsl_pk: str):
        """Filter on an exact RPSL PK (e.g. 192.0.2.0/24,AS65537)."""
        return self.rpsl_pks([rpsl_pk])

    def rpsl_pks(self, rpsl_pks: List[str]):
        """Filter on an exact RPSL PK (e.g. 192.0.2.0/24,AS65537) - will match any PK in the list."""
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

        if self._enable_ordering:
            order_by = []
            if 'ip_first' in self.columns:
                order_by.append(self.columns.ip_first.asc())
            if 'asn_first' in self.columns:
                order_by.append(self.columns.asn_first.asc())
            if 'rpsl_pk' in self.columns:
                order_by.append(self.columns.rpsl_pk.asc())

            if self._ordered_by_sources and self._sources_list:
                case_elements = []
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
            raise ValueError('This query was frozen - no more filters can be applied.')


class RPSLDatabaseQuery(BaseRPSLObjectDatabaseQuery):
    """
    RPSL data query builder for retrieving RPSL objects.

    Offers various ways to filter, which are always constructed in an AND query.
    For example:
        q = RPSLDatabaseQuery().sources(['NTTCOM']).asn_less_specific(65537)
    would match all objects that refer or include AS65537 (i.e. aut-num, route,
    as-block, route6) from the NTTCOM source.

    For methods taking a prefix or IP address, this should be an IPy.IP object.
    """
    table = RPSLDatabaseObject.__table__
    columns = RPSLDatabaseObject.__table__.c
    lookup_field_names = lookup_field_names()

    def __init__(self, column_names=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if column_names is None:
            columns = [
                self.columns.pk,
                self.columns.object_class,
                self.columns.rpsl_pk,
                self.columns.parsed_data,
                self.columns.object_text,
                self.columns.source,
                self.columns.rpki_status,
            ]
        else:
            columns = [self.columns.get(name) for name in column_names]
        self.statement = sa.select(columns)
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
                raise ValueError(f'Invalid lookup attribute: {attr_name}')
        self._check_query_frozen()

        value_filters = []
        statement_params = {}
        for attr_name in attr_names:
            for attr_value in attr_values:
                counter = self._lookup_attr_counter
                self._lookup_attr_counter += 1
                value_filters.append(sa.text(f'parsed_data->:lookup_attr_name{counter} ? :lookup_attr_value{counter}'))
                statement_params[f'lookup_attr_name{counter}'] = attr_name
                statement_params[f'lookup_attr_value{counter}'] = attr_value.upper()
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
        """Filter any more specifics of a prefix, not including exact matches.

        Note that this only finds full more specifics: objects for which their
        IP range is fully encompassed by the ip parameter.
        """
        fltr = sa.and_(
            self.columns.ip_first >= str(ip.net()),
            self.columns.ip_first <= str(ip.broadcast()),
            self.columns.ip_last <= str(ip.broadcast()),
            self.columns.ip_last >= str(ip.net()),
            self.columns.ip_version == ip.version(),
            sa.not_(sa.and_(self.columns.ip_first == str(ip.net()), self.columns.ip_last == str(ip.broadcast()))),
        )
        return self._filter(fltr)

    def asn(self, asn: int):
        """
        Filter for exact matches on an ASN.
        """
        fltr = sa.and_(self.columns.asn_first == asn, self.columns.asn_last == asn)
        return self._filter(fltr)

    def asns_first(self, asns: List[int]):
        """
        Filter for asn_first being in a list of ASNs.
        This is useful when also restricting object class to 'route' for instance.
        """
        fltr = self.columns.asn_first.in_(asns)
        return self._filter(fltr)

    def asn_less_specific(self, asn: int):
        """
        Filter for a specific ASN, or any less specific matches.

        This will match all objects that refer to this ASN, or a block
        encompassing it - including route, route6, aut-num and as-block.
        """
        fltr = sa.and_(self.columns.asn_first <= asn, self.columns.asn_last >= asn)
        return self._filter(fltr)

    def rpki_status(self, status: List[RPKIStatus]):
        """
        Filter for RPSL objects with a specific RPKI validation status.
        """
        fltr = self.columns.rpki_status.in_(status)
        return self._filter(fltr)

    def scopefilter_status(self, status: List[ScopeFilterStatus]):
        """
        Filter for RPSL objects with a specific scope filter status.
        """
        fltr = self.columns.scopefilter_status.in_(status)
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
            return self.object_classes(['as-block', 'as-set', 'aut-num']).asn_less_specific(asn)
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
        return f'RPSLDatabaseQuery: {self.statement}\nPARAMS: {self.statement.compile().params}'


class RPSLDatabaseJournalQuery(BaseRPSLObjectDatabaseQuery):
    """
    RPSL data query builder for retrieving the journal,
    analogous to RPSLDatabaseQuery.
    """
    table = RPSLDatabaseJournal.__table__
    columns = RPSLDatabaseJournal.__table__.c

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.statement = sa.select([
            self.columns.pk,
            self.columns.rpsl_pk,
            self.columns.source,
            self.columns.serial_nrtm,
            self.columns.operation,
            self.columns.object_class,
            self.columns.object_text,
            self.columns.timestamp,
        ]).order_by(self.columns.source.asc(), self.columns.serial_nrtm.asc())

    def serial_range(self, start: int, end: Optional[int]=None):
        """
        Filter for a serials within a specific range, inclusive.
        """
        if end is not None:
            fltr = sa.and_(self.columns.serial_nrtm >= start, self.columns.serial_nrtm <= end)
        else:
            fltr = self.columns.serial_nrtm >= start
        return self._filter(fltr)

    def __repr__(self):
        return f'RPSLDatabaseJournalQuery: {self.statement}\nPARAMS: {self.statement.compile().params}'


class DatabaseStatusQuery:
    table = RPSLDatabaseStatus.__table__
    columns = RPSLDatabaseStatus.__table__.c

    def __init__(self):
        self._sources_list: List[str] = []
        self.statement = sa.select([
            self.columns.pk,
            self.columns.source,
            self.columns.serial_oldest_seen,
            self.columns.serial_newest_seen,
            self.columns.serial_oldest_journal,
            self.columns.serial_newest_journal,
            self.columns.serial_last_export,
            self.columns.serial_newest_mirror,
            self.columns.force_reload,
            self.columns.synchronised_serials,
            self.columns.last_error,
            self.columns.last_error_timestamp,
            self.columns.created,
            self.columns.updated,
        ])

    def source(self, source: str):
        """Filter on a source."""
        return self.sources([source])

    def sources(self, sources: List[str]):
        """Filter on one or more sources."""
        self._sources_list = [s.upper() for s in sources]
        return self

    def finalise_statement(self):
        order_by = [self.columns.source.asc()]

        if self._sources_list:
            fltr = self.columns.source.in_(self._sources_list)
            self._filter(fltr)

            case_elements = []
            for idx, source in enumerate(self._sources_list):
                case_elements.append((self.columns.source == source, idx + 1))

            criterion = sa.case(case_elements, else_=100000)
            order_by.insert(0, criterion)

        self.statement = self.statement.order_by(*order_by)
        return self.statement

    def _filter(self, fltr):
        self.statement = self.statement.where(fltr)
        return self

    def __repr__(self):
        return f'DatabaseStatusQuery: {self.statement}\nPARAMS: {self.statement.compile().params}'


class RPSLDatabaseObjectStatisticsQuery:
    """
    Special statistics query, calculating the number of
    objects per object class per source.
    """
    table = RPSLDatabaseObject.__table__
    columns = RPSLDatabaseObject.__table__.c

    def __init__(self):
        self.statement = sa.select([
            self.columns.source,
            self.columns.object_class,
            sa.func.count(self.columns.pk).label('count'),
        ]).group_by(self.columns.source, self.columns.object_class)

    def finalise_statement(self):
        return self.statement

    def __repr__(self):
        return f'RPSLDatabaseObjectStatisticsQuery: {self.statement}\nPARAMS: {self.statement.compile().params}'


class ROADatabaseObjectQuery:
    """
    Query builder for ROA objects.
    """
    table = ROADatabaseObject.__table__
    columns = ROADatabaseObject.__table__.c

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.statement = sa.select([
            self.columns.pk,
            self.columns.prefix,
            self.columns.asn,
            self.columns.max_length,
            self.columns.trust_anchor,
            self.columns.ip_version,
        ])

    def ip_less_specific_or_exact(self, ip: IP):
        """Filter any less specifics or exact matches of a prefix."""
        fltr = sa.and_(
            self.columns.prefix.op('>>=')(str(ip))
        )
        self.statement = self.statement.where(fltr)
        return self

    def finalise_statement(self):
        return self.statement

    def __repr__(self):
        return f'ROADatabaseObjectQuery: {self.statement}\nPARAMS: {self.statement.compile().params}'
