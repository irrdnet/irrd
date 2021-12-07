import pytest
from unittest.mock import Mock

from irrd.rpsl.rpsl_objects import RPSLMntner
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery
from irrd.utils.rpsl_samples import SAMPLE_MNTNER
from irrd.utils.test_utils import flatten_mock_calls
from ..suspension import suspend_for_mntner


class TestSuspension:

    def test_suspend_for_mntner(self, monkeypatch, config_override):
        mock_database_handler = Mock(spec=DatabaseHandler)
        mock_database_query = Mock(spec=RPSLDatabaseQuery)
        monkeypatch.setattr("irrd.updates.suspension.RPSLDatabaseQuery", mock_database_query)

        mntner = RPSLMntner(SAMPLE_MNTNER)
        query_results = iter([
            [
                {
                    'pk': 'pk_suspend',
                    'rpsl_pk': 'rpsl_pk_suspend',
                    'parsed_data': {'mnt-by': [mntner.pk()]},
                    'object_text': 'text',
                    'created': 'created',
                    'updated': 'updated',
                },
                {
                    'pk': 'pk_skip',
                    'rpsl_pk': 'rpsl_pk_skip',
                    'parsed_data': {'mnt-by': [mntner.pk(), 'OTHER-MNT']},
                    'object_text': 'text',
                    'created': 'created',
                    'updated': 'updated',
                },
                {
                    'pk': 'pk_skip2',
                    'rpsl_pk': 'rpsl_pk_skip2',
                    'parsed_data': {'mnt-by': [mntner.pk(), 'OTHER-MNT']},
                    'object_text': 'text',
                    'created': 'created',
                    'updated': 'updated',
                },
                {
                    'pk': 'pk_suspend2',
                    'rpsl_pk': 'rpsl_pk_suspend2',
                    'parsed_data': {'mnt-by': [mntner.pk(), 'INACTIVE-MNT']},
                    'object_text': 'text',
                    'created': 'created',
                    'updated': 'updated',
                },
            ],
            # query for OTHER-MNT:
            [{'pk': 'OTHER-MNT'}],
            # query for INACTIVE-MNT
            [],
        ])
        mock_database_handler.execute_query = lambda q: next(query_results)

        with pytest.raises(ValueError) as ve:
            list(suspend_for_mntner(mock_database_handler, mntner))
        assert 'authoritative' in str(ve)

        config_override({'sources': {'TEST': {'authoritative': True}}})
        results = list(suspend_for_mntner(mock_database_handler, mntner))
        assert len(results) == 2
        assert results[0]['pk'] == 'pk_suspend'
        assert results[1]['pk'] == 'pk_suspend2'

        assert(flatten_mock_calls(mock_database_handler)) == [
            ['suspend_rpsl_object', ('pk_suspend',), {}],
            ['suspend_rpsl_object', ('pk_suspend2',), {}]
        ]
        assert(flatten_mock_calls(mock_database_query)) == [
            ['', (), {'column_names': ['pk', 'rpsl_pk', 'parsed_data']}],
            ['sources', (['TEST'],), {}],
            ['lookup_attr', ('mnt-by', 'TEST-MNT'), {}],
            ['', (), {'column_names': ['pk']}],
            ['sources', (['TEST'],), {}],
            ['rpsl_pk', ('OTHER-MNT',), {}],
            ['first_only', (), {}],
            ['', (), {'column_names': ['pk']}],
            ['sources', (['TEST'],), {}],
            ['rpsl_pk', ('INACTIVE-MNT',), {}],
            ['first_only', (), {}],
        ]
