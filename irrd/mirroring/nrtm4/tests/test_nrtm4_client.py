import json
from tempfile import NamedTemporaryFile
from uuid import UUID, uuid4

import pytest
from joserfc import jws

from irrd.mirroring.nrtm4.jsonseq import jsonseq_encode
from irrd.mirroring.nrtm4.nrtm4_client import NRTM4Client, NRTM4ClientError
from irrd.mirroring.nrtm4.tests import (
    MOCK_UNF_PRIVATE_KEY,
    MOCK_UNF_PUBLIC_KEY,
    MOCK_UNF_PUBLIC_KEY_OTHER,
)
from irrd.storage.models import NRTM4ClientDatabaseStatus
from irrd.storage.queries import DatabaseStatusQuery
from irrd.utils.test_utils import MockDatabaseHandler

MOCK_SESSION_ID = "ca128382-78d9-41d1-8927-1ecef15275be"

MOCK_SNAPSHOT_URL = "https://example.com/snapshot.2.json"
MOCK_DELTA3_URL = "https://example.com/delta.3.json"
MOCK_DELTA4_URL = "https://example.com/delta.4.json"
MOCK_UNF_URL = "https://example.com/update-notification-file.json"
MOCK_UNF_SIG_URL = "https://example.com/update-notification-file-signature-hash.json"

MOCK_UNF = {
    "nrtm_version": 4,
    "timestamp": "2022-01-01T15:00:00Z",
    "type": "notification",
    "next_signing_key": MOCK_UNF_PUBLIC_KEY_OTHER,
    "source": "TEST",
    "session_id": MOCK_SESSION_ID,
    "version": 4,
    "snapshot": {
        "version": 3,
        "url": MOCK_SNAPSHOT_URL,
        "hash": MOCK_SNAPSHOT_URL,
    },
    "deltas": [
        {
            "version": 3,
            "url": MOCK_DELTA3_URL,
            "hash": MOCK_DELTA3_URL,
        },
        {
            "version": 4,
            "url": MOCK_DELTA4_URL,
            "hash": MOCK_DELTA4_URL,
        },
    ],
}

MOCK_SNAPSHOT = [
    {"nrtm_version": 4, "type": "snapshot", "source": "TEST", "session_id": MOCK_SESSION_ID, "version": 3},
    {"object": "route: 192.0.2.0/24\norigin: AS65530\nsource: TEST"},
]

MOCK_DELTA3 = [
    {"nrtm_version": 4, "type": "delta", "source": "TEST", "session_id": MOCK_SESSION_ID, "version": 3},
    {
        "action": "add_modify",
        "object": "route: 192.0.2.0/24\norigin: AS65530\nsource: TEST",
    },
]

MOCK_DELTA4 = [
    {
        "nrtm_version": 4,
        "type": "delta",
        "source": "TEST",
        "session_id": MOCK_SESSION_ID,
        "version": 4,
    },
    {"action": "delete", "object_class": "route", "primary_key": "192.0.2.0/24AS65530"},
]

MOCK_RESPONSES = {
    MOCK_UNF_URL: MOCK_UNF,
    MOCK_SNAPSHOT_URL: MOCK_SNAPSHOT,
    MOCK_DELTA3_URL: MOCK_DELTA3,
    MOCK_DELTA4_URL: MOCK_DELTA4,
}


def _mock_retrieve_file(tmp_path, mock_responses):
    def mock_retrieve_file(url, expected_hash=None, return_contents=True):
        url = str(url)
        mock_unf_content = json.dumps(mock_responses[MOCK_UNF_URL])
        mock_unf_serialized = jws.serialize_compact({"alg": "ES256"}, mock_unf_content, MOCK_UNF_PRIVATE_KEY)
        if url == MOCK_UNF_URL and return_contents:
            return mock_unf_serialized, False
        elif not return_contents:
            assert url == expected_hash
            destination = NamedTemporaryFile(dir=tmp_path, delete=False)
            jsonseq_encode(mock_responses[url], destination)
            return destination.name, True
        else:
            raise NotImplementedError("mock_retrieve_file does not support these params")

    return mock_retrieve_file


@pytest.fixture
def prepare_nrtm4_test(config_override, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "irrd.mirroring.nrtm4.nrtm4_client.retrieve_file", _mock_retrieve_file(tmp_path, MOCK_RESPONSES)
    )

    config_override(
        {
            "sources": {
                "TEST": {
                    "nrtm4_client_notification_file_url": MOCK_UNF_URL,
                    "nrtm4_client_initial_public_key": MOCK_UNF_PUBLIC_KEY,
                },
                "DIFFERENT-SOURCE": {
                    "nrtm4_client_notification_file_url": MOCK_UNF_URL,
                    "nrtm4_client_initial_public_key": MOCK_UNF_PUBLIC_KEY,
                },
            },
            "rpki": {"roa_source": None},
        }
    )


class TestNRTM4Client:
    def test_valid_from_snapshot(self, prepare_nrtm4_test, caplog):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter(
            [
                {
                    "force_reload": False,
                    "nrtm4_client_session_id": None,
                    "nrtm4_client_version": None,
                    "nrtm4_client_current_key": None,
                    "nrtm4_client_next_key": None,
                }
            ]
        )
        NRTM4Client("TEST", mock_dh).run_client()
        self._assert_import_queries(mock_dh, expect_reload=True)
        assert "No previous known session ID or version, reloading from snapshot" in caplog.text
        assert "import of snapshot at version 3" in caplog.text
        assert "Updating from deltas, starting from version 4" in caplog.text

    def test_valid_from_delta(self, prepare_nrtm4_test, caplog):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter(
            [
                {
                    "force_reload": False,
                    "nrtm4_client_session_id": UUID(MOCK_SESSION_ID),
                    "nrtm4_client_version": 2,
                    "nrtm4_client_current_key": None,
                    "nrtm4_client_next_key": None,
                }
            ]
        )
        NRTM4Client("TEST", mock_dh).run_client()
        self._assert_import_queries(mock_dh, expect_reload=False)
        assert "Updating from deltas, starting from version 3" in caplog.text

    def test_invalid_signature(self, prepare_nrtm4_test, monkeypatch, tmp_path, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "nrtm4_client_notification_file_url": MOCK_UNF_URL,
                        "nrtm4_client_initial_public_key": MOCK_UNF_PUBLIC_KEY_OTHER,
                    },
                },
                "rpki": {"roa_source": None},
            }
        )
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter([])
        with pytest.raises(NRTM4ClientError):
            NRTM4Client("TEST", mock_dh).run_client()

    def test_invalid_empty_delta(self, prepare_nrtm4_test, tmp_path, monkeypatch):
        mock_responses = {
            MOCK_UNF_URL: MOCK_UNF,
            MOCK_SNAPSHOT_URL: MOCK_SNAPSHOT,
            # Shorten delta 3 to header only
            MOCK_DELTA3_URL: MOCK_DELTA3[:1],
            MOCK_DELTA4_URL: MOCK_DELTA4,
        }
        monkeypatch.setattr(
            "irrd.mirroring.nrtm4.nrtm4_client.retrieve_file", _mock_retrieve_file(tmp_path, mock_responses)
        )
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter(
            [
                {
                    "force_reload": False,
                    "nrtm4_client_session_id": UUID(MOCK_SESSION_ID),
                    "nrtm4_client_version": 2,
                    "nrtm4_client_current_key": None,
                    "nrtm4_client_next_key": None,
                }
            ]
        )

        with pytest.raises(ValueError) as ve:
            NRTM4Client("TEST", mock_dh).run_client()
        assert "did not contain any entries" in str(ve)

    def test_invalid_delta_key_error(self, prepare_nrtm4_test, tmp_path, monkeypatch):
        mock_responses = {
            MOCK_UNF_URL: MOCK_UNF,
            MOCK_SNAPSHOT_URL: MOCK_SNAPSHOT,
            # Missing keys in delta 3
            MOCK_DELTA3_URL: [MOCK_DELTA3[0], {}],
            MOCK_DELTA4_URL: MOCK_DELTA4,
        }
        monkeypatch.setattr(
            "irrd.mirroring.nrtm4.nrtm4_client.retrieve_file", _mock_retrieve_file(tmp_path, mock_responses)
        )
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter(
            [
                {
                    "force_reload": False,
                    "nrtm4_client_session_id": UUID(MOCK_SESSION_ID),
                    "nrtm4_client_version": 2,
                    "nrtm4_client_current_key": None,
                    "nrtm4_client_next_key": None,
                }
            ]
        )

        with pytest.raises(ValueError) as ve:
            NRTM4Client("TEST", mock_dh).run_client()
        assert "contained invalid entry" in str(ve)

    def test_invalid_unf_version_too_low(self, prepare_nrtm4_test):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter(
            [
                {
                    "force_reload": False,
                    "nrtm4_client_session_id": UUID(MOCK_SESSION_ID),
                    "nrtm4_client_version": 6,
                    "nrtm4_client_current_key": None,
                    "nrtm4_client_next_key": None,
                }
            ]
        )

        with pytest.raises(ValueError) as ve:
            NRTM4Client("TEST", mock_dh).run_client()
        assert "but version 4 is older than local version 6" in str(ve)

    def test_session_id_mismatch(self, prepare_nrtm4_test, caplog):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter(
            [
                {
                    "force_reload": False,
                    "nrtm4_client_session_id": uuid4(),
                    "nrtm4_client_version": 2,
                    "nrtm4_client_current_key": None,
                    "nrtm4_client_next_key": None,
                }
            ]
        )
        NRTM4Client("TEST", mock_dh).run_client()
        self._assert_import_queries(mock_dh, expect_reload=True)
        assert "Session ID has changed" in caplog.text
        assert "import of snapshot at version 3" in caplog.text
        assert "Updating from deltas, starting from version 4" in caplog.text

    def test_delta_gap(self, prepare_nrtm4_test, caplog):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter(
            [
                {
                    "force_reload": False,
                    "nrtm4_client_session_id": UUID(MOCK_SESSION_ID),
                    "nrtm4_client_version": 1,
                    "nrtm4_client_current_key": None,
                    "nrtm4_client_next_key": None,
                }
            ]
        )
        NRTM4Client("TEST", mock_dh).run_client()
        self._assert_import_queries(mock_dh, expect_reload=True)
        assert "Deltas from current version 1 not available on server, reloading from snapshot" in caplog.text
        assert "import of snapshot at version 3" in caplog.text
        assert "Updating from deltas, starting from version 4" in caplog.text

    def test_force_reload(self, prepare_nrtm4_test, caplog):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter(
            [
                {
                    "force_reload": True,
                    "nrtm4_client_session_id": UUID(MOCK_SESSION_ID),
                    "nrtm4_client_version": 2,
                    "nrtm4_client_current_key": None,
                    "nrtm4_client_next_key": None,
                }
            ]
        )
        NRTM4Client("TEST", mock_dh).run_client()
        self._assert_import_queries(mock_dh, expect_reload=True)
        assert "Forced reload flag set, reloading from snapshot" in caplog.text
        assert "import of snapshot at version 3" in caplog.text
        assert "Updating from deltas, starting from version 4" in caplog.text

    def test_no_status(self, prepare_nrtm4_test, caplog):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter([])
        NRTM4Client("TEST", mock_dh).run_client()
        self._assert_import_queries(mock_dh, expect_reload=True)
        assert "No previous known session ID or version" in caplog.text
        assert "import of snapshot at version 3" in caplog.text
        assert "Updating from deltas, starting from version 4" in caplog.text

    def test_valid_up_to_date(self, prepare_nrtm4_test, caplog):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter(
            [
                {
                    "force_reload": False,
                    "nrtm4_client_session_id": UUID(MOCK_SESSION_ID),
                    "nrtm4_client_version": 4,
                    "nrtm4_client_current_key": None,
                    "nrtm4_client_next_key": None,
                }
            ]
        )
        NRTM4Client("TEST", mock_dh).run_client()
        assert mock_dh.other_calls == [
            (
                "record_nrtm4_client_status",
                {
                    "source": "TEST",
                    "status": NRTM4ClientDatabaseStatus(
                        session_id=UUID(MOCK_SESSION_ID),
                        version=4,
                        current_key=MOCK_UNF_PUBLIC_KEY,
                        next_key=MOCK_UNF_PUBLIC_KEY_OTHER,
                    ),
                },
            ),
        ]
        assert "Up to date at version 4" in caplog.text

    def test_source_mismatch(self, prepare_nrtm4_test):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter([])
        with pytest.raises(NRTM4ClientError):
            NRTM4Client("DIFFERENT-SOURCE", mock_dh).run_client()

        MOCK_SNAPSHOT[0]["source"] = "DIFFERENT-SOURCE"
        with pytest.raises(NRTM4ClientError) as err:
            NRTM4Client("TEST", mock_dh).run_client()
        assert "Mismatch in source field" in str(err)
        MOCK_SNAPSHOT[0]["source"] = "TEST"

    def test_invalid_signature_from_config(self, prepare_nrtm4_test, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "nrtm4_client_notification_file_url": MOCK_UNF_URL,
                        # We are not in key rotation, so this is invalid
                        "nrtm4_client_initial_public_key": MOCK_UNF_PUBLIC_KEY_OTHER,
                    },
                },
            }
        )

        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter([])
        with pytest.raises(NRTM4ClientError) as exc:
            NRTM4Client("TEST", mock_dh).run_client()
        assert "any known keys" in str(exc)

    def test_invalid_current_db_key_with_valid_config_key(self, prepare_nrtm4_test, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "nrtm4_client_notification_file_url": MOCK_UNF_URL,
                        # This key matches but must be ignored
                        "nrtm4_client_initial_public_key": MOCK_UNF_PUBLIC_KEY,
                    },
                },
            }
        )

        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter(
            [
                {
                    "force_reload": False,
                    "nrtm4_client_session_id": UUID(MOCK_SESSION_ID),
                    "nrtm4_client_version": 4,
                    # Does not match, but must be used
                    "nrtm4_client_current_key": MOCK_UNF_PUBLIC_KEY_OTHER,
                    "nrtm4_client_next_key": MOCK_UNF_PUBLIC_KEY_OTHER,
                }
            ]
        )
        with pytest.raises(NRTM4ClientError) as exc:
            NRTM4Client("TEST", mock_dh).run_client()
        assert "is valid for" in str(exc)

    def test_uses_current_db_key(self, prepare_nrtm4_test, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "nrtm4_client_notification_file_url": MOCK_UNF_URL,
                        # Intentionally mismatching key that should be ignored
                        "nrtm4_client_initial_public_key": MOCK_UNF_PUBLIC_KEY_OTHER,
                    },
                },
            }
        )

        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter(
            [
                {
                    "force_reload": False,
                    "nrtm4_client_session_id": UUID(MOCK_SESSION_ID),
                    "nrtm4_client_version": 4,
                    "nrtm4_client_current_key": MOCK_UNF_PUBLIC_KEY,
                    "nrtm4_client_next_key": None,
                }
            ]
        )
        NRTM4Client("TEST", mock_dh).run_client()

    def test_key_rotation(self, prepare_nrtm4_test, config_override, caplog):
        config_override(
            {
                "sources": {
                    "TEST": {
                        "nrtm4_client_notification_file_url": MOCK_UNF_URL,
                        # This key matches but must be ignored
                        "nrtm4_client_initial_public_key": MOCK_UNF_PUBLIC_KEY,
                    },
                },
            }
        )

        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        mock_dh.query_responses[DatabaseStatusQuery] = iter(
            [
                {
                    "force_reload": False,
                    "nrtm4_client_session_id": UUID(MOCK_SESSION_ID),
                    "nrtm4_client_version": 4,
                    # Does not match, but must be used
                    "nrtm4_client_current_key": MOCK_UNF_PUBLIC_KEY_OTHER,
                    "nrtm4_client_next_key": MOCK_UNF_PUBLIC_KEY,
                }
            ]
        )
        NRTM4Client("TEST", mock_dh).run_client()
        assert mock_dh.other_calls == [
            (
                "record_nrtm4_client_status",
                {
                    "source": "TEST",
                    "status": NRTM4ClientDatabaseStatus(
                        session_id=UUID(MOCK_SESSION_ID),
                        version=4,
                        current_key=MOCK_UNF_PUBLIC_KEY,
                        next_key=MOCK_UNF_PUBLIC_KEY_OTHER,
                    ),
                },
            ),
        ]
        assert "key rotated" in caplog.text

    def _assert_import_queries(self, mock_dh, expect_reload=True):
        assert mock_dh.queries == [DatabaseStatusQuery().source("TEST")]
        expected = (
            (
                [
                    (
                        "delete_all_rpsl_objects_with_journal",
                        {"source": "TEST", "journal_guaranteed_empty": False},
                    ),
                    ("disable_journaling", {}),
                ]
                if expect_reload
                else []
            )
            + [
                (
                    "upsert_rpsl_object",
                    {
                        "rpsl_object": "route/192.0.2.0/24AS65530/TEST",
                        "origin": "mirror",
                        "rpsl_guaranteed_no_existing": False,
                        "source_serial": None,
                        "forced_created_value": None,
                    },
                ),
            ]
            + (
                [
                    ("enable_journaling", {}),
                ]
                if expect_reload
                else []
            )
            + [
                (
                    "delete_rpsl_object",
                    {
                        "origin": "mirror",
                        "rpsl_object": None,
                        "source": "TEST",
                        "rpsl_pk": "192.0.2.0/24AS65530",
                        "object_class": "route",
                        "source_serial": None,
                        "protect_rpsl_name": False,
                    },
                ),
                (
                    "record_nrtm4_client_status",
                    {
                        "source": "TEST",
                        "status": NRTM4ClientDatabaseStatus(
                            session_id=UUID(MOCK_SESSION_ID),
                            version=4,
                            current_key=MOCK_UNF_PUBLIC_KEY,
                            next_key=MOCK_UNF_PUBLIC_KEY_OTHER,
                        ),
                    },
                ),
            ]
        )

        assert mock_dh.other_calls == expected
