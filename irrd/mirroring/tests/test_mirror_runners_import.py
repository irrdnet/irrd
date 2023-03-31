from base64 import b64decode
from io import BytesIO
from typing import List
from unittest.mock import Mock
from urllib.error import URLError

import pytest

from irrd.routepref.routepref import update_route_preference_status
from irrd.rpki.importer import ROAParserException
from irrd.rpki.validators import BulkRouteROAValidator
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.database_handler import DatabaseHandler
from irrd.utils.test_utils import flatten_mock_calls

from ..mirror_runners_import import (
    NRTMImportUpdateStreamRunner,
    ROAImportRunner,
    RoutePreferenceUpdateRunner,
    RPSLMirrorFullImportRunner,
    RPSLMirrorImportUpdateRunner,
    ScopeFilterUpdateRunner,
)


class TestRPSLMirrorImportUpdateRunner:
    def test_full_import_call(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        mock_full_import_runner = Mock()

        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseStatusQuery", lambda: mock_dq)
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.RPSLMirrorFullImportRunner",
            lambda source: mock_full_import_runner,
        )

        mock_dh.execute_query = lambda q: iter([])
        runner = RPSLMirrorImportUpdateRunner(source="TEST")
        runner.run()

        assert flatten_mock_calls(mock_dq) == [["source", ("TEST",), {}]]
        assert flatten_mock_calls(mock_dh) == [["commit", (), {}], ["close", (), {}]]

        assert len(mock_full_import_runner.mock_calls) == 1
        assert mock_full_import_runner.mock_calls[0][0] == "run"

    def test_force_reload(self, monkeypatch, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "nrtm_host": "192.0.2.1",
                    }
                }
            }
        )
        mock_dh = Mock()
        mock_dq = Mock()
        mock_full_import_runner = Mock()

        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseStatusQuery", lambda: mock_dq)
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.RPSLMirrorFullImportRunner",
            lambda source: mock_full_import_runner,
        )

        mock_dh.execute_query = lambda q: iter([{"serial_newest_mirror": 424242, "force_reload": True}])
        runner = RPSLMirrorImportUpdateRunner(source="TEST")
        runner.run()

        assert flatten_mock_calls(mock_dq) == [["source", ("TEST",), {}]]
        assert flatten_mock_calls(mock_dh) == [["commit", (), {}], ["close", (), {}]]

        assert len(mock_full_import_runner.mock_calls) == 1
        assert mock_full_import_runner.mock_calls[0][0] == "run"

    def test_update_stream_call(self, monkeypatch, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "nrtm_host": "192.0.2.1",
                    }
                }
            }
        )
        mock_dh = Mock()
        mock_dq = Mock()
        mock_stream_runner = Mock()

        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseStatusQuery", lambda: mock_dq)
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.NRTMImportUpdateStreamRunner",
            lambda source: mock_stream_runner,
        )

        mock_dh.execute_query = lambda q: iter([{"serial_newest_mirror": 424242, "force_reload": False}])
        runner = RPSLMirrorImportUpdateRunner(source="TEST")
        runner.run()

        assert flatten_mock_calls(mock_dq) == [["source", ("TEST",), {}]]
        assert flatten_mock_calls(mock_dh) == [["commit", (), {}], ["close", (), {}]]

        assert len(mock_stream_runner.mock_calls) == 1
        assert mock_stream_runner.mock_calls[0][0] == "run"
        assert mock_stream_runner.mock_calls[0][1] == (424242,)

    def test_io_exception_handling(self, monkeypatch, caplog):
        mock_dh = Mock()
        mock_dq = Mock()
        mock_full_import_runner = Mock()

        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseStatusQuery", lambda: mock_dq)
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.RPSLMirrorFullImportRunner",
            lambda source: mock_full_import_runner,
        )
        mock_full_import_runner.run = Mock(side_effect=ConnectionResetError("test-error"))

        mock_dh.execute_query = lambda q: iter([{"serial_newest_mirror": 424242, "force_reload": False}])
        runner = RPSLMirrorImportUpdateRunner(source="TEST")
        runner.run()

        assert flatten_mock_calls(mock_dh) == [["close", (), {}]]
        assert "An error occurred while attempting a mirror update or initial import for TEST" in caplog.text
        assert "test-error" in caplog.text
        assert "Traceback" not in caplog.text

    def test_unexpected_exception_handling(self, monkeypatch, caplog):
        mock_dh = Mock()
        mock_dq = Mock()
        mock_full_import_runner = Mock()

        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseStatusQuery", lambda: mock_dq)
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.RPSLMirrorFullImportRunner",
            lambda source: mock_full_import_runner,
        )
        mock_full_import_runner.run = Mock(side_effect=Exception("test-error"))

        mock_dh.execute_query = lambda q: iter([{"serial_newest_mirror": 424242, "force_reload": False}])
        runner = RPSLMirrorImportUpdateRunner(source="TEST")
        runner.run()

        assert flatten_mock_calls(mock_dh) == [["close", (), {}]]
        assert (
            "An exception occurred while attempting a mirror update or initial import for TEST" in caplog.text
        )
        assert "test-error" in caplog.text
        assert "Traceback" in caplog.text


class TestRPSLMirrorFullImportRunner:
    def test_run_import_ftp(self, monkeypatch, config_override):
        config_override(
            {
                "rpki": {"roa_source": "https://example.com/roa.json"},
                "sources": {
                    "TEST": {
                        "import_source": ["ftp://host/source1.gz", "ftp://host/source2"],
                        "import_serial_source": "ftp://host/serial",
                    }
                },
            }
        )

        mock_dh = Mock()
        request = Mock()
        MockMirrorFileImportParser.rpsl_data_calls = []
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.MirrorFileImportParser", MockMirrorFileImportParser
        )
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.request", request)

        mock_bulk_validator_init = Mock()
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.BulkRouteROAValidator", mock_bulk_validator_init
        )

        responses = {
            # gzipped data, contains 'source1'
            "ftp://host/source1.gz": b64decode("H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA"),
            "ftp://host/source2": b"source2",
            "ftp://host/serial": b"424242",
        }
        request.urlopen = lambda url, timeout: MockUrlopenResponse(responses[url])
        RPSLMirrorFullImportRunner("TEST").run(mock_dh, serial_newest_mirror=424241)

        assert MockMirrorFileImportParser.rpsl_data_calls == ["source1", "source2"]
        assert flatten_mock_calls(mock_dh) == [
            ["delete_all_rpsl_objects_with_journal", ("TEST",), {}],
            ["disable_journaling", (), {}],
            ["record_serial_newest_mirror", ("TEST", 424242), {}],
        ]
        assert mock_bulk_validator_init.mock_calls[0][1][0] == mock_dh

    def test_failed_import_ftp(self, monkeypatch, config_override):
        config_override(
            {
                "rpki": {"roa_source": "https://example.com/roa.json"},
                "sources": {
                    "TEST": {
                        "import_source": "ftp://host/source1.gz",
                    }
                },
            }
        )

        mock_dh = Mock()
        request = Mock()
        MockMirrorFileImportParser.rpsl_data_calls = []
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.MirrorFileImportParser", MockMirrorFileImportParser
        )
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.request", request)

        mock_bulk_validator_init = Mock()
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.BulkRouteROAValidator", mock_bulk_validator_init
        )

        request.urlopen = lambda url, timeout: MockUrlopenResponse(b"", fail=True)
        with pytest.raises(IOError):
            RPSLMirrorFullImportRunner("TEST").run(mock_dh, serial_newest_mirror=424241)

    def test_run_import_local_file(self, monkeypatch, config_override, tmpdir):
        tmp_import_source1 = tmpdir + "/source1.rpsl.gz"
        with open(tmp_import_source1, "wb") as fh:
            # gzipped data, contains 'source1'
            fh.write(b64decode("H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA"))
        tmp_import_source2 = tmpdir + "/source2.rpsl"
        with open(tmp_import_source2, "w") as fh:
            fh.write("source2")
        tmp_import_serial = tmpdir + "/serial"
        with open(tmp_import_serial, "w") as fh:
            fh.write("424242")

        config_override(
            {
                "rpki": {"roa_source": None},
                "sources": {
                    "TEST": {
                        "import_source": [
                            "file://" + str(tmp_import_source1),
                            "file://" + str(tmp_import_source2),
                        ],
                        "import_serial_source": "file://" + str(tmp_import_serial),
                    }
                },
            }
        )

        mock_dh = Mock()
        MockMirrorFileImportParser.rpsl_data_calls = []
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.MirrorFileImportParser", MockMirrorFileImportParser
        )

        RPSLMirrorFullImportRunner("TEST").run(mock_dh)

        assert MockMirrorFileImportParser.rpsl_data_calls == ["source1", "source2"]
        assert flatten_mock_calls(mock_dh) == [
            ["delete_all_rpsl_objects_with_journal", ("TEST",), {}],
            ["disable_journaling", (), {}],
            ["record_serial_newest_mirror", ("TEST", 424242), {}],
        ]

    def test_no_serial_ftp(self, monkeypatch, config_override):
        config_override(
            {
                "rpki": {"roa_source": None},
                "sources": {
                    "TEST": {
                        "import_source": ["ftp://host/source1.gz", "ftp://host/source2"],
                    }
                },
            }
        )

        mock_dh = Mock()
        request = Mock()
        MockMirrorFileImportParser.rpsl_data_calls = []
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.MirrorFileImportParser", MockMirrorFileImportParser
        )
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.request", request)

        responses = {
            # gzipped data, contains 'source1'
            "ftp://host/source1.gz": b64decode("H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA"),
            "ftp://host/source2": b"source2",
        }
        request.urlopen = lambda url, timeout: MockUrlopenResponse(responses[url])
        RPSLMirrorFullImportRunner("TEST").run(mock_dh, serial_newest_mirror=42)

        assert MockMirrorFileImportParser.rpsl_data_calls == ["source1", "source2"]
        assert flatten_mock_calls(mock_dh) == [
            ["delete_all_rpsl_objects_with_journal", ("TEST",), {}],
            ["disable_journaling", (), {}],
        ]

    def test_import_cancelled_serial_too_old(self, monkeypatch, config_override, caplog):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "import_source": ["ftp://host/source1.gz", "ftp://host/source2"],
                        "import_serial_source": "ftp://host/serial",
                    }
                }
            }
        )

        mock_dh = Mock()
        request = Mock()
        MockMirrorFileImportParser.rpsl_data_calls = []
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.MirrorFileImportParser", MockMirrorFileImportParser
        )
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.request", request)

        responses = {
            # gzipped data, contains 'source1'
            "ftp://host/source1.gz": b64decode("H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA"),
            "ftp://host/source2": b"source2",
            "ftp://host/serial": b"424242",
        }
        request.urlopen = lambda url, timeout: MockUrlopenResponse(responses[url])
        RPSLMirrorFullImportRunner("TEST").run(mock_dh, serial_newest_mirror=424243)

        assert not MockMirrorFileImportParser.rpsl_data_calls
        assert flatten_mock_calls(mock_dh) == []
        assert "Current newest serial seen for TEST is 424243, import_serial is 424242, cancelling import."

    def test_import_force_reload_with_serial_too_old(self, monkeypatch, config_override):
        config_override(
            {
                "rpki": {"roa_source": None},
                "sources": {
                    "TEST": {
                        "import_source": ["ftp://host/source1.gz", "ftp://host/source2"],
                        "import_serial_source": "ftp://host/serial",
                    }
                },
            }
        )

        mock_dh = Mock()
        request = Mock()
        MockMirrorFileImportParser.rpsl_data_calls = []
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.MirrorFileImportParser", MockMirrorFileImportParser
        )
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.request", request)

        responses = {
            # gzipped data, contains 'source1'
            "ftp://host/source1.gz": b64decode("H4sIAE4CfFsAAyvOLy1KTjUEAE5Fj0oHAAAA"),
            "ftp://host/source2": b"source2",
            "ftp://host/serial": b"424242",
        }
        request.urlopen = lambda url, timeout: MockUrlopenResponse(responses[url])
        RPSLMirrorFullImportRunner("TEST").run(mock_dh, serial_newest_mirror=424243, force_reload=True)

        assert MockMirrorFileImportParser.rpsl_data_calls == ["source1", "source2"]
        assert flatten_mock_calls(mock_dh) == [
            ["delete_all_rpsl_objects_with_journal", ("TEST",), {}],
            ["disable_journaling", (), {}],
            ["record_serial_newest_mirror", ("TEST", 424242), {}],
        ]

    def test_missing_source_settings_ftp(self, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "import_serial_source": "ftp://host/serial",
                    }
                }
            }
        )

        mock_dh = Mock()
        RPSLMirrorFullImportRunner("TEST").run(mock_dh)
        assert not flatten_mock_calls(mock_dh)

    def test_unsupported_protocol(self, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "import_source": "ftp://host/source1.gz",
                        "import_serial_source": "gopher://host/serial",
                    }
                }
            }
        )

        mock_dh = Mock()
        with pytest.raises(ValueError) as ve:
            RPSLMirrorFullImportRunner("TEST").run(mock_dh)
        assert "scheme gopher is not supported" in str(ve.value)


class MockUrlopenResponse(BytesIO):
    def __init__(self, bytes: bytes, fail: bool = False):
        if fail:
            raise URLError("error")
        super().__init__(bytes)


class MockMirrorFileImportParser:
    rpsl_data_calls: List[str] = []

    def __init__(
        self, source, filename, serial, database_handler, direct_error_return=False, roa_validator=None
    ):
        self.filename = filename
        assert source == "TEST"
        assert serial is None

    def run_import(self):
        with open(self.filename) as f:
            self.rpsl_data_calls.append(f.read())


class TestROAImportRunner:
    # As the code for retrieving files from HTTP, FTP or local file
    # is shared between ROAImportRunner and RPSLMirrorFullImportRunner,
    # not all protocols are tested here.
    def test_run_import_http_file_success(self, monkeypatch, config_override, tmpdir, caplog):
        slurm_path = str(tmpdir) + "/slurm.json"
        config_override(
            {"rpki": {"roa_source": "https://host/roa.json", "slurm_source": "file://" + slurm_path}}
        )

        class MockRequestsSuccess:
            status_code = 200

            def __init__(self, url, stream, timeout):
                assert url == "https://host/roa.json"
                assert stream
                assert timeout

            def iter_content(self, size):
                return iter([b"roa_", b"data"])

        with open(slurm_path, "wb") as fh:
            fh.write(b"slurm_data")

        mock_dh = Mock(spec=DatabaseHandler)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.ROADataImporter", MockROADataImporter)
        mock_bulk_validator = Mock(spec=BulkRouteROAValidator)
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.BulkRouteROAValidator", lambda dh, roas: mock_bulk_validator
        )
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.requests.get", MockRequestsSuccess)
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.notify_rpki_invalid_owners", lambda dh, invalids: 1
        )

        mock_bulk_validator.validate_all_routes = lambda: (
            [{"rpsl_pk": "pk_now_valid1"}, {"rpsl_pk": "pk_now_valid2"}],
            [{"rpsl_pk": "pk_now_invalid1"}, {"rpsl_pk": "pk_now_invalid2"}],
            [{"rpsl_pk": "pk_now_unknown1"}, {"rpsl_pk": "pk_now_unknown2"}],
        )
        ROAImportRunner().run()

        assert flatten_mock_calls(mock_dh) == [
            ["disable_journaling", (), {}],
            ["delete_all_roa_objects", (), {}],
            ["delete_all_rpsl_objects_with_journal", ("RPKI",), {"journal_guaranteed_empty": True}],
            ["commit", (), {}],
            ["enable_journaling", (), {}],
            [
                "update_rpki_status",
                (),
                {
                    "rpsl_objs_now_valid": [{"rpsl_pk": "pk_now_valid1"}, {"rpsl_pk": "pk_now_valid2"}],
                    "rpsl_objs_now_invalid": [{"rpsl_pk": "pk_now_invalid1"}, {"rpsl_pk": "pk_now_invalid2"}],
                    "rpsl_objs_now_not_found": [
                        {"rpsl_pk": "pk_now_unknown1"},
                        {"rpsl_pk": "pk_now_unknown2"},
                    ],
                },
            ],
            ["commit", (), {}],
            ["close", (), {}],
        ]
        assert (
            "2 newly valid, 2 newly invalid, 2 newly not_found routes, 1 emails sent to contacts of newly"
            " invalid authoritative objects"
            in caplog.text
        )

    def test_run_import_http_file_failed_download(self, monkeypatch, config_override, tmpdir, caplog):
        config_override(
            {
                "rpki": {
                    "roa_source": "https://host/roa.json",
                }
            }
        )

        class MockRequestsSuccess:
            status_code = 500
            content = "expected-test-error"

            def __init__(self, url, stream, timeout):
                assert url == "https://host/roa.json"
                assert stream
                assert timeout

        mock_dh = Mock(spec=DatabaseHandler)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.requests.get", MockRequestsSuccess)

        ROAImportRunner().run()
        assert "Failed to download https://host/roa.json: 500: expected-test-error" in caplog.text

    def test_exception_handling(self, monkeypatch, config_override, tmpdir, caplog):
        tmp_roa_source = tmpdir + "/roa.json"
        with open(tmp_roa_source, "wb") as fh:
            fh.write(b"roa_data")
        config_override(
            {
                "rpki": {
                    "roa_source": "file://" + str(tmp_roa_source),
                }
            }
        )

        mock_dh = Mock(spec=DatabaseHandler)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)

        mock_importer = Mock(side_effect=ValueError("expected-test-error-1"))
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.ROADataImporter", mock_importer)
        ROAImportRunner().run()

        mock_importer = Mock(side_effect=ROAParserException("expected-test-error-2"))
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.ROADataImporter", mock_importer)
        ROAImportRunner().run()

        assert flatten_mock_calls(mock_dh) == 2 * [
            ["disable_journaling", (), {}],
            ["delete_all_roa_objects", (), {}],
            ["delete_all_rpsl_objects_with_journal", ("RPKI",), {"journal_guaranteed_empty": True}],
            ["close", (), {}],
        ]

        assert "expected-test-error-1" in caplog.text
        assert "expected-test-error-2" in caplog.text

    def test_file_error_handling(self, monkeypatch, config_override, tmpdir, caplog):
        tmp_roa_source = tmpdir + "/roa.json"
        config_override(
            {
                "rpki": {
                    "roa_source": "file://" + str(tmp_roa_source),
                }
            }
        )

        mock_dh = Mock(spec=DatabaseHandler)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)
        ROAImportRunner().run()

        assert flatten_mock_calls(mock_dh) == [
            ["disable_journaling", (), {}],
            ["delete_all_roa_objects", (), {}],
            ["delete_all_rpsl_objects_with_journal", ("RPKI",), {"journal_guaranteed_empty": True}],
            ["close", (), {}],
        ]

        assert "No such file or directory" in caplog.text


class MockROADataImporter:
    def __init__(self, rpki_text: str, slurm_text: str, database_handler: DatabaseHandler):
        assert rpki_text == "roa_data"
        assert slurm_text == "slurm_data"
        self.roa_objs = ["roa1", "roa2"]


class TestScopeFilterUpdateRunner:
    def test_run(self, monkeypatch, config_override, tmpdir, caplog):
        mock_dh = Mock(spec=DatabaseHandler)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)
        mock_scopefilter = Mock(spec=ScopeFilterValidator)
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.ScopeFilterValidator", lambda: mock_scopefilter
        )

        mock_scopefilter.validate_all_rpsl_objects = lambda database_handler: (
            [{"rpsl_pk": "pk_now_in_scope1"}, {"rpsl_pk": "pk_now_in_scope2"}],
            [{"rpsl_pk": "pk_now_out_scope_as1"}, {"rpsl_pk": "pk_now_out_scope_as2"}],
            [{"rpsl_pk": "pk_now_out_scope_prefix1"}, {"rpsl_pk": "pk_now_out_scope_prefix2"}],
        )
        ScopeFilterUpdateRunner().run()

        assert flatten_mock_calls(mock_dh) == [
            [
                "update_scopefilter_status",
                (),
                {
                    "rpsl_objs_now_in_scope": [
                        {"rpsl_pk": "pk_now_in_scope1"},
                        {"rpsl_pk": "pk_now_in_scope2"},
                    ],
                    "rpsl_objs_now_out_scope_as": [
                        {"rpsl_pk": "pk_now_out_scope_as1"},
                        {"rpsl_pk": "pk_now_out_scope_as2"},
                    ],
                    "rpsl_objs_now_out_scope_prefix": [
                        {"rpsl_pk": "pk_now_out_scope_prefix1"},
                        {"rpsl_pk": "pk_now_out_scope_prefix2"},
                    ],
                },
            ],
            ["commit", (), {}],
            ["close", (), {}],
        ]
        assert "2 newly in scope, 2 newly out of scope AS, 2 newly out of scope prefix" in caplog.text

    def test_exception_handling(self, monkeypatch, config_override, tmpdir, caplog):
        mock_dh = Mock(spec=DatabaseHandler)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)
        mock_scopefilter = Mock(side_effect=ValueError("expected-test-error"))
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.ScopeFilterValidator", mock_scopefilter)

        ScopeFilterUpdateRunner().run()

        assert flatten_mock_calls(mock_dh) == [["close", (), {}]]
        assert "expected-test-error" in caplog.text


class TestRoutePreferenceUpdateRunner:
    def test_run(self, monkeypatch, config_override, tmpdir, caplog):
        mock_dh = Mock(spec=DatabaseHandler)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)
        mock_update_function = Mock(spec=update_route_preference_status)
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.update_route_preference_status", mock_update_function
        )

        RoutePreferenceUpdateRunner().run()

        assert flatten_mock_calls(mock_dh) == [["commit", (), {}], ["close", (), {}]]

    def test_exception_handling(self, monkeypatch, config_override, tmpdir, caplog):
        mock_dh = Mock(spec=DatabaseHandler)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.DatabaseHandler", lambda: mock_dh)
        mock_update_function = Mock(side_effect=ValueError("expected-test-error"))
        monkeypatch.setattr(
            "irrd.mirroring.mirror_runners_import.update_route_preference_status", mock_update_function
        )

        RoutePreferenceUpdateRunner().run()

        assert flatten_mock_calls(mock_dh) == [["close", (), {}]]
        assert "expected-test-error" in caplog.text


class TestNRTMImportUpdateStreamRunner:
    def test_run_import(self, monkeypatch, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "nrtm_host": "192.0.2.1",
                        "nrtm_port": 43,
                    }
                }
            }
        )

        def mock_whois_query(host, port, query, end_markings) -> str:
            assert host == "192.0.2.1"
            assert port == 43
            assert query == "-g TEST:3:424243-LAST"
            assert "TEST" in end_markings[0]
            return "response"

        mock_dh = Mock()
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.NRTMStreamParser", MockNRTMStreamParser)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_import.whois_query", mock_whois_query)

        NRTMImportUpdateStreamRunner("TEST").run(424242, mock_dh)

    def test_missing_source_settings(self, monkeypatch, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "nrtm_port": "4343",
                    }
                }
            }
        )

        mock_dh = Mock()
        NRTMImportUpdateStreamRunner("TEST").run(424242, mock_dh)


class MockNRTMStreamParser:
    def __init__(self, source, response, database_handler):
        assert source == "TEST"
        assert response == "response"
        self.operations = [Mock()]
