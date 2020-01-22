import ujson

import logging
import textwrap
from IPy import IP
from typing import List

from irrd.conf import RPKI_IRR_PSEUDO_SOURCE
from irrd.rpsl.parser import RPSLObject, RPSL_ATTRIBUTE_TEXT_WIDTH
from irrd.rpsl.rpsl_objects import RPSL_ROUTE_OBJECT_CLASS_FOR_IP_VERSION
from irrd.storage.database_handler import DatabaseHandler
from irrd.utils.validators import parse_as_number

logger = logging.getLogger(__name__)


class ROAParserException(Exception):
    pass


class ROADataImporter:
    """
    Importer for ROAs.

    Loads all ROAs from the JSON data in the json_str parameter.
    Expects all existing ROA and pseudo-IRR objects to be deleted
    already, e.g. with:
        database_handler.delete_all_roa_objects()
        database_handler.delete_all_rpsl_objects_with_journal(RPKI_IRR_PSEUDO_SOURCE)
    """
    def __init__(self, json_str: str, database_handler: DatabaseHandler):
        self.roa_objs: List[ROA] = []
        try:
            roa_dicts = ujson.loads(json_str)['roas']
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
    """
    Representation of a ROA.

    This is used when (re-)importing all ROAs, to save the data to the DB,
    and by the BulkRouteROAValidator when validating all existing routes.
    """
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
        )
        database_handler.upsert_rpsl_object(self._rpsl_object, rpsl_safe_insert_only=True)


class RPSLObjectFromROA(RPSLObject):
    """
    This is an RPSLObject compatible class that represents
    an RPKI pseudo-IRR object. It overrides the API in
    relevant parts.
    """
    # noinspection PyMissingConstructor
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
            remarks:        This route object represents routing data retrieved
            remarks:        from the RPKI. The original data can be found here:
            remarks:        https://rpki.gin.ntt.net/r/AS{self.asn}/{self.prefix_str}
            remarks:        This route object is the result of an automated
            remarks:        RPKI-to-IRR conversion process performed by IRRd.
            remarks:        maxLength {self.max_length}
            origin:         AS{self.asn}
            source:         {RPKI_IRR_PSEUDO_SOURCE}  # Trust Anchor: {self.trust_anchor}
            """).strip() + '\n'
        return rpsl_object_text
