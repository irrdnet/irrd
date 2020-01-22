import tempfile
from unittest.mock import Mock

import pytest

from irrd.rpki.parser import BulkRouteRoaValidator
from irrd.rpki.status import RPKIStatus
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.utils.rpsl_samples import SAMPLE_ROUTE, SAMPLE_UNKNOWN_CLASS, SAMPLE_UNKNOWN_ATTRIBUTE, SAMPLE_MALFORMED_PK, \
    SAMPLE_ROUTE6, SAMPLE_KEY_CERT, KEY_CERT_SIGNED_MESSAGE_VALID, SAMPLE_LEGACY_IRRD_ARTIFACT
from irrd.utils.test_utils import flatten_mock_calls
from .nrtm_samples import (SAMPLE_NRTM_V3, SAMPLE_NRTM_V1, SAMPLE_NRTM_V1_TOO_MANY_ITEMS, SAMPLE_NRTM_INVALID_VERSION,
                           SAMPLE_NRTM_V3_SERIAL_GAP, SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES,
                           SAMPLE_NRTM_INVALID_NO_START_LINE, SAMPLE_NRTM_V3_SERIAL_OUT_OF_ORDER)
from irrd.storage.models import DatabaseOperation
from ..parsers import NRTMStreamParser, MirrorFileImportParser


class TestMirrorFileImportParser:
    def test_parse(self, caplog, tmp_gpg_dir, config_override):
        config_override({
            'sources': {
                'TEST': {
                    'object_class_filter': ['route', 'key-cert'],
                    'strict_import_keycert_objects': True,
                }
            }
        })
        mock_dh = Mock()
        mock_roa_validator = Mock(spec=BulkRouteRoaValidator)
        mock_roa_validator.validate_route = lambda ip, length, asn: RPKIStatus.invalid

        test_data = [
            SAMPLE_UNKNOWN_ATTRIBUTE,  # valid, because mirror imports are non-strict
            SAMPLE_ROUTE6,  # Valid, excluded by object class filter
            SAMPLE_KEY_CERT,
            SAMPLE_ROUTE.replace('TEST', 'BADSOURCE'),
            SAMPLE_UNKNOWN_CLASS,
            SAMPLE_MALFORMED_PK,
            SAMPLE_LEGACY_IRRD_ARTIFACT,
        ]
        test_input = '\n\n'.join(test_data)

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(test_input.encode('utf-8'))
            fp.seek(0)
            parser = MirrorFileImportParser(source='TEST', filename=fp.name, serial=424242,
                                            database_handler=mock_dh, roa_validator=mock_roa_validator)
            parser.run_import()
        assert len(mock_dh.mock_calls) == 4
        assert mock_dh.mock_calls[0][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[0][1][0].pk() == '192.0.2.0/24AS65537'
        assert mock_dh.mock_calls[0][1][0].rpki_status == RPKIStatus.invalid
        assert mock_dh.mock_calls[1][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[1][1][0].pk() == 'PGPKEY-80F238C6'
        assert mock_dh.mock_calls[2][0] == 'record_mirror_error'
        assert mock_dh.mock_calls[3][0] == 'record_mirror_error'

        assert 'Invalid source BADSOURCE for object' in caplog.text
        assert 'Invalid address prefix' in caplog.text
        assert 'File import for TEST: 6 objects read, 2 objects inserted, ignored 2 due to errors' in caplog.text
        assert 'ignored 1 due to object_class_filter' in caplog.text
        assert 'Ignored 1 objects found in file import for TEST due to unknown object classes' in caplog.text

        key_cert_obj = rpsl_object_from_text(SAMPLE_KEY_CERT, strict_validation=False)
        assert key_cert_obj.verify(KEY_CERT_SIGNED_MESSAGE_VALID)

    def test_direct_error_return_invalid_source(self, caplog, tmp_gpg_dir, config_override):
        config_override({
            'sources': {
                'TEST': {},
            }
        })
        mock_dh = Mock()

        test_data = [
            SAMPLE_UNKNOWN_ATTRIBUTE,  # valid, because mirror imports are non-strict
            SAMPLE_ROUTE.replace('TEST', 'BADSOURCE'),
        ]
        test_input = '\n\n'.join(test_data)

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(test_input.encode('utf-8'))
            fp.seek(0)
            parser = MirrorFileImportParser(source='TEST', filename=fp.name, serial=424242, database_handler=mock_dh,
                                            direct_error_return=True)
            error = parser.run_import()
            assert error == 'Invalid source BADSOURCE for object 192.0.2.0/24AS65537, expected TEST'
        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[0][1][0].pk() == '192.0.2.0/24AS65537'
        assert mock_dh.mock_calls[0][1][0].rpki_status == RPKIStatus.unknown

        assert 'Invalid source BADSOURCE for object' not in caplog.text
        assert 'File import for TEST' not in caplog.text

    def test_direct_error_return_malformed_pk(self, caplog, tmp_gpg_dir, config_override):
        config_override({
            'sources': {
                'TEST': {},
            }
        })
        mock_dh = Mock()

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(SAMPLE_MALFORMED_PK.encode('utf-8'))
            fp.seek(0)
            parser = MirrorFileImportParser(source='TEST', filename=fp.name, serial=424242, database_handler=mock_dh,
                                            direct_error_return=True)
            error = parser.run_import()
            assert 'Invalid address prefix: not-a-prefix' in error
        assert not len(mock_dh.mock_calls)

        assert 'Invalid address prefix: not-a-prefix' not in caplog.text
        assert 'File import for TEST' not in caplog.text

    def test_direct_error_return_unknown_class(self, caplog, tmp_gpg_dir, config_override):
        config_override({
            'sources': {
                'TEST': {},
            }
        })
        mock_dh = Mock()

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(SAMPLE_UNKNOWN_CLASS.encode('utf-8'))
            fp.seek(0)
            parser = MirrorFileImportParser(source='TEST', filename=fp.name, serial=424242, database_handler=mock_dh,
                                            direct_error_return=True)
            error = parser.run_import()
            assert error == 'Unknown object class: foo-block'
        assert not len(mock_dh.mock_calls)

        assert 'Unknown object class: foo-block' not in caplog.text
        assert 'File import for TEST' not in caplog.text


class TestNRTMStreamParser:
    def test_test_parse_nrtm_v3_valid(self):
        mock_dh = Mock()
        parser = NRTMStreamParser('TEST', SAMPLE_NRTM_V3, mock_dh)
        self._assert_valid(parser)
        assert flatten_mock_calls(mock_dh) == [['force_record_serial_seen', ('TEST', 11012701), {}]]

    def test_test_parse_nrtm_v1_valid(self, config_override):
        config_override({
            'sources': {
                'TEST': {
                    'object_class_filter': 'person',
                    'strict_import_keycert_objects': True,
                }
            }
        })
        mock_dh = Mock()
        parser = NRTMStreamParser('TEST', SAMPLE_NRTM_V1, mock_dh)
        self._assert_valid(parser)
        assert flatten_mock_calls(mock_dh) == [['force_record_serial_seen', ('TEST', 11012701), {}]]

    def test_test_parse_nrtm_v3_valid_serial_gap(self):
        mock_dh = Mock()
        parser = NRTMStreamParser('TEST', SAMPLE_NRTM_V3_SERIAL_GAP, mock_dh)
        self._assert_valid(parser)
        assert flatten_mock_calls(mock_dh) == [['force_record_serial_seen', ('TEST', 11012703), {}]]

    def test_test_parse_nrtm_v3_invalid_serial_out_of_order(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser('TEST', SAMPLE_NRTM_V3_SERIAL_OUT_OF_ORDER, mock_dh)

        error_msg = 'expected at least'
        assert error_msg in str(ve.value)
        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == 'record_mirror_error'
        assert mock_dh.mock_calls[0][1][0] == 'TEST'
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def test_test_parse_nrtm_v3_invalid_unexpected_source(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser('BADSOURCE', SAMPLE_NRTM_V3, mock_dh)

        error_msg = 'Invalid NRTM source in START line: expected BADSOURCE but found TEST '
        assert error_msg in str(ve.value)
        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == 'record_mirror_error'
        assert mock_dh.mock_calls[0][1][0] == 'BADSOURCE'
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def test_test_parse_nrtm_v1_invalid_too_many_items(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser('TEST', SAMPLE_NRTM_V1_TOO_MANY_ITEMS, mock_dh)
        error_msg = 'expected operations up to and including'
        assert error_msg in str(ve.value)

        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == 'record_mirror_error'
        assert mock_dh.mock_calls[0][1][0] == 'TEST'
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def test_test_parse_nrtm_invalid_invalid_version(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser('TEST', SAMPLE_NRTM_INVALID_VERSION, mock_dh)

        error_msg = 'Invalid NRTM version 99 in START line'
        assert error_msg in str(ve.value)
        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == 'record_mirror_error'
        assert mock_dh.mock_calls[0][1][0] == 'TEST'
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def test_test_parse_nrtm_invalid_multiple_start_lines(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser('TEST', SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES, mock_dh)

        error_msg = 'Encountered second START line'
        assert error_msg in str(ve.value)

        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == 'record_mirror_error'
        assert mock_dh.mock_calls[0][1][0] == 'TEST'
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def test_test_parse_nrtm_invalid_no_start_line(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser('TEST', SAMPLE_NRTM_INVALID_NO_START_LINE, mock_dh)

        error_msg = 'Encountered operation before valid NRTM START line'
        assert error_msg in str(ve.value)
        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == 'record_mirror_error'
        assert mock_dh.mock_calls[0][1][0] == 'TEST'
        assert error_msg in mock_dh.mock_calls[0][1][1]

    def _assert_valid(self, parser: NRTMStreamParser):
        assert parser.operations[0].operation == DatabaseOperation.add_or_update
        assert parser.operations[0].serial == 11012700
        assert parser.operations[0].object_text == 'person: NRTM test\naddress: NowhereLand\nsource: TEST\n'
        assert parser.operations[1].operation == DatabaseOperation.delete
        assert parser.operations[1].serial == 11012701
        assert parser.operations[1].object_text == 'inetnum: 192.0.2.0 - 192.0.2.255\nsource: TEST\n'
