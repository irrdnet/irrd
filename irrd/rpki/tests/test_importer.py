import textwrap
from unittest.mock import Mock

import pytest
import ujson

from irrd.conf import RPKI_IRR_PSEUDO_SOURCE
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.database_handler import DatabaseHandler
from irrd.utils.test_utils import flatten_mock_calls

from ..importer import ROADataImporter, ROAParserException


@pytest.fixture()
def mock_scopefilter(monkeypatch):
    mock_scopefilter = Mock(spec=ScopeFilterValidator)
    monkeypatch.setattr("irrd.rpki.importer.ScopeFilterValidator", lambda: mock_scopefilter)
    mock_scopefilter.validate_rpsl_object = lambda obj: (ScopeFilterStatus.out_scope_as, "")


class TestROAImportProcess:
    def test_valid_process(self, monkeypatch, mock_scopefilter):
        # Note that this test does not mock RPSLObjectFromROA, used
        # for generating the pseudo-IRR object, or the ROA class itself.

        mock_dh = Mock(spec=DatabaseHandler)

        rpki_data = ujson.dumps(
            {
                "roas": [
                    {"asn": "64496", "prefix": "192.0.2.0/24", "maxLength": 26, "ta": "APNIC RPKI Root"},
                    {
                        "asn": "AS64497",
                        "prefix": "2001:db8::/32",
                        "maxLength": 40,
                        "ta": "RIPE NCC RPKI Root",
                    },
                    {
                        # Filtered out by SLURM due to origin
                        "asn": "64498",
                        "prefix": "192.0.2.0/24",
                        "maxLength": 32,
                        "ta": "APNIC RPKI Root",
                    },
                    {
                        # Filtered out by SLURM due to prefix
                        "asn": "AS64496",
                        "prefix": "203.0.113.0/25",
                        "maxLength": 26,
                        "ta": "APNIC RPKI Root",
                    },
                    {
                        # Filtered out by SLURM due to prefix
                        "asn": "AS64497",
                        "prefix": "203.0.113.0/26",
                        "maxLength": 26,
                        "ta": "APNIC RPKI Root",
                    },
                    {
                        # Filtered out by SLURM due to prefix plus origin
                        "asn": "AS64497",
                        "prefix": "203.0.113.128/26",
                        "maxLength": 26,
                        "ta": "APNIC RPKI Root",
                    },
                ]
            }
        )

        slurm_data = ujson.dumps(
            {
                "slurmVersion": 1,
                "validationOutputFilters": {
                    "prefixFilters": [
                        {
                            "prefix": "203.0.113.0/25",
                            "comment": "All VRPs encompassed by prefix",
                        },
                        {
                            "asn": 64498,
                            "comment": "All VRPs matching ASN",
                        },
                        {
                            "prefix": "203.0.113.128/25",
                            "asn": 64497,
                            "comment": "All VRPs encompassed by prefix, matching ASN",
                        },
                        {
                            # This filters out nothing, the ROA for this prefix has AS 64496
                            "prefix": "192.0.2.0/24",
                            "asn": 64497,
                            "comment": "All VRPs encompassed by prefix, matching ASN",
                        },
                        {
                            # This should not filter out the assertion for 198.51.100/24
                            "prefix": "198.51.100.0/24",
                            "asn": 64496,
                            "comment": "All VRPs encompassed by prefix, matching ASN",
                        },
                    ],
                },
                "locallyAddedAssertions": {
                    "prefixAssertions": [
                        {
                            "asn": 64496,
                            "prefix": "198.51.100.0/24",
                            "comment": "My other important route",
                        },
                        {
                            "asn": 64497,
                            "prefix": "2001:DB8::/32",
                            "maxPrefixLength": 48,
                            "comment": "My other important de-aggregated routes",
                        },
                    ],
                },
            }
        )

        roa_importer = ROADataImporter(rpki_data, slurm_data, mock_dh)
        assert flatten_mock_calls(mock_dh, flatten_objects=True) == [
            [
                "insert_roa_object",
                (),
                {
                    "ip_version": 4,
                    "prefix_str": "192.0.2.0/24",
                    "asn": 64496,
                    "max_length": 26,
                    "trust_anchor": "APNIC RPKI Root",
                },
            ],
            [
                "upsert_rpsl_object",
                ("route/192.0.2.0/24AS64496/ML26/RPKI", "JournalEntryOrigin.pseudo_irr"),
                {"rpsl_guaranteed_no_existing": True},
            ],
            [
                "insert_roa_object",
                (),
                {
                    "ip_version": 6,
                    "prefix_str": "2001:db8::/32",
                    "asn": 64497,
                    "max_length": 40,
                    "trust_anchor": "RIPE NCC RPKI Root",
                },
            ],
            [
                "upsert_rpsl_object",
                ("route6/2001:db8::/32AS64497/ML40/RPKI", "JournalEntryOrigin.pseudo_irr"),
                {"rpsl_guaranteed_no_existing": True},
            ],
            [
                "insert_roa_object",
                (),
                {
                    "ip_version": 4,
                    "prefix_str": "198.51.100.0/24",
                    "asn": 64496,
                    "max_length": 24,
                    "trust_anchor": "SLURM file",
                },
            ],
            [
                "upsert_rpsl_object",
                ("route/198.51.100.0/24AS64496/ML24/RPKI", "JournalEntryOrigin.pseudo_irr"),
                {"rpsl_guaranteed_no_existing": True},
            ],
            [
                "insert_roa_object",
                (),
                {
                    "ip_version": 6,
                    "prefix_str": "2001:db8::/32",
                    "asn": 64497,
                    "max_length": 48,
                    "trust_anchor": "SLURM file",
                },
            ],
            [
                "upsert_rpsl_object",
                ("route6/2001:db8::/32AS64497/ML48/RPKI", "JournalEntryOrigin.pseudo_irr"),
                {"rpsl_guaranteed_no_existing": True},
            ],
        ]

        assert roa_importer.roa_objs[0]._rpsl_object.scopefilter_status == ScopeFilterStatus.out_scope_as
        assert roa_importer.roa_objs[0]._rpsl_object.source() == RPKI_IRR_PSEUDO_SOURCE
        assert roa_importer.roa_objs[0]._rpsl_object.parsed_data == {
            "origin": "AS64496",
            "route": "192.0.2.0/24",
            "rpki_max_length": 26,
            "source": "RPKI",
        }
        assert (
            roa_importer.roa_objs[0]._rpsl_object.render_rpsl_text()
            == textwrap.dedent(
                """
            route:          192.0.2.0/24
            descr:          RPKI ROA for 192.0.2.0/24 / AS64496
            remarks:        This AS64496 route object represents routing data retrieved
                            from the RPKI. This route object is the result of an automated
                            RPKI-to-IRR conversion process performed by IRRd.
            max-length:     26
            origin:         AS64496
            source:         RPKI  # Trust Anchor: APNIC RPKI Root
            """
            ).strip()
            + "\n"
        )

    def test_invalid_rpki_json(self, monkeypatch, mock_scopefilter):
        mock_dh = Mock(spec=DatabaseHandler)

        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter("invalid", None, mock_dh)

        assert "Unable to parse ROA input: invalid JSON: Expected object or value" in str(rpe.value)

        data = ujson.dumps({"invalid root": 42})
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, None, mock_dh)
        assert 'Unable to parse ROA input: root key "roas" not found' in str(rpe.value)

        assert flatten_mock_calls(mock_dh) == []

    def test_invalid_data_in_roa(self, monkeypatch, mock_scopefilter):
        mock_dh = Mock(spec=DatabaseHandler)

        data = ujson.dumps(
            {
                "roas": [
                    {"asn": "AS64496", "prefix": "192.0.2.999/24", "maxLength": 26, "ta": "APNIC RPKI Root"}
                ]
            }
        )
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, None, mock_dh)
        assert "Invalid value in ROA or SLURM: '192.0.2.999': single byte must be 0 <= byte < 256" in str(
            rpe.value
        )

        data = ujson.dumps(
            {"roas": [{"asn": "ASx", "prefix": "192.0.2.0/24", "maxLength": 24, "ta": "APNIC RPKI Root"}]}
        )
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, None, mock_dh)
        assert "Invalid AS number ASX: number part is not numeric" in str(rpe.value)

        data = ujson.dumps({"roas": [{"prefix": "192.0.2.0/24", "maxLength": 24, "ta": "APNIC RPKI Root"}]})
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, None, mock_dh)
        assert "Unable to parse ROA record: missing key 'asn'" in str(rpe.value)

        data = ujson.dumps(
            {"roas": [{"asn": "AS64496", "prefix": "192.0.2.0/24", "maxLength": 22, "ta": "APNIC RPKI Root"}]}
        )
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, None, mock_dh)
        assert "Invalid ROA: prefix size 24 is smaller than max length 22" in str(rpe.value)

        data = ujson.dumps(
            {
                "roas": [
                    {"asn": "AS64496", "prefix": "192.0.2.0/24", "maxLength": "xx", "ta": "APNIC RPKI Root"}
                ]
            }
        )
        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter(data, None, mock_dh)
        assert "xx" in str(rpe.value)

        assert flatten_mock_calls(mock_dh) == []

    def test_invalid_slurm_version(self, monkeypatch, mock_scopefilter):
        mock_dh = Mock(spec=DatabaseHandler)

        with pytest.raises(ROAParserException) as rpe:
            ROADataImporter('{"roas": []}', '{"slurmVersion": 2}', mock_dh)

        assert "SLURM data has invalid version: 2" in str(rpe.value)
