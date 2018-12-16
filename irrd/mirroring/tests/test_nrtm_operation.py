from unittest.mock import Mock

from irrd.storage.models import DatabaseOperation
from irrd.utils.rpsl_samples import SAMPLE_MNTNER, SAMPLE_UNKNOWN_CLASS, SAMPLE_MALFORMED_EMPTY_LINE
from ..nrtm_operation import NRTMOperation


class TestNRTMOperation:

    def test_nrtm_add_valid(self):
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
        mock_dh = Mock()

        operation = NRTMOperation(
            source='TEST',
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            object_text=SAMPLE_MALFORMED_EMPTY_LINE,
        )
        assert not operation.save(database_handler=mock_dh)
        assert mock_dh.upsert_rpsl_object.call_count == 0

    def test_nrtm_delete_valid_incomplete_object(self):
        # In some rare cases, NRTM updates will arrive without
        # a source attribute. However, as the source of the NRTM
        # stream is known, we can guess this.
        # This is accepted for deletions only.
        obj_text = 'route: 192.0.02.0/24\norigin: AS65537'
        mock_dh = Mock()

        operation = NRTMOperation(
            source='TEST',
            operation=DatabaseOperation.delete,
            serial=42424242,
            object_text=obj_text,
        )
        assert operation.save(database_handler=mock_dh)

        assert mock_dh.delete_rpsl_object.call_count == 1
        assert mock_dh.mock_calls[0][1][0].pk() == '192.0.2.0/24AS65537'
        assert mock_dh.mock_calls[0][1][0].source() == 'TEST'
        assert mock_dh.mock_calls[0][1][1] == 42424242

    def test_nrtm_add_invalid_incomplete_object(self):
        # Source-less objects are not accepted for add/update
        obj_text = 'route: 192.0.02.0/24\norigin: AS65537'
        mock_dh = Mock()

        operation = NRTMOperation(
            source='TEST',
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            object_text=obj_text,
        )
        assert not operation.save(database_handler=mock_dh)
        assert not mock_dh.upsert_rpsl_object.call_count
