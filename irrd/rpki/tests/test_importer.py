import ujson

import pytest
import textwrap
from unittest.mock import Mock

from irrd.conf import RPKI_IRR_PSEUDO_SOURCE
from irrd.storage.database_handler import DatabaseHandler
from irrd.utils.test_utils import flatten_mock_calls
from ..importer import ROADataImporter, ROAParserException


class TestROAImportProcess:
    def test_valid_process(self, monkeypatch):
        # Note that this test does not mock RPSLObjectFromROA, used
        # for generating the pseudo-IRR object, or the ROA class itself.

        mock_dh = Mock(spec=DatabaseHandler)

        data = ujson.dumps({
            "roas": [{
                "asn": "AS64496",
                "prefix": "192.0.2.0/24",
                "maxLength": 26,
                "ta": "APNIC RPKI Root"
            }, {
                "asn": "AS64497",
                "prefix": "2001:db8::/32",
                "maxLength": 40,
                "ta": "RIPE NCC RPKI Root"
            }]
        })
        roa_importer = ROADataImporter(data, mock_dh)
        assert flatten_mock_calls(mock_dh, flatten_objects=True) == [
            ['insert_roa_object', (),
                {'ip_version': 4, 'prefix_str': '192.0.2.0/24', 'asn': 64496,
                 'max_length': 26, 'trust_anchor': 'APNIC RPKI Root'}],
            ['upsert_rpsl_object', ('route/192.0.2.0/24AS64496/ML26/RPKI',), {'rpsl_safe_insert_only': True}],
            ['insert_roa_object', (),
                {'ip_version': 6, 'prefix_str': '2001:db8::/32', 'asn': 64497,
                 'max_length': 40, 'trust_anchor': 'RIPE NCC RPKI Root'}],
            ['upsert_rpsl_object', ('route6/2001:db8::/32AS64497/ML40/RPKI',), {'rpsl_safe_insert_only': True}],
        ]

        assert roa_importer.roa_objs[0]._rpsl_object.source() == RPKI_IRR_PSEUDO_SOURCE
        assert roa_importer.roa_objs[0]._rpsl_object.render_rpsl_text() == textwrap.dedent("""
            route:          192.0.2.0/24
            descr:          RPKI ROA for 192.0.2.0/24 / AS64496
            remarks:        This route object represents routing data retrieved
            remarks:        from the RPKI. The original data can be found here:
            remarks:        https://rpki.gin.ntt.net/r/AS64496/192.0.2.0/24
            remarks:        This route object is the result of an automated
            remarks:        RPKI-to-IRR conversion process performed by IRRd.
            remarks:        maxLength 26
            origin:         AS64496
            source:         RPKI  # Trust Anchor: APNIC RPKI Root
            """).strip() + '\n'

    def test_invalid_json(self, monkeypatch):
        mock_dh = Mock(spec=DatabaseHandler)

        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter('invalid', mock_dh)

        assert 'Unable to parse ROA input: invalid JSON: Expected object or value' in str(rpe.value)

        data = ujson.dumps({'invalid root': 42})
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, mock_dh)
        assert 'Unable to parse ROA input: root key "roas" not found' in str(rpe.value)

        assert flatten_mock_calls(mock_dh) == []

    def test_invalid_data_in_roa(self, monkeypatch):
        mock_dh = Mock(spec=DatabaseHandler)

        data = ujson.dumps({
            "roas": [{
                "asn": "AS64496",
                "prefix": "192.0.2.999/24",
                "maxLength": 26,
                "ta": "APNIC RPKI Root"
            }]
        })
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, mock_dh)
        assert "Invalid value in ROA: '192.0.2.999': single byte must be 0 <= byte < 256" in str(rpe.value)

        data = ujson.dumps({
            "roas": [{
                "asn": "ASx",
                "prefix": "192.0.2.0/24",
                "maxLength": 24,
                "ta": "APNIC RPKI Root"
            }]
        })
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, mock_dh)
        assert 'Invalid AS number ASX: number part is not numeric' in str(rpe.value)

        data = ujson.dumps({
            "roas": [{
                "prefix": "192.0.2.0/24",
                "maxLength": 24,
                "ta": "APNIC RPKI Root"
            }]
        })
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, mock_dh)
        assert "Unable to parse ROA record: missing key 'asn'" in str(rpe.value)

        data = ujson.dumps({
            "roas": [{
                "asn": "AS64496",
                "prefix": "192.0.2.0/24",
                "maxLength": 22,
                "ta": "APNIC RPKI Root"
            }]
        })
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, mock_dh)
        assert 'Invalid ROA: prefix size 24 is smaller than max length 22' in str(rpe.value)

        assert flatten_mock_calls(mock_dh) == []
