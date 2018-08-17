import pytest

from .nrtm_samples import (SAMPLE_NRTM_V3, SAMPLE_NRTM_V1, SAMPLE_NRTM_V1_TOO_MANY_ITEMS, SAMPLE_NRTM_INVALID_VERSION,
                           SAMPLE_NRTM_V3_SERIAL_GAP, SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES,
                           SAMPLE_NRTM_INVALID_NO_START_LINE, SAMPLE_NRTM_V3_SERIAL_OUT_OF_ORDER)
from irrd.storage.models import DatabaseOperation
from ..nrtm_parser import NRTMStreamParser


class TestNRTMParser:
    def test_test_parse_nrtm_v3_valid(self):
        parser = NRTMStreamParser(SAMPLE_NRTM_V3)
        self._assert_valid(parser)

    def test_test_parse_nrtm_v1_valid(self):
        parser = NRTMStreamParser(SAMPLE_NRTM_V1)
        self._assert_valid(parser)

    def test_test_parse_nrtm_v3_valid_serial_gap(self):
        parser = NRTMStreamParser(SAMPLE_NRTM_V3_SERIAL_GAP)
        self._assert_valid(parser)

    def test_test_parse_nrtm_v3_invalid_serial_out_of_order(self):
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser(SAMPLE_NRTM_V3_SERIAL_OUT_OF_ORDER)
        assert 'expected at least' in str(ve)

    def test_test_parse_nrtm_v1_invalid_too_many_items(self):
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser(SAMPLE_NRTM_V1_TOO_MANY_ITEMS)
        assert 'expected operations up to and including' in str(ve)

    def test_test_parse_nrtm_invalid_invalid_version(self):
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser(SAMPLE_NRTM_INVALID_VERSION)
        assert 'Invalid NRTM version 99 in NRTM start line' in str(ve)

    def test_test_parse_nrtm_invalid_multiple_start_lines(self):
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser(SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES)
        assert 'Encountered second START line' in str(ve)

    def test_test_parse_nrtm_invalid_no_start_line(self):
        with pytest.raises(ValueError) as ve:
            NRTMStreamParser(SAMPLE_NRTM_INVALID_NO_START_LINE)
        assert 'Encountered operation before NRTM START line' in str(ve)

    def _assert_valid(self, parser: NRTMStreamParser):
        assert parser.operations[0].operation == DatabaseOperation.add_or_update
        assert parser.operations[0].serial == 11012700
        assert parser.operations[0].object_text == 'person: NRTM test\naddress: NowhereLand\nsource: RIPE\n'
        assert parser.operations[1].operation == DatabaseOperation.delete
        assert parser.operations[1].serial == 11012701
        assert parser.operations[1].object_text == 'inetnum: 192.0.2.0 - 192.0.2.255\nsource: RIPE\n'
