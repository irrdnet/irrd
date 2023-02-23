import io
from datetime import datetime

import pytz

from irrd.storage.queries import RPSLDatabaseJournalQuery
from irrd.utils.test_utils import MockDatabaseHandler

from ..expire_journal import expire_journal

EXPIRY_DATE = datetime(2022, 1, 1, tzinfo=pytz.utc)


class TestExpireJournal:
    expected_query = (
        RPSLDatabaseJournalQuery(column_names=["timestamp"])
        .sources(["TEST"])
        .entries_before_date(EXPIRY_DATE)
    )

    def test_expire_confirmed(self, capsys, monkeypatch):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        monkeypatch.setattr("irrd.scripts.expire_journal.DatabaseHandler", MockDatabaseHandler)
        monkeypatch.setattr("sys.stdin", io.StringIO("yes"))

        expire_journal(
            skip_confirmation=False,
            expire_before=EXPIRY_DATE,
            source="TEST",
        )
        output = capsys.readouterr().out
        assert "Found 1 journal entries to delete from the journal for TEST" in output
        self._check_success(mock_dh, output)

    def test_expire_skip_confirmation(self, capsys, monkeypatch):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        monkeypatch.setattr("irrd.scripts.expire_journal.DatabaseHandler", MockDatabaseHandler)

        expire_journal(
            skip_confirmation=True,
            expire_before=EXPIRY_DATE,
            source="TEST",
        )
        output = capsys.readouterr().out
        self._check_success(mock_dh, output)

    def _check_success(self, mock_dh, output):
        assert "Expiry complete" in output
        assert mock_dh.closed
        assert mock_dh.queries == [self.expected_query]
        assert mock_dh.other_calls == [
            ("delete_journal_entries_before_date", {"timestamp": EXPIRY_DATE, "source": "TEST"}),
            ("commit", {}),
        ]

    def test_expire_no_entries(self, capsys, monkeypatch):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[RPSLDatabaseJournalQuery] = iter([])
        monkeypatch.setattr("irrd.scripts.expire_journal.DatabaseHandler", MockDatabaseHandler)

        expire_journal(
            skip_confirmation=True,
            expire_before=EXPIRY_DATE,
            source="TEST",
        )
        output = capsys.readouterr().out
        assert "No journal entries found to expire" in output

        assert mock_dh.closed
        assert mock_dh.queries == [self.expected_query]
        assert not mock_dh.other_calls

    def test_expire_rejected(self, capsys, monkeypatch):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        monkeypatch.setattr("irrd.scripts.expire_journal.DatabaseHandler", MockDatabaseHandler)
        monkeypatch.setattr("sys.stdin", io.StringIO("no"))

        expire_journal(
            skip_confirmation=False,
            expire_before=EXPIRY_DATE,
            source="TEST",
        )
        output = capsys.readouterr().out
        assert "Found 1 journal entries to delete from the journal for TEST" in output
        assert "Deletion cancelled" in output

        assert mock_dh.closed
        [query] = mock_dh.queries
        assert query == RPSLDatabaseJournalQuery(column_names=["timestamp"]).sources(
            ["TEST"]
        ).entries_before_date(EXPIRY_DATE)
        assert not mock_dh.other_calls
