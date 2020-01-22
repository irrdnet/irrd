from IPy import IP
from unittest.mock import Mock

from irrd.conf import RPKI_IRR_PSEUDO_SOURCE
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery, ROADatabaseObjectQuery
from irrd.utils.test_utils import flatten_mock_calls
from ..importer import ROA
from ..status import RPKIStatus
from ..validators import BulkRouteROAValidator, SingleRouteROAValidator


class TestBulkRouteROAValidator:
    def test_validate_routes_from_roa_objs(self, monkeypatch, config_override):
        config_override({
            'rpki': {'validation_excluded_sources': 'SOURCE-EXCLUDED'},
            'sources': {'TEST1': {}, 'TEST2': {}, RPKI_IRR_PSEUDO_SOURCE: {}}
        })
        mock_dh = Mock(spec=DatabaseHandler)
        mock_dq = Mock(spec=RPSLDatabaseQuery)
        monkeypatch.setattr('irrd.rpki.validators.RPSLDatabaseQuery',
                            lambda column_names, enable_ordering: mock_dq)

        mock_query_result = [
            {
                'rpsl_pk': 'pk_route_v4_d0_l24',
                'ip_version': 4,
                'ip_first': '192.0.2.0',
                'prefix_length': 24,
                'asn_first': 65546,
                'rpki_status': RPKIStatus.unknown,
                'source': 'TEST1',
            },
            {
                'rpsl_pk': 'pk_route_v4_d0_l25',
                'ip_version': 4,
                'ip_first': '192.0.2.0',
                'prefix_length': 25,
                'asn_first': 65546,
                'rpki_status': RPKIStatus.unknown,
                'source': 'TEST1',
            },
            {
                # This route is valid, but as the state is already valid,
                # it should not be included in the response.
                'rpsl_pk': 'pk_route_v4_d0_l28',
                'ip_version': 4,
                'ip_first': '192.0.2.0',
                'prefix_length': 27,
                'asn_first': 65546,
                'rpki_status': RPKIStatus.valid,
                'source': 'TEST1',
            },
            {
                'rpsl_pk': 'pk_route_v4_d64_l32',
                'ip_version': 4,
                'ip_first': '192.0.2.64',
                'prefix_length': 32,
                'asn_first': 65546,
                'rpki_status': RPKIStatus.valid,
                'source': 'TEST1',
            },
            {
                'rpsl_pk': 'pk_route_v4_d128_l25',
                'ip_version': 4,
                'ip_first': '192.0.2.128',
                'prefix_length': 25,
                'asn_first': 65547,
                'rpki_status': RPKIStatus.valid,
                'source': 'TEST1',
            },
            {
                # RPKI invalid, but should be ignored.
                'rpsl_pk': 'pk_route_v4_d128_l26',
                'ip_version': 4,
                'ip_first': '192.0.2.128',
                'prefix_length': 26,
                'asn_first': 65547,
                'rpki_status': RPKIStatus.invalid,
                'source': RPKI_IRR_PSEUDO_SOURCE,
            },
            {
                # RPKI invalid, but should be unknown because of source.
                'rpsl_pk': 'pk_route_v4_d128_l26_excluded',
                'ip_version': 4,
                'ip_first': '192.0.2.128',
                'prefix_length': 26,
                'asn_first': 65547,
                'rpki_status': RPKIStatus.valid,
                'source': 'SOURCE-EXCLUDED',
            },
            {
                'rpsl_pk': 'pk_route_v6',
                'ip_version': 6,
                'ip_first': '2001:db8::',
                'prefix_length': 32,
                'asn_first': 65547,
                'rpki_status': RPKIStatus.invalid,
                'source': 'TEST1',
            },
            {
                # Should not match any ROA - ROAs for a subset
                # exist, but those should not be included
                'rpsl_pk': 'pk_route_v4_no_roa',
                'ip_version': 4,
                'ip_first': '192.0.2.0',
                'prefix_length': 23,
                'asn_first': 65549,
                'rpki_status': RPKIStatus.valid,
                'source': 'TEST1',
            },
            {
                'rpsl_pk': 'pk_route_v4_roa_as0',
                'ip_version': 4,
                'ip_first': '203.0.113.1',
                'prefix_length': 32,
                'asn_first': 65547,
                'rpki_status': RPKIStatus.unknown,
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
        result = BulkRouteROAValidator(mock_dh, roas).validate_all_routes(sources=['TEST1'])
        new_valid_pks, new_invalid_pks, new_unknown_pks = result
        assert new_valid_pks == {'pk_route_v6', 'pk_route_v4_d0_l25', 'pk_route_v4_d0_l24'}
        assert new_invalid_pks == {'pk_route_v4_d64_l32', 'pk_route_v4_d128_l25', 'pk_route_v4_roa_as0'}
        assert new_unknown_pks == {'pk_route_v4_no_roa', 'pk_route_v4_d128_l26_excluded'}

        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['sources', (['TEST1'],), {}]
        ]

    def test_validate_routes_with_roa_from_database(self, monkeypatch, config_override):
        config_override({
            'sources': {'TEST1': {}, 'TEST2': {}, RPKI_IRR_PSEUDO_SOURCE: {}}
        })
        mock_dh = Mock(spec=DatabaseHandler)
        mock_dq = Mock(spec=RPSLDatabaseQuery)
        monkeypatch.setattr('irrd.rpki.validators.RPSLDatabaseQuery',
                            lambda column_names, enable_ordering: mock_dq)
        mock_rq = Mock(spec=ROADatabaseObjectQuery)
        monkeypatch.setattr('irrd.rpki.validators.ROADatabaseObjectQuery',
                            lambda: mock_rq)

        mock_query_result = iter([
            [  # ROAs:
                {
                    'prefix': '192.0.2.0/24',
                    'asn': 65546,
                    'max_length': 25,
                },
                {
                    'prefix': '192.0.2.0/24',
                    'asn': 65547,
                    'max_length': 24,
                },
            ], [  # RPSL objects:
                {
                    'rpsl_pk': 'pk_route_v4_d0_l25',
                    'ip_version': 4,
                    'ip_first': '192.0.2.0',
                    'prefix_length': 25,
                    'asn_first': 65546,
                    'rpki_status': RPKIStatus.unknown,
                    'source': 'TEST1',
                },
            ]
        ])
        mock_dh.execute_query = lambda query: next(mock_query_result)

        result = BulkRouteROAValidator(mock_dh).validate_all_routes(sources=['TEST1'])
        new_valid_pks, new_invalid_pks, new_unknown_pks = result
        assert new_valid_pks == {'pk_route_v4_d0_l25'}
        assert new_invalid_pks == set()
        assert new_unknown_pks == set()

        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['sources', (['TEST1'],), {}]
        ]
        assert flatten_mock_calls(mock_rq) == []  # No filters applied


class TestSingleRouteROAValidator:
    def test_validator_normal_roa(self, monkeypatch, config_override):
        config_override({'rpki': {'validation_excluded_sources': 'SOURCE-EXCLUDED'}})
        mock_dh = Mock(spec=DatabaseHandler)
        mock_rq = Mock(spec=ROADatabaseObjectQuery)
        monkeypatch.setattr('irrd.rpki.validators.ROADatabaseObjectQuery', lambda: mock_rq)

        roa_response = [{
            'asn': 65548,
            'max_length': 25,
        }]
        mock_dh.execute_query = lambda q: roa_response

        validator = SingleRouteROAValidator(mock_dh)
        assert validator.validate_route(IP('192.0.2.0/24'), 65548, 'TEST1') == RPKIStatus.valid
        assert validator.validate_route(IP('192.0.2.0/24'), 65548, 'SOURCE-EXCLUDED') == RPKIStatus.unknown
        assert validator.validate_route(IP('192.0.2.0/24'), 65549, 'TEST1') == RPKIStatus.invalid
        assert validator.validate_route(IP('192.0.2.0/24'), 65549, 'SOURCE-EXCLUDED') == RPKIStatus.unknown
        assert validator.validate_route(IP('192.0.2.0/26'), 65548, 'TEST1') == RPKIStatus.invalid

        assert flatten_mock_calls(mock_rq) == [
            ['ip_less_specific_or_exact', (IP('192.0.2.0/24'),), {}],
            ['ip_less_specific_or_exact', (IP('192.0.2.0/24'),), {}],
            ['ip_less_specific_or_exact', (IP('192.0.2.0/26'),), {}],
        ]

    def test_validator_as0_roa(self, monkeypatch):
        mock_dh = Mock(spec=DatabaseHandler)
        mock_rq = Mock(spec=ROADatabaseObjectQuery)
        monkeypatch.setattr('irrd.rpki.validators.ROADatabaseObjectQuery', lambda: mock_rq)

        roa_response = [{
            'asn': 0,
            'max_length': 25,
        }]
        mock_dh.execute_query = lambda q: roa_response

        validator = SingleRouteROAValidator(mock_dh)
        assert validator.validate_route(IP('192.0.2.0/24'), 65548, 'TEST1') == RPKIStatus.invalid

    def test_validator_no_matching_roa(self, monkeypatch):
        mock_dh = Mock(spec=DatabaseHandler)
        mock_rq = Mock(spec=ROADatabaseObjectQuery)
        monkeypatch.setattr('irrd.rpki.validators.ROADatabaseObjectQuery', lambda: mock_rq)

        mock_dh.execute_query = lambda q: []

        validator = SingleRouteROAValidator(mock_dh)
        assert validator.validate_route(IP('192.0.2.0/24'), 65548, 'TEST1') == RPKIStatus.unknown
        assert validator.validate_route(IP('192.0.2.0/24'), 65549, 'TEST1') == RPKIStatus.unknown
        assert validator.validate_route(IP('192.0.2.0/26'), 65548, 'TEST1') == RPKIStatus.unknown
