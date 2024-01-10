import copy
import uuid

import pydantic
import pytest

from irrd.mirroring.nrtm4.nrtm4_types import (
    NRTM4DeltaHeader,
    NRTM4SnapshotHeader,
    NRTM4UpdateNotificationFile,
)
from irrd.mirroring.nrtm4.tests import MOCK_UNF_PUBLIC_KEY_OTHER
from irrd.utils.misc import format_pydantic_errors

SESSION_ID = uuid.uuid4()


class TestNRTM4SnapshotHeader:
    valid_data = {
        "nrtm_version": 4,
        "source": "TEST",
        "session_id": SESSION_ID,
        "version": 5,
        "type": "snapshot",
    }
    valid_context = {
        "expected_values": {
            "source": "TEST",
            "session_id": SESSION_ID,
            "version": 5,
        }
    }

    def test_valid(self):
        model = NRTM4SnapshotHeader.model_validate(
            self.valid_data,
            context=self.valid_context,
        )
        assert model.origin_identifier == f"{SESSION_ID}/S5"

    def test_session_mismatch(self):
        with pytest.raises(pydantic.ValidationError) as ve:
            NRTM4SnapshotHeader.model_validate(
                self.valid_data,
                context={
                    "expected_values": {
                        "source": "TEST",
                        "session_id": uuid.uuid4(),
                        "version": 5,
                    }
                },
            )
        assert "Mismatch in session_id field" in str(ve)

    def test_type_mismatch(self):
        with pytest.raises(pydantic.ValidationError) as ve:
            NRTM4SnapshotHeader.model_validate(
                {
                    "nrtm_version": 4,
                    "source": "TEST",
                    "session_id": SESSION_ID,
                    "version": 5,
                    "type": "delta",
                },
                context=self.valid_context,
            )
        assert "Input should be 'snapshot'" in str(ve)


class TestNRTM4DeltaHeader:
    valid_data = {
        "nrtm_version": 4,
        "source": "TEST",
        "session_id": SESSION_ID,
        "version": 5,
        "type": "delta",
    }
    valid_context = {
        "expected_values": {
            "source": "TEST",
            "session_id": SESSION_ID,
            "version": 5,
        }
    }

    def test_valid(self):
        model = NRTM4DeltaHeader.model_validate(self.valid_data, context=self.valid_context)
        assert model.origin_identifier == f"{SESSION_ID}/D5"

    def test_session_mismatch(self):
        with pytest.raises(pydantic.ValidationError) as ve:
            NRTM4DeltaHeader.model_validate(
                self.valid_data,
                context={
                    "expected_values": {
                        "source": "TEST",
                        "session_id": uuid.uuid4(),
                        "version": 5,
                    }
                },
            )
        assert "Mismatch in session_id field" in str(ve)

    def test_type_mismatch(self):
        with pytest.raises(pydantic.ValidationError) as ve:
            NRTM4DeltaHeader.model_validate(
                {
                    "nrtm_version": 4,
                    "source": "TEST",
                    "session_id": SESSION_ID,
                    "version": 5,
                    "type": "snapshot",
                },
                context=self.valid_context,
            )
        assert "Input should be 'delta'" in str(ve)


class TestNRTM4UpdateNotificationFile:
    valid_data = {
        "nrtm_version": 4,
        "source": "TEST",
        "session_id": SESSION_ID,
        "version": 4,
        "type": "notification",
        "timestamp": "2022-03-15 00:00:00+00:00",
        "snapshot": {"version": 3, "url": "https://example.com/snapshot.2.json", "hash": "hash"},
        "deltas": [
            {"version": 2, "url": "https://example.com/delta.2.json", "hash": "hash"},
            {"version": 3, "url": "https://example.com/delta.3.json", "hash": "hash"},
            {"version": 4, "url": "https://example.com/delta.4.json", "hash": "hash"},
        ],
    }
    valid_context = {
        "expected_values": {
            "source": "TEST",
        },
        "update_notification_file_scheme": "https",
    }

    @pytest.mark.freeze_time("2022-03-14 12:34:56")
    def test_valid(self):
        model = NRTM4UpdateNotificationFile.model_validate(
            self.valid_data,
            context=self.valid_context,
        )
        assert model.min_delta_version == 2
        assert model.max_delta_version == 4

        data = copy.deepcopy(self.valid_data)
        data["deltas"] = []
        data["version"] = 3
        data["next_signing_key"] = MOCK_UNF_PUBLIC_KEY_OTHER
        model = NRTM4UpdateNotificationFile.model_validate(
            data,
            context=self.valid_context,
        )
        assert model.min_delta_version is None
        assert model.max_delta_version is None

    @pytest.mark.freeze_time("2022-03-14 12:34:56")
    def test_invalid_missing_snapshot(self):
        data = copy.deepcopy(self.valid_data)
        del data["snapshot"]
        with pytest.raises(pydantic.ValidationError) as ve:
            NRTM4UpdateNotificationFile.model_validate(
                data,
                context=self.valid_context,
            )
        assert "snapshot: Field required" in format_pydantic_errors(ve.value)

    @pytest.mark.freeze_time("2022-03-14 12:34:56")
    def test_invalid_url_scheme(self):
        data = copy.deepcopy(self.valid_data)
        data["deltas"][1]["url"] = "file:///filename"
        with pytest.raises(pydantic.ValidationError) as ve:
            NRTM4UpdateNotificationFile.model_validate(
                data,
                context=self.valid_context,
            )
        assert "Invalid scheme" in str(ve)

    @pytest.mark.freeze_time("2022-03-14 12:34:56")
    def test_invalid_unf_older_than_snapshot(self):
        data = copy.deepcopy(self.valid_data)
        data["snapshot"]["version"] = 10
        with pytest.raises(pydantic.ValidationError) as ve:
            NRTM4UpdateNotificationFile.model_validate(
                data,
                context=self.valid_context,
            )
        assert "version 4 should have " in str(ve)

    @pytest.mark.freeze_time("2022-03-14 12:34:56")
    def test_invalid_unf_older_than_deltas(self):
        data = copy.deepcopy(self.valid_data)
        data["version"] = 1
        data["snapshot"]["version"] = 1
        with pytest.raises(pydantic.ValidationError) as ve:
            NRTM4UpdateNotificationFile.model_validate(
                data,
                context=self.valid_context,
            )
        assert "version 1 should have " in str(ve)

    @pytest.mark.freeze_time("2022-03-14 12:34:56")
    def test_invalid_deltas_not_contiguous(self):
        data = copy.deepcopy(self.valid_data)
        data["version"] = 5
        data["deltas"][2]["version"] = 5
        with pytest.raises(pydantic.ValidationError) as ve:
            NRTM4UpdateNotificationFile.model_validate(
                data,
                context=self.valid_context,
            )
        assert "do not have contiguous serials" in str(format_pydantic_errors(ve.value))

    @pytest.mark.freeze_time("2022-03-14 12:34:56")
    def test_invalid_timestamp_too_old(self):
        data = copy.deepcopy(self.valid_data)
        data["timestamp"] = "2022-05-15 00:00:00+00:00"
        with pytest.raises(pydantic.ValidationError) as ve:
            NRTM4UpdateNotificationFile.model_validate(
                data,
                context=self.valid_context,
            )
        assert "older than 24 hours" in str(format_pydantic_errors(ve.value))

    @pytest.mark.freeze_time("2022-03-14 12:34:56")
    def test_invalid_next_signing_key(self):
        data = copy.deepcopy(self.valid_data)
        data["next_signing_key"] = "invalid"
        with pytest.raises(pydantic.ValidationError) as ve:
            NRTM4UpdateNotificationFile.model_validate(
                data,
                context=self.valid_context,
            )
        assert "invalid next_signing_key" in str(format_pydantic_errors(ve.value))
