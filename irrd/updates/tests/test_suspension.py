import pytest
from unittest.mock import Mock

from irrd.rpsl.rpsl_objects import RPSLMntner
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery
from irrd.utils.rpsl_samples import SAMPLE_MNTNER
from irrd.utils.test_utils import flatten_mock_calls
from irrd.updates.suspension import objects_for_suspended_mntner
from ..suspension import objects_for_suspended_mntner


class TestSuspensionResolver:

    def test_resolver_for_mntner(self, monkeypatch, config_override):
        mock_database_handler = Mock(spec=DatabaseHandler)
        mock_database_query = Mock(spec=RPSLDatabaseQuery)
        monkeypatch.setattr("irrd.updates.suspension.RPSLDatabaseQuery", mock_database_query)

        mntner = RPSLMntner(SAMPLE_MNTNER)
        mock_database_handler.execute_query = lambda q: [
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
        ]

        with pytest.raises(ValueError) as ve:
            list(objects_for_suspended_mntner(mock_database_handler, mntner))
        assert 'authoritative' in str(ve)

        config_override({'sources': {'TEST': {'authoritative': True}}})
        results = list(objects_for_suspended_mntner(mock_database_handler, mntner))
        assert len(results) == 1
        assert results[0]['pk'] == 'pk_suspend'

        assert(flatten_mock_calls(mock_database_query)) == [
            ['', (), {'column_names': ['pk', 'rpsl_pk', 'parsed_data', 'object_text', 'created', 'updated']}],
            ['sources', (['TEST'],), {}],
            ['lookup_attr', ('mnt-by', 'TEST-MNT'), {}],
        ]
