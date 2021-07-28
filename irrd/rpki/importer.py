from collections import defaultdict

import ujson

import logging
from IPy import IP, IPSet
from typing import List, Optional, Dict, Set

from irrd.conf import RPKI_IRR_PSEUDO_SOURCE, get_setting
from irrd.rpki.status import RPKIStatus
from irrd.rpsl.parser import RPSLObject, RPSL_ATTRIBUTE_TEXT_WIDTH
from irrd.rpsl.rpsl_objects import RPSL_ROUTE_OBJECT_CLASS_FOR_IP_VERSION
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import JournalEntryOrigin
from irrd.utils.validators import parse_as_number

SLURM_TRUST_ANCHOR = 'SLURM file'

logger = logging.getLogger(__name__)


class ROAParserException(Exception):  # noqa: N818
    pass


class ROADataImporter:
    """
    Importer for ROAs.

    Loads all ROAs from the JSON data in the rpki_json_str parameter.
    If a slurm_json_str is provided, it is used to filter/amend the ROAs.

    Expects all existing ROA and pseudo-IRR objects to be deleted
    already, e.g. with:
        database_handler.delete_all_roa_objects()
        database_handler.delete_all_rpsl_objects_with_journal(RPKI_IRR_PSEUDO_SOURCE)
    """
    def __init__(self, rpki_json_str: str, slurm_json_str: Optional[str],
                 database_handler: DatabaseHandler):
        self.roa_objs: List[ROA] = []
        self._filtered_asns: Set[int] = set()
        self._filtered_prefixes: IPSet = IPSet()
        self._filtered_combined: Dict[int, IPSet] = defaultdict(IPSet)

        self._load_roa_dicts(rpki_json_str)
        if slurm_json_str:
            self._load_slurm(slurm_json_str)

        scopefilter_validator = ScopeFilterValidator()

        for roa_dict in self._roa_dicts:
            try:
                _, asn = parse_as_number(roa_dict['asn'], permit_plain=True)
                prefix = IP(roa_dict['prefix'])
                ta = roa_dict['ta']
                if ta != SLURM_TRUST_ANCHOR:
                    if asn in self._filtered_asns:
                        continue
                    if any([prefix in self._filtered_prefixes]):
                        continue
                    if any([prefix in self._filtered_combined.get(asn, [])]):
                        continue

                roa_obj = ROA(prefix, asn, roa_dict['maxLength'], ta)
            except KeyError as ke:
                msg = f'Unable to parse ROA record: missing key {ke} -- full record: {roa_dict}'
                logger.error(msg)
                raise ROAParserException(msg)
            except ValueError as ve:
                msg = f'Invalid value in ROA or SLURM: {ve}'
                logger.error(msg)
                raise ROAParserException(msg)

            roa_obj.save(database_handler, scopefilter_validator)
            self.roa_objs.append(roa_obj)

    def _load_roa_dicts(self, rpki_json_str: str) -> None:
        """Load the ROAs from the JSON string into self._roa_dicts"""
        try:
            self._roa_dicts = ujson.loads(rpki_json_str)['roas']
        except ValueError as error:
            msg = f'Unable to parse ROA input: invalid JSON: {error}'
            logger.error(msg)
            raise ROAParserException(msg)
        except KeyError:
            msg = 'Unable to parse ROA input: root key "roas" not found'
            logger.error(msg)
            raise ROAParserException(msg)

    def _load_slurm(self, slurm_json_str: str):
        """
        Load and apply the SLURM in the provided JSON string.

        Prefix filters are loaded into three instance variables:
        - self._filtered_asns: a set of ASNs (in "ASxxx" format) that
          should be filtered, i.e. any ROA with this asn is discarded
        - self._filtered_prefixes: a set of prefixes (as IP instances)
          that should be filtered, i.e. any ROA matching or more specific
          of a prefix in this set should be discarded
        - self._filtered_combined: a dict with ASNs as keys, sets of
          prefixes as values, that should be filered. Any ROA matching
          that ASN and having a prefix that matches or is more specific,
          should be discarded

        Prefix assertions are directly loaded into self._roa_dicts.
        This must be called after _load_roa_dicts()
        """
        slurm = ujson.loads(slurm_json_str)
        version = slurm.get('slurmVersion')
        if version != 1:
            msg = f'SLURM data has invalid version: {version}'
            logger.error(msg)
            raise ROAParserException(msg)

        filters = slurm.get('validationOutputFilters', {}).get('prefixFilters', [])
        for item in filters:
            if 'asn' in item and 'prefix' not in item:
                self._filtered_asns.add(int(item['asn']))
            if 'asn' not in item and 'prefix' in item:
                self._filtered_prefixes.add(IP(item['prefix']))
            if 'asn' in item and 'prefix' in item:
                self._filtered_combined[int(item['asn'])].add(IP(item['prefix']))

        assertions = slurm.get('locallyAddedAssertions', {}).get('prefixAssertions', [])
        for assertion in assertions:
            max_length = assertion.get('maxPrefixLength')
            if max_length is None:
                max_length = IP(assertion['prefix']).prefixlen()
            self._roa_dicts.append({
                'asn': 'AS' + str(assertion['asn']),
                'prefix': assertion['prefix'],
                'maxLength': max_length,
                'ta': SLURM_TRUST_ANCHOR,
            })


class ROA:
    """
    Representation of a ROA.

    This is used when (re-)importing all ROAs, to save the data to the DB,
    and by the BulkRouteROAValidator when validating all existing routes.
    """
    def __init__(self, prefix: IP, asn: int, max_length: str, trust_anchor: str):
        try:
            self.prefix = prefix
            self.prefix_str = str(prefix)
            self.asn = asn
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

    def save(self, database_handler: DatabaseHandler, scopefilter_validator: ScopeFilterValidator):
        """
        Save the ROA object to the DB, create a pseudo-IRR object, and save that too.
        """
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
            scopefilter_validator=scopefilter_validator,
        )
        database_handler.upsert_rpsl_object(self._rpsl_object, JournalEntryOrigin.pseudo_irr,
                                            rpsl_guaranteed_no_existing=True)


class RPSLObjectFromROA(RPSLObject):
    """
    This is an RPSLObject compatible class that represents
    an RPKI pseudo-IRR object. It overrides the API in
    relevant parts.
    """
    # noinspection PyMissingConstructor
    def __init__(self, prefix: IP, prefix_str: str, asn: int, max_length: int, trust_anchor: str,
                 scopefilter_validator: ScopeFilterValidator):
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
        self.rpki_status = RPKIStatus.valid
        self.parsed_data = {
            self.rpsl_object_class: self.prefix_str,
            'origin': 'AS' + str(self.asn),
            'source': RPKI_IRR_PSEUDO_SOURCE,
            'rpki_max_length': max_length,
        }
        self.scopefilter_status, _ = scopefilter_validator.validate_rpsl_object(self)

    def source(self):
        return RPKI_IRR_PSEUDO_SOURCE

    def pk(self):
        return f'{self.prefix_str}AS{self.asn}/ML{self.max_length}'

    def render_rpsl_text(self, last_modified=None):
        object_class_display = f'{self.rpsl_object_class}:'.ljust(RPSL_ATTRIBUTE_TEXT_WIDTH)
        remarks_fill = RPSL_ATTRIBUTE_TEXT_WIDTH * ' '
        remarks = get_setting('rpki.pseudo_irr_remarks').replace('\n', '\n' + remarks_fill).strip()
        remarks = remarks.format(asn=self.asn, prefix=self.prefix_str)
        rpsl_object_text = f"""
{object_class_display}{self.prefix_str}
descr:          RPKI ROA for {self.prefix_str} / AS{self.asn}
remarks:        {remarks}
max-length:     {self.max_length}
origin:         AS{self.asn}
source:         {RPKI_IRR_PSEUDO_SOURCE}  # Trust Anchor: {self.trust_anchor}
""".strip() + '\n'
        return rpsl_object_text
