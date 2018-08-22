from unittest.mock import Mock

from irrd.conf import DEFAULT_SETTINGS
from irrd.storage.models import DatabaseOperation
from irrd.utils.rpsl_samples import SAMPLE_MNTNER, SAMPLE_UNKNOWN_CLASS, SAMPLE_MALFORMED_EMPTY_LINE
from ..operation import NRTMOperation


class TestNRTMOperation:

    def test_nrtm_add_valid(self):
        DEFAULT_SETTINGS['sources'] = {'TEST': {}}
        mock_dh = Mock()

        operation = NRTMOperation(
            source='TEST',
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            object_text=SAMPLE_MNTNER,
            object_class_filter=['route', 'route6', 'mntner'],
        )
        assert operation.save(database_handler=mock_dh)

        assert mock_dh.upsert_rpsl_object.call_count == 1
        assert mock_dh.mock_calls[0][1][0].pk() == 'TEST-MNT'
        assert mock_dh.mock_calls[0][1][1] == 42424242

    def test_nrtm_add_valid_ignored_object_class(self):
        DEFAULT_SETTINGS['sources'] = {'TEST': {}}
        mock_dh = Mock()

        operation = NRTMOperation(
            source='TEST',
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            object_text=SAMPLE_MNTNER,
            object_class_filter=['route', 'route6'],
        )
        assert not operation.save(database_handler=mock_dh)
        assert mock_dh.upsert_rpsl_object.call_count == 0

    def test_nrtm_delete_valid(self):
        DEFAULT_SETTINGS['sources'] = {'TEST': {}}
        mock_dh = Mock()

        operation = NRTMOperation(
            source='TEST',
            operation=DatabaseOperation.delete,
            serial=42424242,
            object_text=SAMPLE_MNTNER,
        )
        assert operation.save(database_handler=mock_dh)

        assert mock_dh.delete_rpsl_object.call_count == 1
        assert mock_dh.mock_calls[0][1][0].pk() == 'TEST-MNT'
        assert mock_dh.mock_calls[0][1][1] == 42424242

    def test_nrtm_add_invalid_unknown_object_class(self):
        DEFAULT_SETTINGS['sources'] = {'TEST': {}}
        mock_dh = Mock()

        operation = NRTMOperation(
            source='TEST',
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            object_text=SAMPLE_UNKNOWN_CLASS,
        )
        assert not operation.save(database_handler=mock_dh)
        assert mock_dh.upsert_rpsl_object.call_count == 0

    def test_nrtm_add_invalid_inconsistent_source(self):
        DEFAULT_SETTINGS['sources'] = {'TEST': {}}
        mock_dh = Mock()

        operation = NRTMOperation(
            source='NOT-TEST',
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            object_text=SAMPLE_MNTNER,
        )
        assert not operation.save(database_handler=mock_dh)
        assert mock_dh.upsert_rpsl_object.call_count == 0

    def test_nrtm_add_invalid_rpsl_errors(self):
        DEFAULT_SETTINGS['sources'] = {'TEST': {}}
        mock_dh = Mock()

        operation = NRTMOperation(
            source='TEST',
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            object_text=SAMPLE_MALFORMED_EMPTY_LINE,
        )
        assert not operation.save(database_handler=mock_dh)
        assert mock_dh.upsert_rpsl_object.call_count == 0
