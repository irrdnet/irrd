import datrie
from collections import defaultdict

import codecs
import socket
from IPy import IP
from typing import Optional, List, Tuple, Set, Dict

from irrd.conf import RPKI_IRR_PSEUDO_SOURCE, get_setting
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery, ROADatabaseObjectQuery
from .importer import ROA
from .status import RPKIStatus

decode_hex = codecs.getdecoder("hex_codec")


class BulkRouteROAValidator:
    """
    The bulk route validator is optimised to validate large amounts
    of routes, e.g. all RPSL route(6)s in the DB.

    As a typical database includes several million route objects,
    this class builds a trie using datrie. All ROAs are then inserted
    into that tree. For each route to be validated, the tree is searched
    to find any matching ROAs.

    ROAs are inserted under a key that is a binary string representation of
    their prefix, including only network bits. For 192.0.2.0/24, the binary
    representation is 11000000000000000000001000000000, reducing this to
    network bits mean the key is 110000000000000000000010.
    As multiple ROAs may exist for the same prefix, the data under the
    110000000000000000000010 key is actually a list of tuples, each
    tuple representing a ROA.

    When searching for ROAs for a route, the entire network address
    is converted to binary, and also trimmed to network bits.
    E.g. for 192.0.2.0/25, this would be 1100000000000000000000100.
    The trie is then searched for any items that are a prefix (inclusive) of
    1100000000000000000000100, which includes 110000000000000000000010,
    the key for 192.0.2(.0). A ROA for 192.0.2.0/26 would have key
    11000000000000000000001000, and therefore will (and should)
    not be included in the validation process.
    """
    def __init__(self, dh: DatabaseHandler, roas: Optional[List[ROA]] = None):
        """
        Create a validator object. Can use either a list of ROA objects,
        or if not give, generates this from the database.
        Due to the overhead in preloading all ROAs, this is only effective
        when many routes have to be validated, otherwise it's more
        efficient to use SingleRouteROAValidator. The break even
        point is in the order of magnitude of checking 10.000 routes.
        """
        self.database_handler = dh
        # Pregenerated conversion from binary to binary strings for performance
        self._byte_bin = [bin(byte)[2:].zfill(8) for byte in range(256)]

        self.excluded_sources = get_setting('rpki.validation_excluded_sources', [])
        if isinstance(self.excluded_sources, str):
            self.excluded_sources = [self.excluded_sources]

        self.roa_tree = datrie.Trie('01')
        if roas is None:
            self._build_roa_tree_from_db()
        else:
            self._build_roa_tree_from_roa_objs(roas)

    def validate_all_routes(self, sources: List[str]=None) -> Tuple[Set[str], Set[str], Set[str]]:
        """
        Validate all RPSL route/route6 objects.

        Retrieves all routes from the DB, and aggregates the validation results.
        Returns a tuple of three sets of RPSL route PKs:
        - one with routes that should be set to status VALID, but are not now
        - one with routes that should be set to status INVALID, but are not now
        - one with routes that should be set to status UNKNOWN, but are not now

        Routes where their current validation status in the DB matches the new
        validation result, are not included in the return value.
        """
        columns = ['rpsl_pk', 'ip_first', 'prefix_length', 'asn_first', 'source', 'rpki_status']
        q = RPSLDatabaseQuery(column_names=columns, enable_ordering=False)
        q = q.object_classes(['route', 'route6'])
        if sources:
            q = q.sources(sources)
        routes = self.database_handler.execute_query(q)

        pks_changed: Dict[RPKIStatus, Set[str]] = defaultdict(set)

        for result in routes:
            # RPKI_IRR_PSEUDO_SOURCE objects are ROAs, and don't need validation.
            if result['source'] == RPKI_IRR_PSEUDO_SOURCE:
                continue

            rpsl_pk = result['rpsl_pk']
            current_status = result['rpki_status']
            new_status = self.validate_route(result['ip_first'], result['prefix_length'],
                                             result['asn_first'], result['source'])
            if new_status != current_status:
                pks_changed[new_status].add(rpsl_pk)

        return pks_changed[RPKIStatus.valid], pks_changed[RPKIStatus.invalid], pks_changed[RPKIStatus.unknown]

    def validate_route(self, prefix_ip: str, prefix_length: int, prefix_asn: int, source: str) -> RPKIStatus:
        """
        Validate a single route.

        A route is valid when at least one ROA is found that covers the prefix,
        with the same origin AS and a match on the max length in the ROA.
        A route is invalid when at least one ROA is found that covers the prefix,
        but none of the covering ROAs matched on both origin AS and max length.
        A route is unknown if no ROAs were found covering the prefix.
        """
        if source in self.excluded_sources:
            return RPKIStatus.unknown

        ip_bin_str = self._ip_to_binary_str(prefix_ip)

        roas_covering = self.roa_tree.prefix_items(ip_bin_str[:prefix_length])
        # print(f'Route {prefix_ip}/{prefix_length} {prefix_asn} covered by ROAs: {roas_covering}')
        if not roas_covering:
            # print('====UNKNOWN====')
            return RPKIStatus.unknown
        for key, value in roas_covering:
            for roa_prefix, roa_asn, roa_max_length in value:
                # print(f'Matching ROA {roa_prefix} {value} to prefix {prefix_asn} length {prefix_length}')
                if roa_asn != 0 and roa_asn == prefix_asn and prefix_length <= roa_max_length:
                    # print('====VALID====')
                    return RPKIStatus.valid
        # print('====INVALID====')
        return RPKIStatus.invalid

    def _build_roa_tree_from_roa_objs(self, roas: List[ROA]):
        """
        Build the tree of all ROAs from ROA objects.
        """
        for roa in roas:
            key = roa.prefix.strBin()[:roa.prefix.prefixlen()]
            if key in self.roa_tree:
                self.roa_tree[key].append((roa.prefix_str, roa.asn, roa.max_length))
            else:
                self.roa_tree[key] = [(roa.prefix_str, roa.asn, roa.max_length)]

    def _build_roa_tree_from_db(self):
        """
        Build the tree of all ROAs from the DB.
        """
        roas = self.database_handler.execute_query(ROADatabaseObjectQuery())
        for roa in roas:
            first_ip, length = roa['prefix'].split('/')
            ip_bin_str = self._ip_to_binary_str(first_ip)
            key = ip_bin_str[:int(length)]
            if key in self.roa_tree:
                self.roa_tree[key].append((roa['prefix'], roa['asn'], roa['max_length']))
            else:
                self.roa_tree[key] = [(roa['prefix'], roa['asn'], roa['max_length'])]

    def _ip_to_binary_str(self, ip: str) -> str:
        """
        Convert an IP string to a binary string, e.g.
        192.0.2.139 to 11000000000000000000001010001011.
        """
        address_family = socket.AF_INET6 if ':' in ip else socket.AF_INET
        ip_bin = socket.inet_pton(address_family, ip)
        ip_bin_str = ''.join([self._byte_bin[b] for b in ip_bin]) + '0'
        return ip_bin_str


class SingleRouteROAValidator:
    def __init__(self, database_handler: DatabaseHandler):
        self.database_handler = database_handler

        self.excluded_sources = get_setting('rpki.validation_excluded_sources', [])
        if isinstance(self.excluded_sources, str):
            self.excluded_sources = [self.excluded_sources]

    def validate_route(self, route: IP, asn: int, source: str) -> RPKIStatus:
        """
        Validate a route from a particular source.
        """
        if source in self.excluded_sources:
            return RPKIStatus.unknown

        query = ROADatabaseObjectQuery().ip_less_specific_or_exact(route)
        roas_covering = list(self.database_handler.execute_query(query))
        if not roas_covering:
            return RPKIStatus.unknown
        for roa in roas_covering:
            if roa['asn'] != 0 and roa['asn'] == asn and route.prefixlen() <= roa['max_length']:
                return RPKIStatus.valid
        return RPKIStatus.invalid
