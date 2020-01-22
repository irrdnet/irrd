import pytest
import ujson

import textwrap
from IPy import IP
from unittest.mock import Mock

from irrd.conf import RPKI_IRR_PSEUDO_SOURCE
from irrd.rpki.status import RPKIStatus
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery, ROADatabaseObjectQuery
from irrd.utils.test_utils import flatten_mock_calls
from ..parser import ROADataImporter, ROAParserException, BulkRouteRoaValidator, ROA, SingleRouteRoaValidator


class TestROAImportProcess:
    def test_valid_process(self, monkeypatch):
        # Note that this test does not mock RPSLObjectFromROA, used
        # for generating the pseudo-IRR object, or the ROA class itself.

        mock_dh = Mock(spec=DatabaseHandler)

        data = ujson.dumps({
            "roas": [{
                "asn": "AS64496",
                "prefix": "192.0.2.0/24",
                "maxLength": 26,
                "ta": "APNIC RPKI Root"
            }, {
                "asn": "AS64497",
                "prefix": "2001:db8::/32",
                "maxLength": 40,
                "ta": "RIPE NCC RPKI Root"
            }]
        })
        roa_importer = ROADataImporter(data, mock_dh)
        assert flatten_mock_calls(mock_dh, flatten_objects=True) == [
            ['insert_roa_object', (),
                {'ip_version': 4, 'prefix_str': '192.0.2.0/24', 'asn': 64496,
                 'max_length': 26, 'trust_anchor': 'APNIC RPKI Root'}],
            ['upsert_rpsl_object', ('route/192.0.2.0/24AS64496/ML26/RPKI',), {'rpsl_safe_insert_only': True}],
            ['insert_roa_object', (),
                {'ip_version': 6, 'prefix_str': '2001:db8::/32', 'asn': 64497,
                 'max_length': 40, 'trust_anchor': 'RIPE NCC RPKI Root'}],
            ['upsert_rpsl_object', ('route6/2001:db8::/32AS64497/ML40/RPKI',), {'rpsl_safe_insert_only': True}],
        ]

        assert roa_importer.roa_objs[0]._rpsl_object.source() == RPKI_IRR_PSEUDO_SOURCE
        assert roa_importer.roa_objs[0]._rpsl_object.render_rpsl_text() == textwrap.dedent("""
            route:          192.0.2.0/24
            descr:          RPKI ROA for 192.0.2.0/24 / AS64496
            remarks:        This route object represents routing data retrieved from the RPKI
            remarks:        The original data can be found here: https://rpki.gin.ntt.net/r/AS64496/192.0.2.0/24
            remarks:        This route object is the result of an automated RPKI-to-IRR conversion process
            remarks:        performed by IRRd.
            remarks:        maxLength 26
            origin:         AS64496
            source:         RPKI  # Trust Anchor: APNIC RPKI Root
            """).strip() + '\n'

    def test_invalid_json(self, monkeypatch):
        mock_dh = Mock(spec=DatabaseHandler)

        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter('invalid', mock_dh)

        assert 'Unable to parse ROA input: invalid JSON: Expected object or value' in str(rpe)

        data = ujson.dumps({'invalid root': 42})
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, mock_dh)
        assert 'Unable to parse ROA input: root key "roas" not found' in str(rpe)

        assert flatten_mock_calls(mock_dh) == []

    def test_invalid_data_in_roa(self, monkeypatch):
        mock_dh = Mock(spec=DatabaseHandler)

        data = ujson.dumps({
            "roas": [{
                "asn": "AS64496",
                "prefix": "192.0.2.999/24",
                "maxLength": 26,
                "ta": "APNIC RPKI Root"
            }]
        })
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, mock_dh)
        assert "Invalid value in ROA: '192.0.2.999': single byte must be 0 <= byte < 256" in str(rpe)

        data = ujson.dumps({
            "roas": [{
                "asn": "ASx",
                "prefix": "192.0.2.0/24",
                "maxLength": 24,
                "ta": "APNIC RPKI Root"
            }]
        })
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, mock_dh)
        assert 'Invalid AS number ASX: number part is not numeric' in str(rpe)

        data = ujson.dumps({
            "roas": [{
                "prefix": "192.0.2.0/24",
                "maxLength": 24,
                "ta": "APNIC RPKI Root"
            }]
        })
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, mock_dh)
        assert "Unable to parse ROA record: missing key 'asn'" in str(rpe)

        data = ujson.dumps({
            "roas": [{
                "asn": "AS64496",
                "prefix": "192.0.2.0/24",
                "maxLength": 22,
                "ta": "APNIC RPKI Root"
            }]
        })
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, mock_dh)
        assert 'Invalid ROA: prefix size 24 is smaller than max length 22' in str(rpe)

        assert flatten_mock_calls(mock_dh) == []


class TestBulkRouteRoaValidator:
    def test_validate_routes(self, monkeypatch, config_override):
        config_override({
            'sources': {'TEST1': {}, 'TEST2': {}, RPKI_IRR_PSEUDO_SOURCE: {}}
        })
        mock_dh = Mock(spec=DatabaseHandler)
        mock_dq = Mock(spec=RPSLDatabaseQuery)
        monkeypatch.setattr('irrd.rpki.parser.RPSLDatabaseQuery',
                            lambda column_names, enable_ordering: mock_dq)

        mock_query_result = [
            {
                'rpsl_pk': 'pk_route_v4_d0_l24',
                'ip_version': 4,
                'ip_first': '192.0.2.0',
                'prefix_length': 24,
                'asn_first': 65546,
                'source': 'TEST1',
            },
            {
                'rpsl_pk': 'pk_route_v4_d0_l25',
                'ip_version': 4,
                'ip_first': '192.0.2.0',
                'prefix_length': 25,
                'asn_first': 65546,
                'source': 'TEST1',
            },
            {
                'rpsl_pk': 'pk_route_v4_d64_l32',
                'ip_version': 4,
                'ip_first': '192.0.2.64',
                'prefix_length': 32,
                'asn_first': 65546,
                'source': 'TEST1',
            },
            {
                'rpsl_pk': 'pk_route_v4_d128_l25',
                'ip_version': 4,
                'ip_first': '192.0.2.128',
                'prefix_length': 25,
                'asn_first': 65547,
                'source': 'TEST1',
            },
            {
                # RPKI invalid, but should be ignored.
                'rpsl_pk': 'pk_route_v4_d128_l26',
                'ip_version': 4,
                'ip_first': '192.0.2.128',
                'prefix_length': 26,
                'asn_first': 65547,
                'source': RPKI_IRR_PSEUDO_SOURCE,
            },
            {
                'rpsl_pk': 'pk_route_v6',
                'ip_version': 6,
                'ip_first': '2001:db8::',
                'prefix_length': 32,
                'asn_first': 65547,
                'source': 'TEST1',
            },
            {
                'rpsl_pk': 'pk_route_v4_no_roa',
                'ip_version': 4,
                'ip_first': '198.51.100.0',
                'prefix_length': 24,
                'asn_first': 65547,
                'source': 'TEST1',
            },
            {
                'rpsl_pk': 'pk_route_v4_roa_as0',
                'ip_version': 4,
                'ip_first': '203.0.113.1',
                'prefix_length': 32,
                'asn_first': 0,
                'source': 'TEST1',
            },
        ]
        mock_dh.execute_query = lambda query: mock_query_result

        roas = [
            # Valid for pk_route_v4_d0_l25 and pk_route_v4_d0_l24
            # - the others have incorrect origin or are too small.
            ROA('192.0.2.0/24', 'AS65546', '28', 'TEST TA'),
            # Matches the origin of pk_route_v4_d128_l25,
            # but not max_length.
            ROA('192.0.2.0/24', 'AS65547', '24', 'TEST TA'),
            # Matches pk_route_v6, but not max_length.
            ROA('2001:db8::/30', 'AS65547', '30', 'TEST TA'),
            # Matches pk_route_v6, but not on origin.
            ROA('2001:db8::/32', 'AS65548', '32', 'TEST TA'),
            # Matches pk_route_v6
            ROA('2001:db8::/32', 'AS65547', '64', 'TEST TA'),
            # Matches no routes, no effect
            ROA('203.0.113.0/32', 'AS65547', '32', 'TEST TA'),
            # AS0 can not match
            ROA('203.0.113.1/32', 'AS0', '32', 'TEST TA'),
        ]
        valid_pks, invalid_pks = BulkRouteRoaValidator(roas).validate_all_routes(mock_dh, sources=['TEST1'])
        assert valid_pks == {'pk_route_v6', 'pk_route_v4_d0_l25', 'pk_route_v4_d0_l24'}
        assert invalid_pks == {'pk_route_v4_d64_l32', 'pk_route_v4_d128_l25', 'pk_route_v4_roa_as0'}

        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['sources', (['TEST1'],), {}]
        ]


class TestSingleRouteRoaValidator:
    def test_validator_normal_roa(self, monkeypatch):
        mock_dh = Mock(spec=DatabaseHandler)
        mock_rq = Mock(spec=ROADatabaseObjectQuery)
        monkeypatch.setattr('irrd.rpki.parser.ROADatabaseObjectQuery', lambda: mock_rq)

        roa_response = [{
            'asn': 65548,
            'max_length': 25,
        }]
        mock_dh.execute_query = lambda q: roa_response

        validator = SingleRouteRoaValidator(mock_dh)
        assert validator.validate_route(IP('192.0.2.0/24'), 65548) == RPKIStatus.valid
        assert validator.validate_route(IP('192.0.2.0/24'), 65549) == RPKIStatus.invalid
        assert validator.validate_route(IP('192.0.2.0/26'), 65548) == RPKIStatus.invalid

        assert flatten_mock_calls(mock_rq) == [
            ['ip_less_specific_or_exact', (IP('192.0.2.0/24'),), {}],
            ['ip_less_specific_or_exact', (IP('192.0.2.0/24'),), {}],
            ['ip_less_specific_or_exact', (IP('192.0.2.0/26'),), {}],
        ]

    def test_validator_as0_roa(self, monkeypatch):
        mock_dh = Mock(spec=DatabaseHandler)
        mock_rq = Mock(spec=ROADatabaseObjectQuery)
        monkeypatch.setattr('irrd.rpki.parser.ROADatabaseObjectQuery', lambda: mock_rq)

        roa_response = [{
            'asn': 0,
            'max_length': 25,
        }]
        mock_dh.execute_query = lambda q: roa_response

        validator = SingleRouteRoaValidator(mock_dh)
        assert validator.validate_route(IP('192.0.2.0/24'), 65548) == RPKIStatus.invalid

    def test_validator_no_matching_roa(self, monkeypatch):
        mock_dh = Mock(spec=DatabaseHandler)
        mock_rq = Mock(spec=ROADatabaseObjectQuery)
        monkeypatch.setattr('irrd.rpki.parser.ROADatabaseObjectQuery', lambda: mock_rq)

        mock_dh.execute_query = lambda q: []

        validator = SingleRouteRoaValidator(mock_dh)
        assert validator.validate_route(IP('192.0.2.0/24'), 65548) == RPKIStatus.unknown
        assert validator.validate_route(IP('192.0.2.0/24'), 65549) == RPKIStatus.unknown
        assert validator.validate_route(IP('192.0.2.0/26'), 65548) == RPKIStatus.unknown
