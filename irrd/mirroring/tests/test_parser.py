import tempfile
from unittest.mock import Mock

import pytest

from irrd.utils.rpsl_samples import SAMPLE_ROUTE, SAMPLE_UNKNOWN_CLASS, SAMPLE_UNKNOWN_ATTRIBUTE, SAMPLE_MALFORMED_PK
from irrd.utils.test_utils import flatten_mock_calls
from .nrtm_samples import (SAMPLE_NRTM_V3, SAMPLE_NRTM_V1, SAMPLE_NRTM_V1_TOO_MANY_ITEMS, SAMPLE_NRTM_INVALID_VERSION,
                           SAMPLE_NRTM_V3_SERIAL_GAP, SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES,
                           SAMPLE_NRTM_INVALID_NO_START_LINE, SAMPLE_NRTM_V3_SERIAL_OUT_OF_ORDER)
from irrd.storage.models import DatabaseOperation
from ..parser import NRTMStreamParser, MirrorFullImportParser


class TestMirrorFullImportParser:
    def test_parse(self, monkeypatch, caplog):
        monkeypatch.setenv('IRRD_SOURCES_RIPE_OBJECT_CLASS_FILTER', 'as-block,as-set')
        mock_dh = Mock()

        test_data = [
            SAMPLE_UNKNOWN_ATTRIBUTE,  # valid, because mirror imports are non-strict
            SAMPLE_ROUTE,  # Valid, excluded by object class filter
            SAMPLE_ROUTE.replace('RIPE', 'BADSOURCE'),
            SAMPLE_UNKNOWN_CLASS,
            SAMPLE_MALFORMED_PK,
        ]
        test_input = '\n\n'.join(test_data)

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(test_input.encode('utf-8'))
            fp.seek(0)
            MirrorFullImportParser(
                source='RIPE',
                filename=fp.name,
                serial=424242,
                database_handler=mock_dh,
            )
        assert len(mock_dh.mock_calls) == 1
        assert mock_dh.mock_calls[0][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[0][1][0].pk() == 'AS2043 - AS2043'

        assert 'Invalid source BADSOURCE for object' in caplog.text
        assert 'Invalid AS number ASX' in caplog.text
        assert 'Full import for RIPE: 9 objects read, 1 objects inserted, ignored 2 due to errors' in caplog.text
        assert 'ignored 1 due to object_class_filter' in caplog.text
        assert 'Ignored 5 objects found in full import for RIPE due to unknown object classes' in caplog.text


class TestNRTMStreamParser:
    def test_test_parse_nrtm_v3_valid(self):
        mock_dh = Mock()
        parser = NRTMStreamParser('RIPE', SAMPLE_NRTM_V3, mock_dh)
        self._assert_valid(parser)
        assert flatten_mock_calls(mock_dh) == [['force_record_serial_seen', ('RIPE', 11012701), {}]]

    def test_test_parse_nrtm_v1_valid(self):
        mock_dh = Mock()
        parser = NRTMStreamParser('RIPE', SAMPLE_NRTM_V1, mock_dh)
        self._assert_valid(parser)
        assert flatten_mock_calls(mock_dh) == [['force_record_serial_seen', ('RIPE', 11012701), {}]]

    def test_test_parse_nrtm_v3_valid_serial_gap(self):
        mock_dh = Mock()
        parser = NRTMStreamParser('RIPE', SAMPLE_NRTM_V3_SERIAL_GAP, mock_dh)
        self._assert_valid(parser)
        assert flatten_mock_calls(mock_dh) == [['force_record_serial_seen', ('RIPE', 11012703), {}]]

    def test_test_parse_nrtm_v3_invalid_serial_out_of_order(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser('RIPE', SAMPLE_NRTM_V3_SERIAL_OUT_OF_ORDER, mock_dh)
        assert 'expected at least' in str(ve)
        assert flatten_mock_calls(mock_dh) == [['force_record_serial_seen', ('RIPE', 11012703), {}]]

    def test_test_parse_nrtm_v3_invalid_unexpected_source(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser('BADSOURCE', SAMPLE_NRTM_V3, mock_dh)
        assert 'Invalid NRTM source in START line: expected BADSOURCE but found RIPE ' in str(ve)
        assert not len(mock_dh.mock_calls)

    def test_test_parse_nrtm_v1_invalid_too_many_items(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser('RIPE', SAMPLE_NRTM_V1_TOO_MANY_ITEMS, mock_dh)
        assert 'expected operations up to and including' in str(ve)
        assert flatten_mock_calls(mock_dh) == [['force_record_serial_seen', ('RIPE', 11012700), {}]]

    def test_test_parse_nrtm_invalid_invalid_version(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser('RIPE', SAMPLE_NRTM_INVALID_VERSION, mock_dh)
        assert 'Invalid NRTM version 99 in START line' in str(ve)
        assert not len(mock_dh.mock_calls)

    def test_test_parse_nrtm_invalid_multiple_start_lines(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser('RIPE', SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES, mock_dh)
        assert 'Encountered second START line' in str(ve)

    def test_test_parse_nrtm_invalid_no_start_line(self):
        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser('RIPE', SAMPLE_NRTM_INVALID_NO_START_LINE, mock_dh)
        assert 'Encountered operation before valid NRTM START line' in str(ve)
        assert not len(mock_dh.mock_calls)

    def _assert_valid(self, parser: NRTMStreamParser):
        assert parser.operations[0].operation == DatabaseOperation.add_or_update
        assert parser.operations[0].serial == 11012700
        assert parser.operations[0].object_text == 'person: NRTM test\naddress: NowhereLand\nsource: RIPE\n'
        assert parser.operations[1].operation == DatabaseOperation.delete
        assert parser.operations[1].serial == 11012701
        assert parser.operations[1].object_text == 'inetnum: 192.0.2.0 - 192.0.2.255\nsource: RIPE\n'
