import pytest

from irrd.nrtm.tests.nrtm_samples import SAMPLE_NRTM_V3, SAMPLE_NRTM_V1, SAMPLE_NRTM_V1_TOO_MANY_ITEMS, \
    SAMPLE_NRTM_INVALID_VERSION, SAMPLE_NRTM_V3_SERIAL_MISMATCH, SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES
from ..nrtm_splitter import NRTMSplitter


class TestNRTMSplitter:
    def test_split_stream_v3_valid(self):
        splitter = NRTMSplitter(SAMPLE_NRTM_V3)
        assert splitter.operations == [
            ('ADD', '11012700', 'person: NRTM test\naddress: NowhereLand\nsource: RIPE\n'),
            ('DEL', '11012701', 'inetnum: 192.0.2.0 - 192.0.2.255\nsource: RIPE\n'),
        ]

    def test_split_stream_v1_valid(self):
        splitter = NRTMSplitter(SAMPLE_NRTM_V1)
        assert splitter.operations == [
            ('ADD', '11012700', 'person: NRTM test\naddress: NowhereLand\nsource: RIPE\n'),
            ('DEL', '11012701', 'inetnum: 192.0.2.0 - 192.0.2.255\nsource: RIPE\n'),
        ]

    def test_split_stream_v1_invalid_too_many_items(self):
        with pytest.raises(ValueError) as ve:
            NRTMSplitter(SAMPLE_NRTM_V1_TOO_MANY_ITEMS)
        assert 'expected operations up to and including' in str(ve)

    def test_split_stream_invalid_invalid_version(self):
        with pytest.raises(ValueError) as ve:
            NRTMSplitter(SAMPLE_NRTM_INVALID_VERSION)
        assert 'Invalid NRTM version 99 in NRTM start line' in str(ve)

    def test_split_stream_v3_invalid_serial_mismatch(self):
        with pytest.raises(ValueError) as ve:
            NRTMSplitter(SAMPLE_NRTM_V3_SERIAL_MISMATCH)
        assert 'Invalid NRTM serial: ADD/DEL has serial' in str(ve)

    def test_split_stream_invalid_multiple_start_lines(self):
        with pytest.raises(ValueError) as ve:
            NRTMSplitter(SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES)
        assert 'Encountered second START line' in str(ve)
