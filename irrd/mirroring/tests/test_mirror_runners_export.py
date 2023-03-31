import gzip
import os
from itertools import cycle, repeat
from pathlib import Path
from unittest.mock import Mock

from irrd.routepref.status import RoutePreferenceStatus
from irrd.rpki.status import RPKIStatus
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.utils.test_utils import flatten_mock_calls

from ..mirror_runners_export import EXPORT_PERMISSIONS, SourceExportRunner


class TestSourceExportRunner:
    def test_export(self, tmpdir, config_override, monkeypatch, caplog):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "export_destination": str(tmpdir),
                    }
                }
            }
        )

        mock_dh = Mock()
        mock_dq = Mock()
        mock_dsq = Mock()

        monkeypatch.setattr("irrd.mirroring.mirror_runners_export.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_export.RPSLDatabaseQuery", lambda: mock_dq)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_export.DatabaseStatusQuery", lambda: mock_dsq)

        responses = cycle(
            [
                repeat({"serial_newest_seen": "424242"}),
                [
                    # The CRYPT-PW hash must not appear in the output
                    {"object_text": "object 1 🦄\nauth: CRYPT-PW foobar\n"},
                    {"object_text": "object 2 🌈\n"},
                ],
            ]
        )
        mock_dh.execute_query = lambda q: next(responses)

        runner = SourceExportRunner("TEST")
        runner.run()
        runner.run()

        serial_filename = tmpdir + "/TEST.CURRENTSERIAL"
        assert oct(os.lstat(serial_filename).st_mode)[-3:] == oct(EXPORT_PERMISSIONS)[-3:]
        with open(serial_filename) as fh:
            assert fh.read() == "424242"

        export_filename = tmpdir + "/test.db.gz"
        assert oct(os.lstat(export_filename).st_mode)[-3:] == oct(EXPORT_PERMISSIONS)[-3:]
        with gzip.open(export_filename) as fh:
            assert (
                fh.read().decode("utf-8")
                == "object 1 🦄\nauth: CRYPT-PW DummyValue  # Filtered for security\n\nobject 2 🌈\n\n# EOF\n"
            )

        assert flatten_mock_calls(mock_dh) == [
            ["record_serial_exported", ("TEST", "424242"), {}],
            ["commit", (), {}],
            ["close", (), {}],
            ["record_serial_exported", ("TEST", "424242"), {}],
            ["commit", (), {}],
            ["close", (), {}],
        ]
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["rpki_status", ([RPKIStatus.not_found, RPKIStatus.valid],), {}],
            ["scopefilter_status", ([ScopeFilterStatus.in_scope],), {}],
            ["route_preference_status", ([RoutePreferenceStatus.visible],), {}],
            ["sources", (["TEST"],), {}],
            ["rpki_status", ([RPKIStatus.not_found, RPKIStatus.valid],), {}],
            ["scopefilter_status", ([ScopeFilterStatus.in_scope],), {}],
            ["route_preference_status", ([RoutePreferenceStatus.visible],), {}],
        ]
        assert "Starting a source export for TEST" in caplog.text
        assert "Export for TEST complete" in caplog.text

    def test_export_unfiltered(self, tmpdir, config_override, monkeypatch, caplog):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "export_destination_unfiltered": str(tmpdir),
                    }
                }
            }
        )

        mock_dh = Mock()
        mock_dq = Mock()
        mock_dsq = Mock()

        monkeypatch.setattr("irrd.mirroring.mirror_runners_export.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_export.RPSLDatabaseQuery", lambda: mock_dq)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_export.DatabaseStatusQuery", lambda: mock_dsq)

        responses = cycle(
            [
                repeat({"serial_newest_seen": "424242"}),
                [
                    # The CRYPT-PW hash should appear in the output
                    {"object_text": "object 1 🦄\nauth: CRYPT-PW foobar\n"},
                    {"object_text": "object 2 🌈\n"},
                ],
            ]
        )
        mock_dh.execute_query = lambda q: next(responses)

        runner = SourceExportRunner("TEST")
        runner.run()

        serial_filename = tmpdir + "/TEST.CURRENTSERIAL"
        assert oct(os.lstat(serial_filename).st_mode)[-3:] == oct(EXPORT_PERMISSIONS)[-3:]
        with open(serial_filename) as fh:
            assert fh.read() == "424242"

        export_filename = tmpdir + "/test.db.gz"
        assert oct(os.lstat(export_filename).st_mode)[-3:] == oct(EXPORT_PERMISSIONS)[-3:]
        with gzip.open(export_filename) as fh:
            assert fh.read().decode("utf-8") == "object 1 🦄\nauth: CRYPT-PW foobar\n\nobject 2 🌈\n\n# EOF\n"

    def test_failure(self, tmpdir, config_override, monkeypatch, caplog):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "export_destination": str(tmpdir),
                    }
                }
            }
        )

        mock_dh = Mock()
        mock_dsq = Mock()
        monkeypatch.setattr("irrd.mirroring.mirror_runners_export.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_export.DatabaseStatusQuery", lambda: mock_dsq)
        mock_dh.execute_query = Mock(side_effect=ValueError("expected-test-error"))

        runner = SourceExportRunner("TEST")
        runner.run()

        assert "An exception occurred while attempting to run an export for TEST" in caplog.text
        assert "expected-test-error" in caplog.text

    def test_export_no_serial(self, tmpdir, config_override, monkeypatch, caplog):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "export_destination": str(tmpdir),
                    }
                }
            }
        )

        mock_dh = Mock()
        mock_dq = Mock()
        mock_dsq = Mock()

        monkeypatch.setattr("irrd.mirroring.mirror_runners_export.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_export.RPSLDatabaseQuery", lambda: mock_dq)
        monkeypatch.setattr("irrd.mirroring.mirror_runners_export.DatabaseStatusQuery", lambda: mock_dsq)

        responses = cycle(
            [
                iter([]),
                [
                    # The CRYPT-PW hash must not appear in the output
                    {"object_text": "object 1 🦄\nauth: CRYPT-PW foobar\n"},
                    {"object_text": "object 2 🌈\n"},
                ],
            ]
        )
        mock_dh.execute_query = lambda q: next(responses)

        runner = SourceExportRunner("TEST")
        runner.run()
        runner.run()

        serial_filename = Path(tmpdir + "/TEST.CURRENTSERIAL")
        assert not serial_filename.exists()

        export_filename = tmpdir + "/test.db.gz"
        with gzip.open(export_filename) as fh:
            assert (
                fh.read().decode("utf-8")
                == "object 1 🦄\nauth: CRYPT-PW DummyValue  # Filtered for security\n\nobject 2 🌈\n\n# EOF\n"
            )

        assert "Starting a source export for TEST" in caplog.text
        assert "Export for TEST complete" in caplog.text
