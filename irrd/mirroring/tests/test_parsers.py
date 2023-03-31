import tempfile
from unittest.mock import Mock

import pytest

from irrd.rpki.status import RPKIStatus
from irrd.rpki.validators import BulkRouteROAValidator
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.models import DatabaseOperation, JournalEntryOrigin
from irrd.utils.rpsl_samples import (
    KEY_CERT_SIGNED_MESSAGE_VALID,
    SAMPLE_KEY_CERT,
    SAMPLE_LEGACY_IRRD_ARTIFACT,
    SAMPLE_MALFORMED_PK,
    SAMPLE_ROLE,
    SAMPLE_ROUTE,
    SAMPLE_ROUTE6,
    SAMPLE_RTR_SET,
    SAMPLE_UNKNOWN_ATTRIBUTE,
    SAMPLE_UNKNOWN_CLASS,
)
from irrd.utils.test_utils import flatten_mock_calls

from ..parsers import (
    MirrorFileImportParser,
    MirrorUpdateFileImportParser,
    NRTMStreamParser,
)
from .nrtm_samples import (
    SAMPLE_NRTM_INVALID_NO_START_LINE,
    SAMPLE_NRTM_INVALID_VERSION,
    SAMPLE_NRTM_V1,
    SAMPLE_NRTM_V1_TOO_MANY_ITEMS,
    SAMPLE_NRTM_V3,
    SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES,
    SAMPLE_NRTM_V3_NO_END,
    SAMPLE_NRTM_V3_SERIAL_GAP,
    SAMPLE_NRTM_V3_SERIAL_OUT_OF_ORDER,
)


@pytest.fixture
def mock_scopefilter(monkeypatch):
    mock_scopefilter = Mock(spec=ScopeFilterValidator)
    monkeypatch.setattr("irrd.mirroring.parsers.ScopeFilterValidator", lambda: mock_scopefilter)
    mock_scopefilter.validate_rpsl_object = lambda obj: (ScopeFilterStatus.in_scope, "")
    return mock_scopefilter


class TestMirrorFileImportParser:
    # This test also covers the common parts of MirrorFileImportParserBase
    def test_parse(self, mock_scopefilter, caplog, tmp_gpg_dir, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "object_class_filter": ["route", "key-cert"],
                        "strict_import_keycert_objects": True,
                    }
                }
            }
        )
        mock_dh = Mock()
        mock_roa_validator = Mock(spec=BulkRouteROAValidator)
        mock_roa_validator.validate_route = lambda ip, length, asn, source: RPKIStatus.invalid

        test_data = [
            SAMPLE_UNKNOWN_ATTRIBUTE,  # valid, because mirror imports are non-strict
            SAMPLE_ROUTE6,  # Valid, excluded by object class filter
            SAMPLE_KEY_CERT,
            SAMPLE_ROUTE.replace("TEST", "BADSOURCE"),
            SAMPLE_UNKNOWN_CLASS,
            SAMPLE_MALFORMED_PK,
            SAMPLE_LEGACY_IRRD_ARTIFACT,
        ]
        test_input = "\n\n".join(test_data)

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(test_input.encode("utf-8"))
            fp.seek(0)
            parser = MirrorFileImportParser(
                source="TEST",
                filename=fp.name,
                serial=424242,
                database_handler=mock_dh,
                roa_validator=mock_roa_validator,
            )
            parser.run_import()
        assert len(mock_dh.mock_calls) == 5
        assert mock_dh.mock_calls[0][0] == "upsert_rpsl_object"
        assert mock_dh.mock_calls[0][1][0].pk() == "192.0.2.0/24AS65537"
        assert mock_dh.mock_calls[0][1][0].rpki_status == RPKIStatus.invalid
        assert mock_dh.mock_calls[0][1][0].scopefilter_status == ScopeFilterStatus.in_scope
        assert mock_dh.mock_calls[1][0] == "upsert_rpsl_object"
        assert mock_dh.mock_calls[1][1][0].pk() == "PGPKEY-80F238C6"
        assert mock_dh.mock_calls[2][0] == "record_mirror_error"
        assert mock_dh.mock_calls[3][0] == "record_mirror_error"
        assert mock_dh.mock_calls[4][0] == "record_serial_seen"
        assert mock_dh.mock_calls[4][1][0] == "TEST"
        assert mock_dh.mock_calls[4][1][1] == 424242

        assert "Invalid source BADSOURCE for object" in caplog.text
        assert "Invalid address prefix" in caplog.text
        assert (
            "File import for TEST: 6 objects read, 2 objects inserted, ignored 2 due to errors" in caplog.text
        )
        assert "ignored 1 due to object_class_filter" in caplog.text
        assert "Ignored 1 objects found in file import for TEST due to unknown object classes" in caplog.text

        key_cert_obj = rpsl_object_from_text(SAMPLE_KEY_CERT, strict_validation=False)
        assert key_cert_obj.verify(KEY_CERT_SIGNED_MESSAGE_VALID)

    def test_direct_error_return_invalid_source(self, mock_scopefilter, caplog, tmp_gpg_dir, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {},
                }
            }
        )
        mock_dh = Mock()

        test_data = [
            SAMPLE_UNKNOWN_ATTRIBUTE,  # valid, because mirror imports are non-strict
            SAMPLE_ROUTE.replace("TEST", "BADSOURCE"),
        ]
        test_input = "\n\n".join(test_data)

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(test_input.encode("utf-8"))
            fp.seek(0)
            parser = MirrorFileImportParser(
                source="TEST",
                filename=fp.name,
                serial=424242,
                database_handler=mock_dh,
                direct_error_return=True,
            )
            error = parser.run_import()
            assert error == "Invalid source BADSOURCE for object 192.0.2.0/24AS65537, expected TEST"
        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == "upsert_rpsl_object"
        assert mock_dh.mock_calls[0][1][0].pk() == "192.0.2.0/24AS65537"
        assert mock_dh.mock_calls[0][1][0].rpki_status == RPKIStatus.not_found

        assert "Invalid source BADSOURCE for object" not in caplog.text
        assert "File import for TEST" not in caplog.text

    def test_direct_error_return_malformed_pk(self, mock_scopefilter, caplog, tmp_gpg_dir, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {},
                }
            }
        )
        mock_dh = Mock()

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(SAMPLE_MALFORMED_PK.encode("utf-8"))
            fp.seek(0)
            parser = MirrorFileImportParser(
                source="TEST",
                filename=fp.name,
                serial=424242,
                database_handler=mock_dh,
                direct_error_return=True,
            )
            error = parser.run_import()
            assert "Invalid address prefix: not-a-prefix" in error
        assert not len(mock_dh.mock_calls)

        assert "Invalid address prefix: not-a-prefix" not in caplog.text
        assert "File import for TEST" not in caplog.text

    def test_direct_error_return_unknown_class(self, mock_scopefilter, caplog, tmp_gpg_dir, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {},
                }
            }
        )
        mock_dh = Mock()

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(SAMPLE_UNKNOWN_CLASS.encode("utf-8"))
            fp.seek(0)
            parser = MirrorFileImportParser(
                source="TEST",
                filename=fp.name,
                serial=424242,
                database_handler=mock_dh,
                direct_error_return=True,
            )
            error = parser.run_import()
            assert error == "Unknown object class: foo-block"
        assert not len(mock_dh.mock_calls)

        assert "Unknown object class: foo-block" not in caplog.text
        assert "File import for TEST" not in caplog.text


class TestMirrorUpdateFileImportParser:
    def test_parse(self, mock_scopefilter, caplog, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "object_class_filter": ["route", "route6", "key-cert", "role"],
                    }
                }
            }
        )
        mock_dh = Mock()

        test_data = [
            SAMPLE_ROUTE,  # Valid retained
            SAMPLE_ROUTE6,  # Valid modified
            SAMPLE_ROLE,  # Valid new object
            SAMPLE_ROUTE.replace("TEST", "BADSOURCE"),
            SAMPLE_UNKNOWN_CLASS,
            SAMPLE_MALFORMED_PK,
        ]
        test_input = "\n\n".join(test_data)

        route_with_last_modified = SAMPLE_ROUTE + "last-modified:  2020-01-01T00:00:00Z\n"
        mock_query_result = [
            {
                # Retained object (with format cleaning)
                # includes a last-modified which should be ignored in the comparison
                "rpsl_pk": "192.0.2.0/24AS65537",
                "object_class": "route",
                "object_text": rpsl_object_from_text(route_with_last_modified).render_rpsl_text(),
            },
            {
                # Modified object
                "rpsl_pk": "2001:DB8::/48AS65537",
                "object_class": "route6",
                "object_text": SAMPLE_ROUTE6.replace("test-MNT", "existing-mnt"),
            },
            {
                # Deleted object
                "rpsl_pk": "rtrs-settest",
                "object_class": "route-set",
                "object_text": SAMPLE_RTR_SET,
            },
        ]
        mock_dh.execute_query = lambda query: mock_query_result

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(test_input.encode("utf-8"))
            fp.seek(0)
            parser = MirrorUpdateFileImportParser(
                source="TEST",
                filename=fp.name,
                database_handler=mock_dh,
            )
            parser.run_import()

        assert len(mock_dh.mock_calls) == 5
        assert mock_dh.mock_calls[0][0] == "record_mirror_error"
        assert mock_dh.mock_calls[1][0] == "record_mirror_error"
        assert mock_dh.mock_calls[2][0] == "upsert_rpsl_object"
        assert mock_dh.mock_calls[2][1][0].pk() == "ROLE-TEST"
        assert mock_dh.mock_calls[3][0] == "delete_rpsl_object"
        assert mock_dh.mock_calls[3][2]["source"] == "TEST"
        assert mock_dh.mock_calls[3][2]["rpsl_pk"] == "rtrs-settest"
        assert mock_dh.mock_calls[3][2]["object_class"] == "route-set"
        assert mock_dh.mock_calls[3][2]["origin"] == JournalEntryOrigin.synthetic_nrtm
        assert mock_dh.mock_calls[4][0] == "upsert_rpsl_object"
        assert mock_dh.mock_calls[4][1][0].pk() == "2001:DB8::/48AS65537"

        assert "Invalid source BADSOURCE for object" in caplog.text
        assert "Invalid address prefix" in caplog.text
        assert (
            "File update for TEST: 6 objects read, 3 objects processed, 1 objects newly inserted, 1 objects"
            " newly deleted, 2 objects retained, of which 1 modified"
            in caplog.text
        )
        assert "ignored 0 due to object_class_filter" in caplog.text
        assert "Ignored 1 objects found in file import for TEST due to unknown object classes" in caplog.text

    def test_direct_error_return(self, mock_scopefilter, config_override):
        config_override({"sources": {"TEST": {}}})
        mock_dh = Mock()

        test_data = [
            SAMPLE_UNKNOWN_CLASS,
            SAMPLE_MALFORMED_PK,
        ]
        test_input = "\n\n".join(test_data)

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(test_input.encode("utf-8"))
            fp.seek(0)
            parser = MirrorUpdateFileImportParser(
                source="TEST",
                filename=fp.name,
                database_handler=mock_dh,
                direct_error_return=True,
            )
            assert parser.run_import() == "Unknown object class: foo-block"

        assert len(mock_dh.mock_calls) == 0


class TestNRTMStreamParser:
    def test_test_parse_nrtm_v3_valid(self):
        mock_dh = Mock()
        parser = NRTMStreamParser("TEST", SAMPLE_NRTM_V3, mock_dh)
        self._assert_valid(parser)
        assert flatten_mock_calls(mock_dh) == [["record_serial_newest_mirror", ("TEST", 11012701), {}]]

    def test_test_parse_nrtm_v1_valid(self, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "object_class_filter": "person",
                        "strict_import_keycert_objects": True,
                    }
                }
            }
        )
        mock_dh = Mock()
        parser = NRTMStreamParser("TEST", SAMPLE_NRTM_V1, mock_dh)
        self._assert_valid(parser)
        assert flatten_mock_calls(mock_dh) == [["record_serial_newest_mirror", ("TEST", 11012701), {}]]

    def test_test_parse_nrtm_v3_valid_serial_gap(self):
        mock_dh = Mock()
        parser = NRTMStreamParser("TEST", SAMPLE_NRTM_V3_SERIAL_GAP, mock_dh)
        self._assert_valid(parser)
        assert flatten_mock_calls(mock_dh) == [["record_serial_newest_mirror", ("TEST", 11012703), {}]]

    def test_test_parse_nrtm_v3_invalid_serial_out_of_order(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser("TEST", SAMPLE_NRTM_V3_SERIAL_OUT_OF_ORDER, mock_dh)

        error_msg = "expected at least"
        assert error_msg in str(ve.value)
        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == "record_mirror_error"
        assert mock_dh.mock_calls[0][1][0] == "TEST"
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def test_test_parse_nrtm_v3_invalid_unexpected_source(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser("BADSOURCE", SAMPLE_NRTM_V3, mock_dh)

        error_msg = "Invalid NRTM source in START line: expected BADSOURCE but found TEST "
        assert error_msg in str(ve.value)
        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == "record_mirror_error"
        assert mock_dh.mock_calls[0][1][0] == "BADSOURCE"
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def test_test_parse_nrtm_v1_invalid_too_many_items(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser("TEST", SAMPLE_NRTM_V1_TOO_MANY_ITEMS, mock_dh)
        error_msg = "expected operations up to and including"
        assert error_msg in str(ve.value)

        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == "record_mirror_error"
        assert mock_dh.mock_calls[0][1][0] == "TEST"
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def test_test_parse_nrtm_invalid_invalid_version(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser("TEST", SAMPLE_NRTM_INVALID_VERSION, mock_dh)

        error_msg = "Invalid NRTM version 99 in START line"
        assert error_msg in str(ve.value)
        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == "record_mirror_error"
        assert mock_dh.mock_calls[0][1][0] == "TEST"
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def test_test_parse_nrtm_invalid_multiple_start_lines(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser("TEST", SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES, mock_dh)

        error_msg = "Encountered second START line"
        assert error_msg in str(ve.value)

        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == "record_mirror_error"
        assert mock_dh.mock_calls[0][1][0] == "TEST"
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def test_test_parse_nrtm_invalid_no_start_line(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser("TEST", SAMPLE_NRTM_INVALID_NO_START_LINE, mock_dh)

        error_msg = "Encountered operation before valid NRTM START line"
        assert error_msg in str(ve.value)
        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == "record_mirror_error"
        assert mock_dh.mock_calls[0][1][0] == "TEST"
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def test_test_parse_nrtm_no_end(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser("TEST", SAMPLE_NRTM_V3_NO_END, mock_dh)

        error_msg = "last comment paragraph expected to be"
        assert error_msg in str(ve.value)
        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == "record_mirror_error"
        assert mock_dh.mock_calls[0][1][0] == "TEST"
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def _assert_valid(self, parser: NRTMStreamParser):
        assert parser.operations[0].operation == DatabaseOperation.add_or_update
        assert parser.operations[0].serial == 11012700
        assert parser.operations[0].object_text == "person: NRTM test\naddress: NowhereLand\nsource: TEST\n"
        assert parser.operations[1].operation == DatabaseOperation.delete
        assert parser.operations[1].serial == 11012701
        assert parser.operations[1].object_text == "inetnum: 192.0.2.0 - 192.0.2.255\nsource: TEST\n"
