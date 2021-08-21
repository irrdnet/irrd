import os

import gzip
import logging
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from irrd.conf import get_setting
from irrd.rpki.status import RPKIStatus
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery, DatabaseStatusQuery
from irrd.utils.text import remove_auth_hashes as remove_auth_hashes_func

EXPORT_PERMISSIONS = 0o644

logger = logging.getLogger(__name__)


class SourceExportRunner:
    """
    This SourceExportRunner is the entry point for the export process
    for a single source.

    A gzipped file will be created in the export_destination directory
    with the contents of the source, along with a CURRENTSERIAL file.

    The contents of the source are first written to a temporary file, and
    then moved in place.
    """

    def __init__(self, source: str) -> None:
        self.source = source

    def run(self) -> None:
        self.database_handler = DatabaseHandler()
        try:
            export_destination = get_setting(f'sources.{self.source}.export_destination')
            if export_destination:
                logger.info(f'Starting a source export for {self.source} to {export_destination}')
                self._export(export_destination)

            export_destination_unfiltered = get_setting(f'sources.{self.source}.export_destination_unfiltered')
            if export_destination_unfiltered:
                logger.info(f'Starting an unfiltered source export for {self.source} '
                            f'to {export_destination_unfiltered}')
                self._export(export_destination_unfiltered, remove_auth_hashes=False)

            self.database_handler.commit()
        except Exception as exc:
            logger.error(f'An exception occurred while attempting to run an export '
                         f'for {self.source}: {exc}', exc_info=exc)
        finally:
            self.database_handler.close()

    def _export(self, export_destination, remove_auth_hashes=True):
        filename_export = Path(export_destination) / f'{self.source.lower()}.db.gz'
        export_tmpfile = NamedTemporaryFile(delete=False)
        filename_serial = Path(export_destination) / f'{self.source.upper()}.CURRENTSERIAL'

        query = DatabaseStatusQuery().source(self.source)

        try:
            serial = next(self.database_handler.execute_query(query))['serial_newest_seen']
        except StopIteration:
            serial = None

        with gzip.open(export_tmpfile.name, 'wb') as fh:
            query = RPSLDatabaseQuery().sources([self.source])
            query = query.rpki_status([RPKIStatus.not_found, RPKIStatus.valid])
            query = query.scopefilter_status([ScopeFilterStatus.in_scope])
            for obj in self.database_handler.execute_query(query):
                object_text = obj['object_text']
                if remove_auth_hashes:
                    object_text = remove_auth_hashes_func(object_text)
                object_bytes = object_text.encode('utf-8')
                fh.write(object_bytes + b'\n')
            fh.write(b'# EOF\n')

        os.chmod(export_tmpfile.name, EXPORT_PERMISSIONS)
        if filename_export.exists():
            os.unlink(filename_export)
        if filename_serial.exists():
            os.unlink(filename_serial)
        shutil.move(export_tmpfile.name, filename_export)

        if serial is not None:
            with open(filename_serial, 'w') as fh:
                fh.write(str(serial))
            os.chmod(filename_serial, EXPORT_PERMISSIONS)

        self.database_handler.record_serial_exported(self.source, serial)
        logger.info(f'Export for {self.source} complete at serial {serial}, stored in {filename_export} / {filename_serial}')
