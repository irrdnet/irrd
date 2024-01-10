import hashlib
import logging
import os
from base64 import b64decode
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import pydantic
from cryptography.exceptions import InvalidSignature

from irrd.conf import get_setting
from irrd.mirroring.nrtm4.jsonseq import jsonseq_decode
from irrd.mirroring.nrtm4.nrtm4_types import (
    NRTM4DeltaHeader,
    NRTM4SnapshotHeader,
    NRTM4UpdateNotificationFile,
)
from irrd.mirroring.nrtm_operation import NRTMOperation
from irrd.mirroring.parsers import (
    MirrorFileImportParserBase,
    get_object_class_filter_for_source,
)
from irrd.mirroring.retrieval import retrieve_file
from irrd.rpki.validators import BulkRouteROAValidator
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import (
    DatabaseOperation,
    JournalEntryOrigin,
    NRTM4ClientDatabaseStatus,
)
from irrd.storage.queries import DatabaseStatusQuery
from irrd.utils.crypto import ed25519_public_key_from_str
from irrd.utils.misc import format_pydantic_errors

logger = logging.getLogger(__name__)


NRTM4_OPERATION_MAPPING = {
    "add_modify": DatabaseOperation.add_or_update,
    "delete": DatabaseOperation.delete,
}


class NRTM4ClientError(ValueError):
    """
    Errors in the state of the NRTMv4 client. These are either
    configuration issues or issues with the remote NRTMv4 data.
    """

    @staticmethod
    def from_pydantic_error(err: pydantic.ValidationError):
        return NRTM4ClientError("; ".join(format_pydantic_errors(err)))


class NRTM4Client:
    def __init__(self, source: str, database_handler: DatabaseHandler):
        self.source = source
        self.database_handler = database_handler
        self.rpki_aware = bool(get_setting("rpki.roa_source"))
        self.force_reload, self.last_status = self._current_db_status()

    def run_client(self) -> bool:
        """
        Run the client based on the parameters provided to init().
        Returns True to indicate that a full reload has happened,
        and the journal is no longer complete, False otherwise.
        The very small wrapper here is to catch all pydantic
        errors and convert them appropriately.
        """
        try:
            return self._run_client()
        except pydantic.ValidationError as ve:
            raise NRTM4ClientError.from_pydantic_error(ve)
        except ValueError as ve:
            raise NRTM4ClientError((str(ve)))

    def _run_client(self) -> bool:
        has_loaded_snapshot = False

        unf, used_key = self._retrieve_unf()
        next_delta_version = self._find_next_version(unf)
        if next_delta_version is None:
            self._load_snapshot(unf)
            next_delta_version = self._find_next_version(unf, unf.snapshot.version)
            has_loaded_snapshot = True

        if unf.max_delta_version and next_delta_version <= unf.max_delta_version:
            logger.info(f"{self.source}: Updating from deltas, starting from version {next_delta_version}")
            self._load_deltas(unf, next_delta_version)
        else:
            logger.info(f"{self.source}: Up to date at version {unf.version}")

        if self.last_status.current_key and self.last_status.current_key != used_key:
            logger.info(
                f"{self.source}: Update Notification File signing key rotated from"
                f" {self.last_status.current_key} to {used_key}"
            )

        self.database_handler.record_nrtm4_client_status(
            self.source,
            NRTM4ClientDatabaseStatus(
                session_id=unf.session_id,
                version=unf.version,
                current_key=used_key,
                next_key=unf.next_signing_key,
            ),
        )
        return has_loaded_snapshot

    def _retrieve_unf(self) -> Tuple[NRTM4UpdateNotificationFile, str]:
        """
        Retrieve, verify and parse the Update Notification File.
        Returns the UNF object and the used key in base64 string.
        """
        notification_file_url = get_setting(f"sources.{self.source}.nrtm4_client_notification_file_url")
        if not notification_file_url:  # pragma: no cover
            raise RuntimeError("NRTM4 client called for a source without a Update Notification File URL")

        unf_content, _ = retrieve_file(notification_file_url, return_contents=True)
        unf_hash = hashlib.sha256(unf_content.encode("ascii")).hexdigest()
        sig_url = notification_file_url.replace(
            "update-notification-file.json", f"update-notification-file-signature-{unf_hash}.sig"
        )
        legacy_sig_url = notification_file_url + ".sig"
        if "nrtm.db.ripe.net" in notification_file_url:  # pragma: no cover
            logger.warning(
                f"Downloading signature from legacy url {legacy_sig_url} instead of expected {sig_url}"
            )
            signature, _ = retrieve_file(legacy_sig_url, return_contents=True)
        else:
            signature, _ = retrieve_file(sig_url, return_contents=True)

        used_key = self._validate_unf_signature(unf_content, signature)

        unf = NRTM4UpdateNotificationFile.model_validate_json(
            unf_content,
            context={
                "update_notification_file_scheme": urlparse(notification_file_url).scheme,
                "expected_values": {
                    "source": self.source,
                },
            },
        )
        return unf, used_key

    def _validate_unf_signature(self, unf_content: str, signature_b64: str) -> str:
        """
        Verify the Update Notification File signature,
        given the content (before JSON parsing) and a base64 signature.
        Returns the used key in base64 string.
        """
        unf_content_bytes = unf_content.encode("utf-8")
        signature = b64decode(signature_b64, validate=True)
        config_key = get_setting(f"sources.{self.source}.nrtm4_client_initial_public_key")

        if self.last_status.current_key:
            keys = [
                self.last_status.current_key,
                self.last_status.next_key,
            ]
        else:
            keys = [get_setting(f"sources.{self.source}.nrtm4_client_initial_public_key")]

        for key in keys:
            if key and self._validate_ed25519_signature(key, unf_content_bytes, signature):
                return key

        if self.last_status.current_key and self._validate_ed25519_signature(
            config_key, unf_content_bytes, signature
        ):
            # While technically just a "signature not valid case", it is a rather
            # confusing situation for the user, so gets a special message.
            msg = (
                f"{self.source}: No valid signature found for the Update Notification File for signature"
                f" {signature_b64}. The signature is valid for public key {config_key} set in the"
                " nrtm4_client_initial_public_key setting, but that is only used for initial validation."
                f" IRRD is currently expecting the public key {self.last_status.current_key}. If you want to"
                " clear IRRDs key information and revert to nrtm4_client_initial_public_key, use the"
                " 'irrdctl nrtmv4 client-clear-known-keys' command."
            )
            if self.last_status.next_key:
                msg += f" or {self.last_status.next_key}"
            raise NRTM4ClientError(msg)
        raise NRTM4ClientError(
            f"{self.source}: No valid signature found for any known keys, signature {signature_b64},"
            f" considered public keys: {keys}"
        )

    def _validate_ed25519_signature(self, key_b64: str, content: bytes, signature: bytes) -> bool:
        """
        Verify an Ed25519 signature, given the key in base64, and the content
        and signature in bytes. Returns True or False for validity, raises other
        exceptions for things like an invalid key format.
        """
        try:
            ed25519_public_key_from_str(key_b64).verify(signature, content)
            return True
        except InvalidSignature:
            return False

    def _current_db_status(self) -> Tuple[bool, NRTM4ClientDatabaseStatus]:
        """Look up the current status of self.source in the database."""
        query = DatabaseStatusQuery().source(self.source)
        result = self.database_handler.execute_query(query)
        try:
            status = next(result)
            return status["force_reload"], NRTM4ClientDatabaseStatus(
                session_id=status["nrtm4_client_session_id"],
                version=status["nrtm4_client_version"],
                current_key=status["nrtm4_client_current_key"],
                next_key=status["nrtm4_client_next_key"],
            )
        except StopIteration:
            return False, NRTM4ClientDatabaseStatus(None, None, None, None)

    def _find_next_version(self, unf: NRTM4UpdateNotificationFile, last_version: Optional[int] = None):
        """
        Find the next version to look for, if any.
        If last_version is supplied, it overrides the last version from the DB.
        Returns None if a new snapshot load is required, otherwise the next version.
        """
        if not last_version:
            last_version = self.last_status.version

            if self.force_reload:
                logger.info(f"{self.source}: Forced reload flag set, reloading from snapshot")
                return None

            if not self.last_status.session_id or not last_version:
                logger.info(
                    f"{self.source}: No previous known session ID or version, reloading from snapshot"
                )
                return None

            if unf.session_id != self.last_status.session_id:
                logger.info(
                    f"{self.source}: Session ID has changed from {self.last_status.session_id} to"
                    f" {unf.session_id}, reloading from snapshot"
                )
                return None

        if last_version > unf.version:
            raise NRTM4ClientError(
                f"Update Notification File {self.source}/{unf.session_id} has matching session ID, but"
                f" version {unf.version} is older than local version {last_version}"
            )
        next_version = last_version + 1

        if unf.min_delta_version and unf.min_delta_version > next_version:
            logger.info(
                f"{self.source}: Deltas from current version {last_version} not available on server,"
                " reloading from snapshot"
            )
            return None

        return next_version

    def _load_snapshot(self, unf: NRTM4UpdateNotificationFile):
        """
        Load a snapshot into the database.
        Deals with the usual things for bulk loading, like deleting old objects.
        """
        snapshot_path, should_delete = retrieve_file(
            unf.snapshot.url, return_contents=False, expected_hash=unf.snapshot.hash
        )

        try:
            snapshot_file = open(snapshot_path, "rb")
            snapshot_iterator = jsonseq_decode(snapshot_file)

            NRTM4SnapshotHeader.model_validate(
                next(snapshot_iterator),
                context={
                    "expected_values": {
                        "source": self.source,
                        "session_id": unf.session_id,
                        "version": unf.snapshot.version,
                    }
                },
            )
            roa_validator = BulkRouteROAValidator(self.database_handler) if self.rpki_aware else None
            self.database_handler.delete_all_rpsl_objects_with_journal(self.source)
            self.database_handler.disable_journaling()
            importer = MirrorFileImportParserBase(
                source=self.source,
                database_handler=self.database_handler,
                filename="",
                roa_validator=roa_validator,
            )
            for snapshot_item in snapshot_iterator:
                rpsl_obj = importer.parse_object(snapshot_item["object"])
                if rpsl_obj:
                    self.database_handler.upsert_rpsl_object(rpsl_obj, origin=JournalEntryOrigin.mirror)

            importer.log_report_with_prefix(
                f"{self.source}: import of snapshot at version {unf.snapshot.version}"
            )
            self.database_handler.enable_journaling()
            snapshot_file.close()

        finally:
            if should_delete:
                os.unlink(snapshot_path)

    def _load_deltas(self, unf: NRTM4UpdateNotificationFile, next_version: int):
        """
        Load all deltas found in the UNF, starting with next_version.
        Each delta file is downloaded, parsed, then all changes processed,
        until reaching the final version.
        """
        object_class_filter = get_object_class_filter_for_source(self.source)

        for delta in unf.deltas:
            if delta.version < next_version:
                continue
            delta_path, should_delete = retrieve_file(
                delta.url, return_contents=False, expected_hash=delta.hash
            )
            try:
                delta_file = open(delta_path, "rb")
                delta_iterator = jsonseq_decode(delta_file)

                header = NRTM4DeltaHeader.model_validate(
                    next(delta_iterator),
                    context={
                        "expected_values": {
                            "source": self.source,
                            "session_id": unf.session_id,
                            "version": delta.version,
                        }
                    },
                )

                delta_has_items = False
                for delta_item in delta_iterator:
                    self._process_delta_item(header, delta_item, object_class_filter)
                    delta_has_items = True

                if not delta_has_items:
                    raise NRTM4ClientError(
                        f"Delta file {self.source}/{unf.session_id}/{delta.version} did not contain any"
                        " entries."
                    )

                delta_file.close()
            finally:
                if should_delete:
                    os.unlink(delta_path)

    def _process_delta_item(
        self, header: NRTM4DeltaHeader, delta_item: dict, object_class_filter: Optional[List[str]]
    ) -> None:
        """Process a single item from a delta file into an NRTMOperation."""
        try:
            operation = NRTM4_OPERATION_MAPPING[delta_item["action"]]
            nrtm_kwargs: Dict[str, Any] = {
                "source": self.source,
                "operation": operation,
                "serial": None,
                "origin_identifier": header.origin_identifier,
                "object_class_filter": object_class_filter,
                "rpki_aware": self.rpki_aware,
            }
            if operation == DatabaseOperation.add_or_update:
                nrtm_operation = NRTMOperation(
                    object_text=delta_item["object"],
                    **nrtm_kwargs,
                )
            elif operation == DatabaseOperation.delete:
                nrtm_operation = NRTMOperation(
                    rpsl_pk=delta_item["primary_key"].upper(),
                    object_class=delta_item["object_class"].lower(),
                    **nrtm_kwargs,
                )
            nrtm_operation.save(self.database_handler)
        except KeyError as ke:
            raise NRTM4ClientError(
                f"Delta file {self.source}/{header.session_id}/{header.version} contained invalid entry:"
                f" {ke}: {delta_item}"
            )
