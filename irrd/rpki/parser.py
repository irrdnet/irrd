import codecs
import datrie
import logging
import socket
import textwrap
import ujson
from IPy import IP
from typing import List, Set, Optional, Tuple

from irrd.conf import RPKI_IRR_PSEUDO_SOURCE
from irrd.rpki.status import RPKIStatus
from irrd.rpsl.parser import RPSLObject, RPSL_ATTRIBUTE_TEXT_WIDTH
from irrd.rpsl.rpsl_objects import RPSL_ROUTE_OBJECT_CLASS_FOR_IP_VERSION
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery, ROADatabaseObjectQuery
from irrd.utils.validators import parse_as_number

decode_hex = codecs.getdecoder("hex_codec")
logger = logging.getLogger(__name__)

# TODO: refactor this file structure


class ROAParserException(Exception):
    pass


class ROADataImporter:
    def __init__(self, text: str, database_handler: DatabaseHandler):
        self.roa_objs: List[ROA] = []
        try:
            roa_dicts = ujson.loads(text)['roas']
        except ValueError as error:
            msg = f'Unable to parse ROA input: invalid JSON: {error}'
            logger.error(msg)
            raise ROAParserException(msg)
        except KeyError:
            msg = f'Unable to parse ROA input: root key "roas" not found'
            logger.error(msg)
            raise ROAParserException(msg)

        for roa_dict in roa_dicts:
            try:
                roa_obj = ROA(
                    roa_dict['prefix'],
                    roa_dict['asn'],
                    roa_dict['maxLength'],
                    roa_dict['ta'],
                )
            except KeyError as ke:
                msg = f'Unable to parse ROA record: missing key {ke} -- full record: {roa_dict}'
                logger.error(msg)
                raise ROAParserException(msg)

            roa_obj.save(database_handler)
            self.roa_objs.append(roa_obj)


class ROA:
    def __init__(self, prefix: str, asn: str, max_length: str, trust_anchor: str):
        try:
            self.prefix = IP(prefix)
            self.prefix_str = prefix
            _, self.asn = parse_as_number(asn)
            self.max_length = int(max_length)
            self.trust_anchor = trust_anchor
        except ValueError as ve:
            msg = f'Invalid value in ROA: {ve}'
            logger.error(msg)
            raise ROAParserException(msg)

        if self.max_length < self.prefix.prefixlen():
            msg = f'Invalid ROA: prefix size {self.prefix.prefixlen()} is smaller than max length {max_length} in ' \
                  f'ROA for {self.prefix} / AS{self.asn}'
            logger.error(msg)
            raise ROAParserException(msg)

    def save(self, database_handler: DatabaseHandler):
        database_handler.insert_roa_object(
            ip_version=self.prefix.version(),
            prefix_str=self.prefix_str,
            asn=self.asn,
            max_length=self.max_length,
            trust_anchor=self.trust_anchor,
        )
        self._rpsl_object = RPSLObjectFromROA(
            prefix=self.prefix,
            prefix_str=self.prefix_str,
            asn=self.asn,
            max_length=self.max_length,
            trust_anchor=self.trust_anchor,
        )
        database_handler.upsert_rpsl_object(self._rpsl_object, rpsl_safe_insert_only=True)


class RPSLObjectFromROA(RPSLObject):
    def __init__(self, prefix: IP, prefix_str: str, asn: int, max_length: int, trust_anchor: str):
        self.prefix = prefix
        self.prefix_str = prefix_str
        self.asn = asn
        self.max_length = max_length
        self.trust_anchor = trust_anchor

        self.rpsl_object_class = RPSL_ROUTE_OBJECT_CLASS_FOR_IP_VERSION[self.prefix.version()]
        self.ip_first = self.prefix.net()
        self.ip_last = self.prefix.broadcast()
        self.prefix_length = self.prefix.prefixlen()
        self.asn_first = asn
        self.asn_last = asn
        self.parsed_data = {
            self.rpsl_object_class: self.prefix_str,
            'origin': 'AS' + str(self.asn),
            'source': RPKI_IRR_PSEUDO_SOURCE,
        }

    def source(self):
        return RPKI_IRR_PSEUDO_SOURCE

    def pk(self):
        return f'{self.prefix_str}AS{self.asn}/ML{self.max_length}'

    def render_rpsl_text(self):
        # TODO: we could just have a max-length attribute?
        object_class_display = f'{self.rpsl_object_class}:'.ljust(RPSL_ATTRIBUTE_TEXT_WIDTH)
        rpsl_object_text = textwrap.dedent(f"""
            {object_class_display}{self.prefix_str}
            descr:          RPKI ROA for {self.prefix_str} / AS{self.asn}
            remarks:        This route object represents routing data retrieved from the RPKI
            remarks:        The original data can be found here: https://rpki.gin.ntt.net/r/AS{self.asn}/{self.prefix_str}
            remarks:        This route object is the result of an automated RPKI-to-IRR conversion process
            remarks:        performed by IRRd.
            remarks:        maxLength {self.max_length}
            origin:         AS{self.asn}
            source:         {RPKI_IRR_PSEUDO_SOURCE}  # Trust Anchor: {self.trust_anchor}
            """).strip() + '\n'
        return rpsl_object_text


class BulkRouteRoaValidator:
    """
    The bulk route validator is optimised to validate large amounts
    of routes, e.g. all RPSL route(6)s in the DB.

    As a typical database includes several million route objects,
    this class builds a trie using datrie. All ROAs are then inserted
    into that tree. For each route to be validated, the tree is searched
    to find any matching ROAs.

    ROAs are inserted under a key that is a binary representation of their
    prefix, including only network bits. For 192.0.2.0/24, the binary
    representation is 11000000000000000000001000000000, reducing this to
    network bits mean the key is 110000000000000000000010.
    As multiple ROAs may exist for the same prefix, the data under the
    110000000000000000000010 key is actually a list of tuples, each
    tuple representing a ROA.

    When searching for ROAs for a route, the entire network address
    is converted to binary. E.g. for 192.0.2.139, this would be
    11000000000000000000001010001011. The trie is then searched for
    any items that are a prefix of 11000000000000000000001010001011,
    which includes 110000000000000000000010, the key for 192.0.2(.0).
    """
    def __init__(self, dh: DatabaseHandler, roas: Optional[List[ROA]] = None):
        """
        Create a validator object. Can use either a list of ROA bojects,
        or if not give, generates this from the database.
        Due to the overhead in preloading all ROAs, this is only effective
        when many routes have to be validated, otherwise it's more
        efficient to use SingleRouteRoaValidator. The break even
        point is in the order of magnitude of checking 10.000 routes.
        """
        self.database_handler = dh
        # Pregenerated conversion from binary to binary strings for performance
        self._byte_bin = [bin(byte)[2:].zfill(8) for byte in range(256)]

        self.roa_tree = datrie.Trie('01')
        if roas is None:
            self._build_roa_tree_from_db()
        else:
            self._build_roa_tree_from_roa_objs(roas)

    def validate_all_routes(self, sources: List[str]=None) -> Tuple[Set[str], Set[str]]:
        """
        Validate all RPSL route/route6 objects.

        Retrieves all routes from the DB, and aggregates the validation results.
        Returns a tuple of two sets: one with RPSL pks of all valid routes,
        one with RPSL pks of all invalid routes. Routes not included in either
        have no known RPKI status.
        """
        q = RPSLDatabaseQuery(column_names=['rpsl_pk', 'ip_first', 'prefix_length', 'asn_first', 'source'], enable_ordering=False)
        q = q.object_classes(['route', 'route6'])
        if sources:
            q = q.sources(sources)
        routes = self.database_handler.execute_query(q)

        pks_valid = set()
        pks_invalid = set()

        for result in routes:
            # RPKI_IRR_PSEUDO_SOURCE objects are ROAs,
            # and don't need validation.
            if result['source'] == RPKI_IRR_PSEUDO_SOURCE:
                continue

            rpsl_pk = result['rpsl_pk']
            status = self._validate_route(result['ip_first'], result['prefix_length'], result['asn_first'])
            if status is True:
                pks_valid.add(rpsl_pk)
            elif status is False:
                pks_invalid.add(rpsl_pk)

        return pks_valid, pks_invalid

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

    # TODO: update to use RPKIStatus return values
    def _validate_route(self, prefix_ip, prefix_length, prefix_asn) -> Optional[bool]:
        """
        Validate a single route.

        Returns True for valid, False for invalid, None for unknown.
        A route is valid when at least one ROA is found that covers the prefix,
        with the same origin AS and a match on the max length in the ROA.
        A route is invalid when at least one ROA is found that covers the prefix,
        but none of the covering ROAs matched on both origin AS and max length.
        A route is unknown if no ROAs were found covering the prefix.
        """
        ip_bin_str = self._ip_to_binary_str(prefix_ip)

        roas_covering = self.roa_tree.prefix_items(ip_bin_str)
        # print(f'Route {prefix_ip}/{prefix_length} {prefix_asn} covered by ROAs: {roas_covering}')
        if not roas_covering:
            # print('====UNKNOWN====')
            return None
        for key, value in roas_covering:
            for roa_prefix, roa_asn, roa_max_length in value:
                # print(f'Matching ROA {roa_prefix} {value} to prefix {prefix_asn} length {prefix_length}')
                if roa_asn != 0 and roa_asn == prefix_asn and prefix_length <= roa_max_length:
                    # print('====VALID====')
                    return True
        # print('====INVALID====')
        return False

    def _ip_to_binary_str(self, ip: str) -> str:
        """
        Convert an IP string to a binary string, e.g.
        192.0.2.139 to 11000000000000000000001010001011.
        """
        address_family = socket.AF_INET6 if ':' in ip else socket.AF_INET
        ip_bin = socket.inet_pton(address_family, ip)
        ip_bin_str = ''.join([self._byte_bin[x] for x in ip_bin]) + '0'
        return ip_bin_str


class SingleRouteRoaValidator:
    def __init__(self, database_handler: DatabaseHandler):
        self.database_handler = database_handler

    def validate_route(self, route: IP, asn: int) -> RPKIStatus:
        """
        Validate a route.
        """
        query = ROADatabaseObjectQuery().ip_less_specific_or_exact(route)
        roas_covering = list(self.database_handler.execute_query(query))
        if not roas_covering:
            return RPKIStatus.unknown
        for roa in roas_covering:
            if roa['asn'] != 0 and roa['asn'] == asn and route.prefixlen() <= roa['max_length']:
                return RPKIStatus.valid
        return RPKIStatus.invalid
