import copy
import datetime
import gzip
import logging
import os
import secrets
import uuid
from pathlib import Path
from typing import Optional

from pytz import UTC

from irrd.conf import (
    DEFAULT_SOURCE_NRTM4_SERVER_SNAPSHOT_FREQUENCY,
    NRTM4_SERVER_DELTA_EXPIRY_TIME,
    get_setting,
)
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import DatabaseOperation, NRTM4ServerDatabaseStatus
from irrd.storage.queries import (
    DatabaseStatusQuery,
    RPSLDatabaseJournalQuery,
    RPSLDatabaseJournalStatisticsQuery,
    RPSLDatabaseQuery,
)
from irrd.utils.crypto import eckey_from_config, eckey_public_key_as_str, jws_serialize
from irrd.utils.text import dummify_object_text, remove_auth_hashes

from ...utils.process_support import get_lockfile
from ..retrieval import file_hash_sha256
from . import UPDATE_NOTIFICATION_FILENAME
from .jsonseq import jsonseq_encode, jsonseq_encode_one
from .nrtm4_types import (
    NRTM4DeltaHeader,
    NRTM4FileReference,
    NRTM4SnapshotHeader,
    NRTM4UpdateNotificationFile,
)

logger = logging.getLogger(__name__)

DANGLING_SNAPSHOT_EXPIRY_TIME = datetime.timedelta(minutes=5)


class NRTM4Server:
    """
    This is a small wrapper around NRTM4ServerWriter to interface with MirrorScheduler.
    """

    def __init__(self, source: str):
        self.source = source

    def run(self) -> None:
        database_handler = DatabaseHandler()
        try:
            NRTM4ServerWriter(self.source, database_handler).run()
        except Exception as exc:  # pragma: no cover
            logger.error(
                f"{self.source}: An exception occurred during an NRTMv4 server update: {exc}", exc_info=exc
            )
            raise
        finally:
            database_handler.close()


class NRTM4ServerWriter:
    """
    NRTMv4 server writer/updater.
    Covers all steps of updating/creating NRTMv4 server repositories.

    The status is represented in self.status, updated with new/expired
    snapshots/deltas, and written to the database.
    The new UNF is derived from the status.
    """

    def __init__(
        self,
        source: str,
        database_handler: DatabaseHandler,
    ):
        self.database_handler = database_handler
        self.source = source
        self.path = Path(get_setting(f"sources.{self.source}.nrtm4_server_local_path"))
        self.status_lockfile_path = Path(get_setting("piddir")) / f"nrtm4-server-status-{source}.lock"
        self.snapshot_lockfile_path = Path(get_setting("piddir")) / f"nrtm4-server-snapshot-{source}.lock"
        self.timestamp = datetime.datetime.now(tz=UTC)
        max_serial_global = next(self.database_handler.execute_query(RPSLDatabaseJournalStatisticsQuery()))[
            "max_serial_global"
        ]
        # If the journal is entirely empty on a new database, there is no serial at all yet
        self.max_serial_global = max_serial_global if max_serial_global else 0

    def _update_status(self):
        self.status = None
        self.original_status = None
        try:
            database_status = next(
                self.database_handler.execute_query(DatabaseStatusQuery().source(self.source))
            )
        except StopIteration:
            logger.debug(
                f"{self.source}: NRTMv4 server found no current status yet, possibly new source, exiting"
            )
            return
        self.force_reload = database_status["force_reload"]
        self.status = NRTM4ServerDatabaseStatus.from_dict(database_status)
        self.original_status = copy.deepcopy(self.status)

    def run(self):
        status_lockfile = get_lockfile(self.status_lockfile_path, blocking=False)
        if not status_lockfile:  # pragma: no cover - covered in integration
            logger.debug(
                f"{self.source}: NRTMv4 server update cancelled, status changes locked by other server"
            )
            return

        self._update_status()
        if not self.status:
            return
        if self.force_reload:
            logger.debug(
                f"{self.source}: NRTMv4 server update cancelled, as force_reload is set - waiting on new"
                " import"
            )
            return

        logger.debug(f"{self.source}: NRTMv4 server starting update in {self.path}")

        if not self._verify_integrity():
            logger.error(f"{self.source}: integrity check failed, discarding existing session")
            self.status.session_id = None

        is_initialisation = not bool(self.status.session_id)
        if is_initialisation:
            self.status.session_id = uuid.uuid4()
            self.status.version = 1
            self.status.last_snapshot_version = None
            self.status.last_snapshot_global_serial = None
            self.status.previous_deltas = []
            logger.info(
                f"{self.source}: No current session ID in database, starting new NRTMv4 session with ID"
                f" {self.status.session_id}"
            )

        # Deltas are not created when the repository has only just been initialised.
        if not is_initialisation:
            try:
                serial_global_start = self.status.previous_deltas[-1]["serial_global_end"]
            except IndexError:
                serial_global_start = self.status.last_snapshot_global_serial
            serial_global_start += 1

            next_version = self.status.version + 1

            filename = self._write_delta(next_version, serial_global_start)
            if filename:
                self.status.version = next_version
                self.status.previous_deltas.append(
                    {
                        "filename": filename,
                        "hash": file_hash_sha256(self.path / filename).hexdigest(),
                        "timestamp": self.timestamp.timestamp(),
                        "version": self.status.version,
                        "serial_global_start": serial_global_start,
                        "serial_global_end": self.max_serial_global,
                    }
                )
                logger.info(
                    f"{self.source}: Created delta {self.status.version} for global serial"
                    f" {serial_global_start}-{self.max_serial_global} in {filename}"
                )

            self._commit_status()
            status_lockfile.close()

        snapshot_frequency = datetime.timedelta(
            seconds=get_setting(
                f"sources.{self.source}.nrtm4_server_snapshot_frequency",
                DEFAULT_SOURCE_NRTM4_SERVER_SNAPSHOT_FREQUENCY,
            )
        )
        # If the data has changed since the last snapshot, Deltas will have been generated,
        # therefore the version will have been incremented.
        data_has_changed = self.status.last_snapshot_version != self.status.version
        should_create_snapshot = not self.status.last_snapshot_version or (
            data_has_changed and (self.timestamp - self.status.last_snapshot_timestamp) > snapshot_frequency
        )
        if should_create_snapshot:
            snapshot_lockfile = get_lockfile(self.snapshot_lockfile_path, blocking=False)
            if not snapshot_lockfile:  # pragma: no cover - covered in integration
                logger.debug(
                    f"{self.source}: Not creating a snapshot, as a snapshot runner is already active"
                )
                if not status_lockfile.closed:
                    self._commit_status()
                    status_lockfile.close()
                return

            logger.debug(f"{self.source}: Generating a new snapshot at version {self.status.version}")
            snapshot_file = self._write_snapshot(self.status.version)
            snapshot_version = self.status.version

            if not is_initialisation:  # pragma: no cover - covered in integration
                status_lockfile = get_lockfile(self.status_lockfile_path, blocking=True)
                # Commit to refresh the transaction
                self.database_handler.commit()
                self._update_status()

            self.status.last_snapshot_filename = snapshot_file
            self.status.last_snapshot_version = snapshot_version
            self.status.last_snapshot_global_serial = self.max_serial_global
            self.status.last_snapshot_timestamp = self.timestamp
            self.status.last_snapshot_hash = file_hash_sha256(
                self.path / self.status.last_snapshot_filename
            ).hexdigest()
            logger.info(
                f"{self.source}: Created snapshot {snapshot_version} for global serial"
                f" {self.max_serial_global} in {self.status.last_snapshot_filename}"
            )
            self._commit_status()
            status_lockfile.close()
            snapshot_lockfile.close()

        # Ensure UNF is updated at least every 24h - this can only execute
        # if none of the code above has written an updated UNF.
        if self.status.last_update_notification_file_update <= self.timestamp - datetime.timedelta(hours=24):
            self._commit_status()

    def _commit_status(self) -> None:
        self._expire_deltas()
        self._write_unf()

        if self.status != self.original_status:
            self.database_handler.record_nrtm4_server_status(self.source, self.status)
        self._expire_snapshots()
        self.database_handler.commit()

    def _write_unf(self) -> None:
        """
        Write the Update Notification File.
        This is based on settings and self.status.
        """
        assert self.status
        next_signing_private_key = eckey_from_config(
            f"sources.{self.source}.nrtm4_server_private_key_next", permit_empty=True
        )
        next_signing_public_key = (
            eckey_public_key_as_str(next_signing_private_key) if next_signing_private_key else None
        )
        unf = NRTM4UpdateNotificationFile(
            nrtm_version=4,
            type="notification",
            source=self.source,
            session_id=self.status.session_id,
            version=self.status.version,
            timestamp=self.timestamp,
            next_signing_key=next_signing_public_key,
            snapshot=NRTM4FileReference(
                version=self.status.last_snapshot_version,
                url=self.status.last_snapshot_filename,
                hash=self.status.last_snapshot_hash,
            ),
            deltas=[
                NRTM4FileReference(version=delta["version"], url=delta["filename"], hash=delta["hash"])
                for delta in self.status.previous_deltas
            ],
        )
        unf_content = unf.model_dump_json(exclude_none=True, include=unf.model_fields_set).encode("ascii")
        private_key = eckey_from_config(f"sources.{self.source}.nrtm4_server_private_key")
        assert private_key
        unf_serialized = jws_serialize(unf_content, private_key)
        with open(self.path / UPDATE_NOTIFICATION_FILENAME, "w") as unf_file:
            unf_file.write(unf_serialized)
        self.status.last_update_notification_file_update = unf.timestamp

    def _expire_deltas(self) -> None:
        """
        Expire old delta files and remove any dangling ones.
        Delta files are removed from disk and metadata after the expiry time.
        Any delta files not referred in the current known deltas are deleted.
        """
        new_delta_list = []
        assert self.status
        for delta in self.status.previous_deltas:
            delta_timestamp = datetime.datetime.fromtimestamp(delta["timestamp"], tz=UTC)
            if self.timestamp - delta_timestamp > NRTM4_SERVER_DELTA_EXPIRY_TIME:
                (self.path / delta["filename"]).unlink()
                logger.debug(f"{self.source}: Expired older delta {delta['version']}")

            else:
                new_delta_list.append(delta)
        self.status.previous_deltas = new_delta_list

        known_delta_filenames = {d["filename"] for d in self.status.previous_deltas}
        for file_path in self.path.glob("nrtm-delta.*.json.gz"):
            if file_path.name not in known_delta_filenames:
                file_path.unlink()
                logger.debug(f"{self.source}: Removed dangling delta file {file_path.name}")

    def _expire_snapshots(self) -> None:
        """
        Expire old snapshots.
        To avoid race conditions, these files are kept around after they
        are no longer referred. This method cleans them up.
        """
        assert self.status
        snapshot_pattern = "nrtm-snapshot.*.json.gz"
        for file_path in self.path.glob(snapshot_pattern):
            modification_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path), tz=UTC)
            if (
                self.timestamp - modification_time > DANGLING_SNAPSHOT_EXPIRY_TIME
                and file_path.name != self.status.last_snapshot_filename
            ):
                file_path.unlink()

    def _write_snapshot(self, version: int) -> str:
        """
        Write a snapshot of the database, at NRTMv4 version {version}.
        This generates a filename, writes all objects, returns the filename.
        """
        assert self.status
        filename = f"nrtm-snapshot.{self.status.session_id}.{version}.{secrets.token_hex(16)}.json.gz"
        query = (
            RPSLDatabaseQuery(["object_text", "object_class", "rpsl_pk"])
            .sources([self.source])
            .default_suppression()
        )
        objs = self.database_handler.execute_query(query)

        with gzip.open(self.path / filename, "wb") as outstream:
            header = NRTM4SnapshotHeader(
                nrtm_version=4,
                source=self.source,
                session_id=self.status.session_id,
                version=version,
                type="snapshot",
            )
            jsonseq_encode_one(
                header.model_dump(mode="json", include=header.model_fields_set),
                outstream,
            )
            objs_filtered = (
                {
                    "object": dummify_object_text(
                        remove_auth_hashes(obj["object_text"]),
                        obj["object_class"],
                        self.source,
                        obj["rpsl_pk"],
                    )
                }
                for obj in objs
            )
            jsonseq_encode(objs_filtered, outstream)
        return filename

    def _write_delta(self, version: int, serial_global_start: int) -> Optional[str]:
        """
        Write a delta file, starting at the provided global serial, at NRTMv4 version {version}
        Returns the filename if a delta was written.
        If there are no changes, returns None and does not create any file.
        """
        assert self.status
        filename = f"nrtm-delta.{self.status.session_id}.{version}.{secrets.token_hex(16)}.json.gz"
        query = (
            RPSLDatabaseJournalQuery().sources([self.source]).serial_global_range(start=serial_global_start)
        )
        journal_entries = list(self.database_handler.execute_query(query))
        if not journal_entries:
            return None

        with gzip.open(self.path / filename, "wb") as outstream:
            header = NRTM4DeltaHeader(
                nrtm_version=4,
                source=self.source,
                session_id=self.status.session_id,
                version=version,
                type="delta",
            )
            jsonseq_encode_one(
                header.model_dump(mode="json", include=header.model_fields_set),
                outstream,
            )
            for journal_entry in journal_entries:
                if journal_entry["operation"] == DatabaseOperation.add_or_update:
                    object_text = remove_auth_hashes(journal_entry["object_text"])
                    object_text = dummify_object_text(
                        object_text, journal_entry["object_class"], self.source, journal_entry["rpsl_pk"]
                    )
                    entry_encoded = {
                        "action": "add_modify",
                        "object": object_text,
                    }
                elif journal_entry["operation"] == DatabaseOperation.delete:
                    entry_encoded = {
                        "action": "delete",
                        "object_class": journal_entry["object_class"],
                        "primary_key": journal_entry["rpsl_pk"],
                    }
                else:  # pragma: no cover
                    raise ValueError(f"Unknown journal action: {journal_entry}")
                jsonseq_encode_one(entry_encoded, outstream)
        return filename

    def _verify_integrity(self) -> bool:
        """
        Verify the integrity of current on disk status, by checking all files
        mentioned in self.status are still present. Returns True for success.

        This intentionally does not check all hashes, to reduce overhead.
        """
        assert self.status
        filenames = [delta["filename"] for delta in self.status.previous_deltas]
        if self.status.last_snapshot_filename:
            filenames.append(self.status.last_snapshot_filename)
        for filename in filenames:
            if not (self.path / filename).exists():
                logger.error(f"{self.source}: missing file {filename} in {self.path} in integrity check")
                return False
        return True
