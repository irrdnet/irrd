import datetime
from unittest.mock import create_autospec

from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.preload import Preloader

from ...utils.test_utils import flatten_mock_calls
from ..jobs import TransactionTimePreloadSignaller


class TestTransactionTimePreloadSignaller:
    def test_run(self, monkeypatch):
        mock_dh = create_autospec(DatabaseHandler)
        mock_preloader = create_autospec(Preloader)

        monkeypatch.setattr("irrd.mirroring.jobs.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.jobs.Preloader", lambda enable_queries: mock_preloader)

        mock_dh.timestamp_last_committed_transaction = lambda: datetime.datetime(2023, 1, 1)

        signaller = TransactionTimePreloadSignaller()
        signaller.run()
        signaller.run()
        # Should only have one call
        assert flatten_mock_calls(mock_preloader) == [["signal_reload", (), {}]]

        mock_preloader.reset_mock()
        mock_dh.timestamp_last_committed_transaction = lambda: datetime.datetime(2023, 1, 2)
        signaller.run()
        assert flatten_mock_calls(mock_preloader) == [["signal_reload", (), {}]]

    def test_fail_database_query(self, monkeypatch, caplog):
        mock_dh = create_autospec(DatabaseHandler)
        mock_preloader = create_autospec(Preloader)

        monkeypatch.setattr("irrd.mirroring.jobs.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.jobs.Preloader", lambda enable_queries: mock_preloader)

        mock_dh.timestamp_last_committed_transaction.side_effect = Exception()

        signaller = TransactionTimePreloadSignaller()
        signaller.run()
        assert flatten_mock_calls(mock_preloader) == [["signal_reload", (), {}]]
        assert "exception occurred" in caplog.text

    def test_fail_preload(self, monkeypatch, caplog):
        mock_dh = create_autospec(DatabaseHandler)
        mock_preloader = create_autospec(Preloader)

        monkeypatch.setattr("irrd.mirroring.jobs.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.jobs.Preloader", lambda enable_queries: mock_preloader)

        mock_preloader.signal_reload.side_effect = Exception()

        signaller = TransactionTimePreloadSignaller()
        signaller.run()
        assert "Failed to send" in caplog.text
