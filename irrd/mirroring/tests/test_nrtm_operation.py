from unittest.mock import Mock

from irrd.rpki.status import RPKIStatus
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.models import DatabaseOperation, JournalEntryOrigin
from irrd.utils.rpsl_samples import (
    KEY_CERT_SIGNED_MESSAGE_VALID,
    SAMPLE_KEY_CERT,
    SAMPLE_MALFORMED_EMPTY_LINE,
    SAMPLE_MNTNER,
    SAMPLE_ROUTE,
    SAMPLE_UNKNOWN_CLASS,
)

from ..nrtm_operation import NRTMOperation


class TestNRTMOperation:
    def test_nrtm_add_valid_without_strict_import_keycert(self, monkeypatch, tmp_gpg_dir):
        mock_dh = Mock()
        mock_scopefilter = Mock(spec=ScopeFilterValidator)
        monkeypatch.setattr("irrd.mirroring.nrtm_operation.ScopeFilterValidator", lambda: mock_scopefilter)
        mock_scopefilter.validate_rpsl_object = lambda obj: (ScopeFilterStatus.in_scope, "")

        operation = NRTMOperation(
            source="TEST",
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            object_text=SAMPLE_KEY_CERT,
            strict_validation_key_cert=False,
            object_class_filter=["route", "route6", "mntner", "key-cert"],
        )
        assert operation.save(database_handler=mock_dh)

        assert mock_dh.upsert_rpsl_object.call_count == 1
        assert mock_dh.mock_calls[0][1][0].pk() == "PGPKEY-80F238C6"
        assert mock_dh.mock_calls[0][1][1] == JournalEntryOrigin.mirror

        # key-cert should not be imported in the keychain, therefore
        # verification should fail
        key_cert_obj = rpsl_object_from_text(SAMPLE_KEY_CERT, strict_validation=False)
        assert not key_cert_obj.verify(KEY_CERT_SIGNED_MESSAGE_VALID)

    def test_nrtm_add_valid_with_strict_import_keycert(self, monkeypatch, tmp_gpg_dir):
        mock_dh = Mock()
        mock_scopefilter = Mock(spec=ScopeFilterValidator)
        monkeypatch.setattr("irrd.mirroring.nrtm_operation.ScopeFilterValidator", lambda: mock_scopefilter)
        mock_scopefilter.validate_rpsl_object = lambda obj: (ScopeFilterStatus.in_scope, "")

        operation = NRTMOperation(
            source="TEST",
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            object_text=SAMPLE_KEY_CERT,
            strict_validation_key_cert=True,
            object_class_filter=["route", "route6", "mntner", "key-cert"],
        )
        assert operation.save(database_handler=mock_dh)

        assert mock_dh.upsert_rpsl_object.call_count == 1
        assert mock_dh.mock_calls[0][1][0].pk() == "PGPKEY-80F238C6"
        assert mock_dh.mock_calls[0][1][1] == JournalEntryOrigin.mirror

        # key-cert should be imported in the keychain, therefore
        # verification should succeed
        key_cert_obj = rpsl_object_from_text(SAMPLE_KEY_CERT, strict_validation=False)
        assert key_cert_obj.verify(KEY_CERT_SIGNED_MESSAGE_VALID)

    def test_nrtm_add_valid_rpki_scopefilter_aware(self, tmp_gpg_dir, monkeypatch):
        mock_dh = Mock()
        mock_route_validator = Mock()
        monkeypatch.setattr(
            "irrd.mirroring.nrtm_operation.SingleRouteROAValidator", lambda dh: mock_route_validator
        )
        mock_scopefilter = Mock(spec=ScopeFilterValidator)
        monkeypatch.setattr("irrd.mirroring.nrtm_operation.ScopeFilterValidator", lambda: mock_scopefilter)

        mock_route_validator.validate_route = lambda prefix, asn, source: RPKIStatus.invalid
        mock_scopefilter.validate_rpsl_object = lambda obj: (ScopeFilterStatus.out_scope_prefix, "")
        operation = NRTMOperation(
            source="TEST",
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            object_text=SAMPLE_ROUTE,
            strict_validation_key_cert=False,
            rpki_aware=True,
        )
        assert operation.save(database_handler=mock_dh)

        assert mock_dh.upsert_rpsl_object.call_count == 1
        assert mock_dh.mock_calls[0][1][0].pk() == "192.0.2.0/24AS65537"
        assert mock_dh.mock_calls[0][1][0].rpki_status == RPKIStatus.invalid
        assert mock_dh.mock_calls[0][1][0].scopefilter_status == ScopeFilterStatus.out_scope_prefix
        assert mock_dh.mock_calls[0][1][1] == JournalEntryOrigin.mirror

    def test_nrtm_add_valid_ignored_object_class(self):
        mock_dh = Mock()

        operation = NRTMOperation(
            source="TEST",
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            object_text=SAMPLE_MNTNER,
            strict_validation_key_cert=False,
            object_class_filter=["route", "route6"],
        )
        assert not operation.save(database_handler=mock_dh)
        assert mock_dh.upsert_rpsl_object.call_count == 0

    def test_nrtm_delete_valid(self):
        mock_dh = Mock()

        operation = NRTMOperation(
            source="TEST",
            operation=DatabaseOperation.delete,
            serial=42424242,
            strict_validation_key_cert=False,
            object_text=SAMPLE_MNTNER,
        )
        assert operation.save(database_handler=mock_dh)

        assert mock_dh.delete_rpsl_object.call_count == 1
        assert mock_dh.mock_calls[0][2]["rpsl_object"].pk() == "TEST-MNT"
        assert mock_dh.mock_calls[0][2]["origin"] == JournalEntryOrigin.mirror

    def test_nrtm_add_invalid_unknown_object_class(self):
        mock_dh = Mock()

        operation = NRTMOperation(
            source="TEST",
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            strict_validation_key_cert=False,
            object_text=SAMPLE_UNKNOWN_CLASS,
        )
        assert not operation.save(database_handler=mock_dh)
        assert mock_dh.upsert_rpsl_object.call_count == 0

    def test_nrtm_add_invalid_inconsistent_source(self):
        mock_dh = Mock()

        operation = NRTMOperation(
            source="NOT-TEST",
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            strict_validation_key_cert=False,
            object_text=SAMPLE_MNTNER,
        )
        assert not operation.save(database_handler=mock_dh)
        assert mock_dh.upsert_rpsl_object.call_count == 0

    def test_nrtm_add_invalid_rpsl_errors(self):
        mock_dh = Mock()

        operation = NRTMOperation(
            source="TEST",
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            strict_validation_key_cert=False,
            object_text=SAMPLE_MALFORMED_EMPTY_LINE,
        )
        assert not operation.save(database_handler=mock_dh)
        assert mock_dh.upsert_rpsl_object.call_count == 0

    def test_nrtm_delete_valid_incomplete_object(self):
        # In some rare cases, NRTM updates will arrive without
        # a source attribute. However, as the source of the NRTM
        # stream is known, we can guess this.
        # This is accepted for deletions only.
        obj_text = "route: 192.0.02.0/24\norigin: AS65537"
        mock_dh = Mock()

        operation = NRTMOperation(
            source="TEST",
            operation=DatabaseOperation.delete,
            serial=42424242,
            object_text=obj_text,
            strict_validation_key_cert=False,
        )
        assert operation.save(database_handler=mock_dh)

        assert mock_dh.delete_rpsl_object.call_count == 1
        assert mock_dh.mock_calls[0][2]["rpsl_object"].pk() == "192.0.2.0/24AS65537"
        assert mock_dh.mock_calls[0][2]["rpsl_object"].source() == "TEST"
        assert mock_dh.mock_calls[0][2]["origin"] == JournalEntryOrigin.mirror

    def test_nrtm_add_invalid_incomplete_object(self):
        # Source-less objects are not accepted for add/update
        obj_text = "route: 192.0.02.0/24\norigin: AS65537"
        mock_dh = Mock()

        operation = NRTMOperation(
            source="TEST",
            operation=DatabaseOperation.add_or_update,
            serial=42424242,
            object_text=obj_text,
            strict_validation_key_cert=False,
        )
        assert not operation.save(database_handler=mock_dh)
        assert not mock_dh.upsert_rpsl_object.call_count
