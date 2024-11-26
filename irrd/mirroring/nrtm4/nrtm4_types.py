import datetime
from functools import cached_property
from typing import Any, Literal, Optional
from urllib.parse import urlparse, urlunparse
from uuid import UUID

import pydantic
from joserfc.rfc7518.ec_key import ECKey
from pytz import UTC
from typing_extensions import Self

from irrd.mirroring.nrtm4 import UPDATE_NOTIFICATION_FILENAME


def get_from_pydantic_context(info: pydantic.ValidationInfo, key: str) -> Optional[Any]:
    """
    This is a little helper to get a key from the pydantic context,
    as it's a bit convoluted and needs some type guarding.
    """
    context = getattr(info, "context", {})
    return context.get(key, None) if context else None


class ExpectedValuesMixin:
    """
    Mixin to validate a dict of "expected_values" in the pydantic context,
    whose values must match to attributes. Used for e.g. session ID matching.
    """

    @pydantic.model_validator(mode="after")  # type: ignore
    def validate_expected_values(self, info: pydantic.ValidationInfo):
        expected_values = get_from_pydantic_context(info, "expected_values")
        if not expected_values:
            return self
        for key, expected_value in expected_values.items():
            value = getattr(self, key)
            if value != expected_value:
                raise ValueError(f"Mismatch in {key} field: expected {expected_value}, found {value}")
        return self


class NRTM4Common(ExpectedValuesMixin, pydantic.main.BaseModel):
    """Common parts of all NRTM root objects, i.e. snapshot/delta header and UNF."""

    nrtm_version: Literal[4]
    source: str
    session_id: UUID
    version: pydantic.PositiveInt


class NRTM4SnapshotHeader(NRTM4Common):
    type: Literal["snapshot"]

    @pydantic.computed_field  # type: ignore[misc]
    @cached_property
    def origin_identifier(self) -> str:
        return f"{self.session_id}/S{self.version}"


class NRTM4DeltaHeader(NRTM4Common):
    type: Literal["delta"]

    @pydantic.computed_field  # type: ignore[misc]
    @cached_property
    def origin_identifier(self) -> str:
        return f"{self.session_id}/D{self.version}"


class NRTM4FileReference(pydantic.main.BaseModel):
    """
    References to specific files (from the UNF).
    Must match scheme with expected, as we allow file and https,
    but not mixing them in one NRTMv4 repo.
    """

    version: pydantic.PositiveInt
    url: str  # Convert to Path when RIPE db is fixed
    hash: str

    def full_url(self, unf_url: str) -> str:
        unf_path = urlparse(unf_url)
        return urlunparse(
            (
                unf_path.scheme,
                unf_path.hostname,
                unf_path.path.replace(UPDATE_NOTIFICATION_FILENAME, str(self.url)),
                "",
                "",
                "",
            )
        )


class NRTM4UpdateNotificationFile(NRTM4Common):
    """
    UNF parsing model. This has a few derived properties,
    and many consistency rules from the standard.
    """

    timestamp: datetime.datetime
    type: Literal["notification"]
    snapshot: NRTM4FileReference
    deltas: list[NRTM4FileReference]
    next_signing_key: Optional[str] = None

    @pydantic.computed_field  # type: ignore[misc]
    @property
    def min_delta_version(self) -> Optional[int]:
        return self.deltas[0].version if self.deltas else None

    @pydantic.computed_field  # type: ignore[misc]
    @property
    def max_delta_version(self) -> Optional[int]:
        return self.deltas[-1].version if self.deltas else None

    @pydantic.model_validator(mode="after")
    def check_version_consistency(self) -> Self:
        expected_unf_version = self.snapshot.version
        if self.max_delta_version:
            expected_unf_version = max(self.snapshot.version, self.max_delta_version)
        if self.version != expected_unf_version:
            raise ValueError(
                f"Update Notification File version {self.version} should have version {expected_unf_version}"
                " based on Snapshot and Delta versions"
            )
        if self.deltas:
            assert self.min_delta_version
            assert self.max_delta_version

            expected_versions = range(self.min_delta_version, self.max_delta_version + 1)
            if [d.version for d in self.deltas] != list(expected_versions):
                raise ValueError("Deltas in Update Notification File do not have contiguous serials.")
        return self

    @pydantic.field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, timestamp: datetime.datetime):
        if timestamp - datetime.datetime.now(tz=UTC) > datetime.timedelta(hours=24):
            raise ValueError(
                f"Update Notification File is older than 24 hours, timestamp {timestamp.isoformat()}"
            )
        return timestamp

    @pydantic.field_validator("next_signing_key")
    @classmethod
    def validate_next_signing_key(cls, next_signing_key: Optional[str]):
        if next_signing_key:
            try:
                ECKey.import_key(next_signing_key)
            except ValueError as ve:
                raise ValueError(
                    f"Update Notification File has invalid next_signing_key {next_signing_key}: {ve}"
                )
        return next_signing_key
