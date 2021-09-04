from collections import defaultdict
from typing import Optional, Tuple, List, Dict

from IPy import IP

from irrd.conf import get_setting
from irrd.rpsl.parser import RPSLObject
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery
from .status import ScopeFilterStatus


class ScopeFilterValidator:
    """
    The scope filter validator validates whether prefixes, ASNs or RPSL
    objects fall within the configured scope filter.
    """

    def __init__(self):
        self.load_filters()

    def load_filters(self):
        """
        (Re)load the local cache of the configured filters.
        Also called by __init__
        """
        prefixes = get_setting('scopefilter.prefixes', [])
        self.filtered_prefixes = [IP(prefix) for prefix in prefixes]

        self.filtered_asns = set()
        self.filtered_asn_ranges = set()
        asn_filters = get_setting('scopefilter.asns', [])
        for asn_filter in asn_filters:
            if '-' in str(asn_filter):
                start, end = asn_filter.split('-')
                self.filtered_asn_ranges.add((int(start), int(end)))
            else:
                self.filtered_asns.add(int(asn_filter))

    def validate(self, source: str, prefix: Optional[IP]=None, asn: Optional[int]=None) -> ScopeFilterStatus:
        """
        Validate a prefix and/or ASN, for a particular source.
        Returns a tuple of a ScopeFilterStatus and an explanation string.
        """
        if not prefix and asn is None:
            raise ValueError('Scope Filter validator must be provided asn or prefix')

        if get_setting(f'sources.{source}.scopefilter_excluded'):
            return ScopeFilterStatus.in_scope

        if prefix:
            for filtered_prefix in self.filtered_prefixes:
                if prefix.version() == filtered_prefix.version() and filtered_prefix.overlaps(prefix):
                    return ScopeFilterStatus.out_scope_prefix

        if asn is not None:
            if asn in self.filtered_asns:
                return ScopeFilterStatus.out_scope_as
            for range_start, range_end in self.filtered_asn_ranges:
                if range_start <= asn <= range_end:
                    return ScopeFilterStatus.out_scope_as

        return ScopeFilterStatus.in_scope

    def _validate_rpsl_data(self, source: str, object_class: str, prefix: Optional[IP],
                            asn_first: Optional[int]) -> Tuple[ScopeFilterStatus, str]:
        """
        Validate whether a particular set of RPSL data is in scope.
        Returns a ScopeFilterStatus.
        """
        out_of_scope = [ScopeFilterStatus.out_scope_prefix, ScopeFilterStatus.out_scope_as]
        if object_class not in ['route', 'route6', 'aut-num']:
            return ScopeFilterStatus.in_scope, ''

        if prefix:
            prefix_state = self.validate(source, prefix)
            if prefix_state in out_of_scope:
                return prefix_state, f'prefix {prefix} is out of scope'

        if asn_first is not None:
            asn_state = self.validate(source, asn=asn_first)
            if asn_state in out_of_scope:
                return asn_state, f'ASN {asn_first} is out of scope'

        return ScopeFilterStatus.in_scope, ''

    def validate_rpsl_object(self, rpsl_object: RPSLObject) -> Tuple[ScopeFilterStatus, str]:
        """
        Validate whether an RPSLObject is in scope.
        Returns a tuple of a ScopeFilterStatus and an explanation string.
        """
        return self._validate_rpsl_data(
            rpsl_object.source(),
            rpsl_object.rpsl_object_class,
            rpsl_object.prefix,
            rpsl_object.asn_first,
        )

    def validate_all_rpsl_objects(self, database_handler: DatabaseHandler) -> \
            Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
        """
        Apply the scope filter to all relevant objects.

        Retrieves all routes from the DB, and aggregates the validation results.
        Returns a tuple of three sets:
        - one with routes that should be set to status in_scope, but are not now
        - one with routes that should be set to status out_scope_as, but are not now
        - one with routes that should be set to status out_scope_prefix, but are not now
        Each object is recorded as a dict, which has the fields shown
        in "columns" below.

        Objects where their current status in the DB matches the new
        validation result, are not included in the return value.
        """
        columns = ['pk', 'rpsl_pk', 'ip_first', 'prefix_length', 'asn_first', 'source', 'object_class',
                   'scopefilter_status', 'rpki_status']

        objs_changed: Dict[ScopeFilterStatus, List[Dict[str, str]]] = defaultdict(list)

        q = RPSLDatabaseQuery(column_names=columns, enable_ordering=False)
        q = q.object_classes(['route', 'route6', 'aut-num'])
        results = database_handler.execute_query(q)

        for result in results:
            current_status = result['scopefilter_status']
            result['old_status'] = current_status
            prefix = None
            if result.get('ip_first'):
                prefix = IP(result['ip_first'] + '/' + str(result['prefix_length']))
            new_status, _ = self._validate_rpsl_data(
                result['source'],
                result['object_class'],
                prefix,
                result['asn_first'],
            )
            if new_status != current_status:
                result['scopefilter_status'] = new_status
                objs_changed[new_status].append(result)

        # Object text is only retrieved for objects with state changes
        pks_to_enrich = [obj['pk'] for objs in objs_changed.values() for obj in objs]
        query = RPSLDatabaseQuery(['pk', 'object_text'], enable_ordering=False).pks(pks_to_enrich)
        rows_per_pk = {row['pk']: row for row in database_handler.execute_query(query)}

        for rpsl_objs in objs_changed.values():
            for rpsl_obj in rpsl_objs:
                rpsl_obj.update(rows_per_pk[rpsl_obj['pk']])

        return (objs_changed[ScopeFilterStatus.in_scope],
                objs_changed[ScopeFilterStatus.out_scope_as],
                objs_changed[ScopeFilterStatus.out_scope_prefix])
