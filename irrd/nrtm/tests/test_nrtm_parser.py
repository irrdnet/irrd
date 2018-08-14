import pytest

from .nrtm_samples import SAMPLE_NRTM_V3, SAMPLE_NRTM_V1, SAMPLE_NRTM_V1_TOO_MANY_ITEMS, \
    SAMPLE_NRTM_INVALID_VERSION, SAMPLE_NRTM_V3_SERIAL_MISMATCH, SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES, \
    SAMPLE_NRTM_INVALID_NO_START_LINE
from irrd.storage.models import DatabaseOperation
from ..nrtm_parser import NRTMParser


class TestNRTMParser:
    def test_test_parse_nrtm_v3_valid(self):
        splitter = NRTMParser(SAMPLE_NRTM_V3)
        assert splitter.operations[0].operation == DatabaseOperation.add_or_update
        assert splitter.operations[0].serial == 11012700
        assert splitter.operations[0].object_text == 'person: NRTM test\naddress: NowhereLand\nsource: RIPE\n'
        assert splitter.operations[1].operation == DatabaseOperation.delete
        assert splitter.operations[1].serial == 11012701
        assert splitter.operations[1].object_text == 'inetnum: 192.0.2.0 - 192.0.2.255\nsource: RIPE\n'

    def test_test_parse_nrtm_v1_valid(self):
        splitter = NRTMParser(SAMPLE_NRTM_V1)
        assert splitter.operations[0].operation == DatabaseOperation.add_or_update
        assert splitter.operations[0].serial == 11012700
        assert splitter.operations[0].object_text == 'person: NRTM test\naddress: NowhereLand\nsource: RIPE\n'
        assert splitter.operations[1].operation == DatabaseOperation.delete
        assert splitter.operations[1].serial == 11012701
        assert splitter.operations[1].object_text == 'inetnum: 192.0.2.0 - 192.0.2.255\nsource: RIPE\n'

    def test_test_parse_nrtm_v1_invalid_too_many_items(self):
        with pytest.raises(ValueError) as ve:
            NRTMParser(SAMPLE_NRTM_V1_TOO_MANY_ITEMS)
        assert 'expected operations up to and including' in str(ve)

    def test_test_parse_nrtm_invalid_invalid_version(self):
        with pytest.raises(ValueError) as ve:
            NRTMParser(SAMPLE_NRTM_INVALID_VERSION)
        assert 'Invalid NRTM version 99 in NRTM start line' in str(ve)

    def test_test_parse_nrtm_v3_invalid_serial_mismatch(self):
        with pytest.raises(ValueError) as ve:
            NRTMParser(SAMPLE_NRTM_V3_SERIAL_MISMATCH)
        assert 'Invalid NRTM serial: ADD/DEL has serial' in str(ve)

    def test_test_parse_nrtm_invalid_multiple_start_lines(self):
        with pytest.raises(ValueError) as ve:
            NRTMParser(SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES)
        assert 'Encountered second START line' in str(ve)

    def test_test_parse_nrtm_invalid_no_start_line(self):
        with pytest.raises(ValueError) as ve:
            NRTMParser(SAMPLE_NRTM_INVALID_NO_START_LINE)
        assert 'Encountered operation before NRTM START line' in str(ve)
