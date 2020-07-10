from collections import defaultdict
from typing import Optional, Tuple, List, Dict

from IPy import IP

from irrd.conf import get_setting
from irrd.rpsl.parser import RPSLObject
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery
from irrd.utils.validators import parse_as_number
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
                            asn_first: Optional[int], members: List[str], mp_members: List[str]
                            ) -> Tuple[ScopeFilterStatus, str]:
        """
        Validate whether a particular set of RPSL data is in scope.
        Depending on object_class, members and mp_members are also validated.
        Returns a ScopeFilterStatus.
        """
        out_of_scope = [ScopeFilterStatus.out_scope_prefix, ScopeFilterStatus.out_scope_as]
        if object_class not in ['route', 'route6', 'aut-num', 'as-set', 'route-set']:
            return ScopeFilterStatus.in_scope, ''

        if prefix:
            prefix_state = self.validate(source, prefix)
            if prefix_state in out_of_scope:
                return prefix_state, f'prefix {prefix} is out of scope'

        if asn_first is not None:
            asn_state = self.validate(source, asn=asn_first)
            if asn_state in out_of_scope:
                return asn_state, f'ASN {asn_first} is out of scope'

        if object_class == 'route-set':
            for member in members + mp_members:
                try:
                    prefix = IP(member)
                except ValueError:
                    continue
                prefix_state = self.validate(source, prefix=prefix)
                if prefix_state in out_of_scope:
                    return prefix_state, f'member prefix {member} is out of scope'

        if object_class == 'as-set':
            for member in members:
                try:
                    _, asn = parse_as_number(member)
                except ValueError:
                    continue
                asn_state = self.validate(source, asn=asn)
                if asn_state in out_of_scope:
                    return asn_state, f'member ASN {member} is out of scope'

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
            rpsl_object.parsed_data.get('members', []),
            rpsl_object.parsed_data.get('mp-members', []),
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
        columns = ['rpsl_pk', 'ip_first', 'prefix_length', 'asn_first', 'source', 'object_class',
                   'object_text', 'scopefilter_status']

        objs_changed: Dict[ScopeFilterStatus, List[Dict[str, str]]] = defaultdict(list)

        def process_results(results):
            for result in results:
                current_status = result['scopefilter_status']
                result['old_status'] = current_status
                prefix = None
                if result['ip_first']:
                    prefix = IP(result['ip_first'] + '/' + str(result['prefix_length']))
                new_status, _ = self._validate_rpsl_data(
                    result['source'],
                    result['object_class'],
                    prefix,
                    result['asn_first'],
                    result.get('parsed_data', {}).get('members', []),
                    result.get('parsed_data', {}).get('mp-members', []),
                )
                if new_status != current_status:
                    result['scopefilter_status'] = new_status
                    objs_changed[new_status].append(result)

        q = RPSLDatabaseQuery(column_names=columns, enable_ordering=False)
        q = q.object_classes(['route', 'route6', 'aut-num'])
        process_results(database_handler.execute_query(q))

        # parsed_data is only retrieved when needed, as it has a performance impact
        columns.append('parsed_data')
        q = RPSLDatabaseQuery(column_names=columns, enable_ordering=False)
        q = q.object_classes(['as-set', 'route-set'])
        process_results(database_handler.execute_query(q))

        return (objs_changed[ScopeFilterStatus.in_scope],
                objs_changed[ScopeFilterStatus.out_scope_as],
                objs_changed[ScopeFilterStatus.out_scope_prefix])
