import dataclasses
import gzip
import json
import os
import time
from pathlib import Path
from unittest.mock import create_autospec

from irrd.conf import NRTM4_SERVER_DELTA_EXPIRY_TIME, PASSWORD_HASH_DUMMY_VALUE
from irrd.mirroring.nrtm4 import UPDATE_NOTIFICATION_FILENAME
from irrd.mirroring.nrtm4.jsonseq import jsonseq_decode
from irrd.mirroring.nrtm4.nrtm4_server import NRTM4Server, NRTM4ServerWriter
from irrd.mirroring.nrtm4.tests import MOCK_UNF_PRIVATE_KEY, MOCK_UNF_PRIVATE_KEY_STR
from irrd.mirroring.retrieval import check_file_hash_sha256
from irrd.storage.models import DatabaseOperation, NRTM4ServerDatabaseStatus
from irrd.storage.queries import (
    DatabaseStatusQuery,
    RPSLDatabaseJournalQuery,
    RPSLDatabaseJournalStatisticsQuery,
    RPSLDatabaseQuery,
)
from irrd.utils.crypto import jws_deserialize
from irrd.utils.rpsl_samples import SAMPLE_MNTNER
from irrd.utils.test_utils import MockDatabaseHandler
from irrd.utils.text import dummify_object_text, remove_auth_hashes


class TestNRTM4Server:
    def test_server(self, monkeypatch):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_writer = create_autospec(NRTM4ServerWriter)
        monkeypatch.setattr("irrd.mirroring.nrtm4.nrtm4_server.DatabaseHandler", lambda: mock_dh)
        monkeypatch.setattr("irrd.mirroring.nrtm4.nrtm4_server.NRTM4ServerWriter", mock_writer)
        NRTM4Server("TEST").run()
        assert mock_dh.other_calls == []


class TestNRTM4ServerWriter:
    empty_status = {
        "force_reload": False,
        "nrtm4_server_session_id": None,
        "nrtm4_server_version": None,
        "nrtm4_server_last_update_notification_file_update": None,
        "nrtm4_server_last_snapshot_version": None,
        "nrtm4_server_last_snapshot_global_serial": None,
        "nrtm4_server_last_snapshot_timestamp": None,
        "nrtm4_server_last_snapshot_filename": None,
        "nrtm4_server_last_snapshot_hash": None,
        "nrtm4_server_previous_deltas": None,
    }

    def test_nrtm4_server(self, tmpdir, config_override):
        nrtm_path = Path(tmpdir / "nrtm4")
        nrtm_path.mkdir()
        pid_path = Path(tmpdir / "piddir")
        pid_path.mkdir()

        config_override(
            {
                "piddir": pid_path,
                "sources": {
                    "TEST": {
                        "nrtm4_server_private_key": MOCK_UNF_PRIVATE_KEY_STR,
                        "nrtm4_server_local_path": str(nrtm_path),
                        # "nrtm4_server_snapshot_frequency": 0,
                        "nrtm_dummified_object_classes": "mntner",
                        "nrtm_dummified_attributes": {
                            "descr": "Dummy description for %s",
                            "upd-to": "unread@ripe.net",
                        },
                        "nrtm_dummified_remarks": "Invalid object",
                    }
                },
            }
        )
        mock_dh = MockDatabaseHandler()

        delta_dangling_path = nrtm_path / "nrtm-delta.aaaaa.json.gz"
        snapshot_outdated_path = nrtm_path / "nrtm-snapshot.aaaaa.json.gz"
        for path in delta_dangling_path, snapshot_outdated_path:
            path.touch()
            os.utime(path, (time.time() - 86400, time.time() - 86400))

        # Initial run, no data, no action
        self._run_writer(mock_dh, [])
        assert mock_dh.queries == [
            RPSLDatabaseJournalStatisticsQuery(),
            DatabaseStatusQuery().source("TEST"),
        ]

        # First run, no prior data
        # Expect new snapshot
        self._run_writer(mock_dh, [self.empty_status])
        assert mock_dh.queries == [
            RPSLDatabaseJournalStatisticsQuery(),
            DatabaseStatusQuery().source("TEST"),
            RPSLDatabaseQuery(["object_text", "object_class", "rpsl_pk"])
            .sources(["TEST"])
            .default_suppression(),
        ]

        unf = self._load_unf(nrtm_path)
        assert unf["version"] == 1
        assert unf["deltas"] == []
        assert "next_signing_key" not in unf
        assert unf["snapshot"]["version"] == 1

        snapshot_filename = unf["snapshot"]["url"].split("/")[-1]
        with gzip.open(nrtm_path / snapshot_filename, "rb") as snapshot_file:
            snapshot = list(jsonseq_decode(snapshot_file))
        assert len(snapshot) == 2
        assert snapshot[0]["nrtm_version"] == 4
        assert snapshot[0]["source"] == "TEST"
        assert snapshot[0]["type"] == "snapshot"
        assert snapshot[0]["session_id"] == unf["session_id"]
        assert snapshot[0]["version"] == unf["snapshot"]["version"]
        assert snapshot[1]["object"] == dummify_object_text(
            remove_auth_hashes(SAMPLE_MNTNER), "mntner", "TEST", "TEST-MNT"
        )
        assert PASSWORD_HASH_DUMMY_VALUE in snapshot[1]["object"]

        assert len(mock_dh.other_calls) == 2
        assert mock_dh.other_calls[0][0] == "record_nrtm4_server_status"
        assert mock_dh.other_calls[0][1]["source"] == "TEST"
        assert mock_dh.other_calls[1][0] == "commit"
        status = mock_dh.other_calls[0][1]["status"]
        assert str(status.session_id) == unf["session_id"]
        assert status.version == unf["version"]
        assert status.last_snapshot_version == unf["version"]
        assert status.last_snapshot_filename == snapshot_filename
        assert status.last_snapshot_hash == unf["snapshot"]["hash"]
        assert status.previous_deltas == []

        # Second run, expect one delta to be generated.
        # Snapshot and session not changed
        self._run_writer(
            mock_dh,
            [self._status_to_dict(status)],
            [
                {
                    "operation": DatabaseOperation.add_or_update,
                    "object_text": SAMPLE_MNTNER,
                    "object_class": "mntner",
                    "rpsl_pk": "TEST-MNT",
                }
            ],
        )
        assert mock_dh.queries == [
            RPSLDatabaseJournalStatisticsQuery(),
            DatabaseStatusQuery().source("TEST"),
            RPSLDatabaseJournalQuery()
            .sources(["TEST"])
            .serial_global_range(status.last_snapshot_global_serial + 1),
        ]
        new_unf = self._load_unf(nrtm_path)
        assert new_unf["version"] == 2
        assert new_unf["snapshot"] == unf["snapshot"]
        assert new_unf["session_id"] == unf["session_id"]
        assert new_unf["timestamp"] != unf["timestamp"]

        delta1_filename = new_unf["deltas"][0]["url"].split("/")[-1]
        with gzip.open(nrtm_path / delta1_filename, "rb") as delta_file:
            delta = list(jsonseq_decode(delta_file))
        assert len(delta) == 2
        assert delta[0]["nrtm_version"] == 4
        assert delta[0]["source"] == "TEST"
        assert delta[0]["type"] == "delta"
        assert delta[0]["session_id"] == unf["session_id"]
        assert delta[0]["version"] == new_unf["version"]
        assert delta[1]["object"] == dummify_object_text(
            remove_auth_hashes(SAMPLE_MNTNER), "mntner", "TEST", "TEST-MNT"
        )
        assert delta[1]["action"] == "add_modify"
        assert PASSWORD_HASH_DUMMY_VALUE in delta[1]["object"]

        status = mock_dh.other_calls[0][1]["status"]
        assert len(status.previous_deltas) == 1
        assert status.previous_deltas[0]["filename"] == delta1_filename
        assert status.previous_deltas[0]["hash"] == new_unf["deltas"][0]["hash"]
        assert status.previous_deltas[0]["version"] == new_unf["version"]
        assert status.last_snapshot_hash == new_unf["snapshot"]["hash"]

        # Third run, expect one delete delta to be generated.
        # Snapshot and session not changed
        self._run_writer(
            mock_dh,
            [self._status_to_dict(status)],
            [
                {
                    "operation": DatabaseOperation.delete,
                    "object_class": "mntner",
                    "rpsl_pk": "TEST-MNT",
                }
            ],
        )
        assert mock_dh.queries == [
            RPSLDatabaseJournalStatisticsQuery(),
            DatabaseStatusQuery().source("TEST"),
            RPSLDatabaseJournalQuery()
            .sources(["TEST"])
            .serial_global_range(status.last_snapshot_global_serial + 1),
        ]
        newest_unf = self._load_unf(nrtm_path)
        assert newest_unf["version"] == 3
        assert newest_unf["snapshot"] == unf["snapshot"]
        assert newest_unf["session_id"] == unf["session_id"]
        assert newest_unf["timestamp"] != unf["timestamp"]
        assert newest_unf["deltas"][0] == new_unf["deltas"][0]

        delta2_filename = newest_unf["deltas"][1]["url"].split("/")[-1]
        with gzip.open(nrtm_path / delta2_filename, "rb") as delta_file:
            delta = list(jsonseq_decode(delta_file))
        assert len(delta) == 2
        assert delta[0]["nrtm_version"] == 4
        assert delta[0]["source"] == "TEST"
        assert delta[0]["type"] == "delta"
        assert delta[0]["session_id"] == unf["session_id"]
        assert delta[0]["version"] == newest_unf["version"]
        assert delta[1]["primary_key"] == "TEST-MNT"
        assert delta[1]["object_class"] == "mntner"
        assert delta[1]["action"] == "delete"

        # Final run, no new journal entries, but one delta expired
        # Most hashes checked at the end, but this one is about to be deleted
        check_file_hash_sha256(nrtm_path / delta1_filename, new_unf["deltas"][0]["hash"])

        status = mock_dh.other_calls[0][1]["status"]
        status.previous_deltas[0]["timestamp"] -= (NRTM4_SERVER_DELTA_EXPIRY_TIME * 2).total_seconds()
        self._run_writer(mock_dh, [self._status_to_dict(status)])
        assert mock_dh.queries == [
            RPSLDatabaseJournalStatisticsQuery(),
            DatabaseStatusQuery().source("TEST"),
            RPSLDatabaseJournalQuery()
            .sources(["TEST"])
            .serial_global_range(status.last_snapshot_global_serial + 1),
        ]
        expiry_unf = self._load_unf(nrtm_path)
        assert expiry_unf["version"] == newest_unf["version"]
        assert expiry_unf["snapshot"] == newest_unf["snapshot"]
        assert expiry_unf["session_id"] == newest_unf["session_id"]
        assert expiry_unf["timestamp"] != newest_unf["timestamp"]
        assert len(expiry_unf["deltas"]) == 1
        assert expiry_unf["deltas"][0] == newest_unf["deltas"][1]

        assert not (nrtm_path / delta1_filename).exists()
        # Also used to make sure files were not deleted
        check_file_hash_sha256(nrtm_path / snapshot_filename, unf["snapshot"]["hash"])
        check_file_hash_sha256(nrtm_path / delta2_filename, newest_unf["deltas"][1]["hash"])

        (nrtm_path / delta2_filename).unlink()
        self._run_writer(mock_dh, [self._status_to_dict(status)])
        integrity_fail_reset_unf = self._load_unf(nrtm_path)
        assert integrity_fail_reset_unf["version"] == 1
        assert integrity_fail_reset_unf["session_id"] != newest_unf["session_id"]

        self._run_writer(mock_dh, [self._status_to_dict(status, force_reload=True)])
        assert [type(q) for q in mock_dh.queries] == [RPSLDatabaseJournalStatisticsQuery, DatabaseStatusQuery]
        assert not mock_dh.other_calls

    def _load_unf(self, nrtm_path):
        with open(nrtm_path / UPDATE_NOTIFICATION_FILENAME, "rb") as f:
            unf_content = f.read()
        unf_payload = jws_deserialize(unf_content, MOCK_UNF_PRIVATE_KEY)
        unf = json.loads(unf_payload.payload)
        assert unf["nrtm_version"] == 4
        assert unf["source"] == "TEST"
        assert unf["type"] == "notification"
        return unf

    def _status_to_dict(self, status: NRTM4ServerDatabaseStatus, force_reload=False):
        result = {"nrtm4_server_" + key: value for key, value in dataclasses.asdict(status).items()}
        result["force_reload"] = force_reload
        return result

    def _run_writer(self, mock_dh, status, journal=None):
        if journal is None:
            journal = []
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = status
        mock_dh.query_responses[RPSLDatabaseQuery] = iter(
            [
                {
                    "object_text": SAMPLE_MNTNER,
                    "object_class": "mntner",
                    "rpsl_pk": "TEST-MNT",
                }
            ]
        )
        mock_dh.query_responses[RPSLDatabaseJournalQuery] = iter(journal)
        NRTM4ServerWriter("TEST", mock_dh).run()
