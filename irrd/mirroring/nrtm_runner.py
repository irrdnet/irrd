import gzip
import logging
import os
import shutil
from ftplib import FTP
from io import BytesIO
from tempfile import NamedTemporaryFile
from typing import Optional
from urllib.parse import urlparse

from irrd.conf import get_setting
from irrd.storage.api import DatabaseHandler, RPSLDatabaseStatusQuery
from irrd.utils.whois_client import whois_query
from .parser import MirrorFullImportParser, NRTMStreamParser

logger = logging.getLogger(__name__)


class MirrorUpdateRunner:
    """
    This MirrorUpdateRunner is the entry point for updating a single
    database mirror, depending on current state.

    If there is no current mirror, will call MirrorFullImportRunner
    to run a new import from full dump files.
    Otherwise, will call NRTMUpdateStreamRunner to retrieve new updates
    from NRTM.
    """
    def __init__(self, source: str) -> None:
        self.source = source
        self.full_import_runner = MirrorFullImportRunner(source)
        self.update_stream_runner = NRTMUpdateStreamRunner(source)

    def run(self) -> None:
        self.database_handler = DatabaseHandler()

        serial_newest_seen = self._serial_newest_seen()
        logger.debug(f'Most recent serial seen for {self.source}: {serial_newest_seen}')
        if not serial_newest_seen:
            self.full_import_runner.run(database_handler=self.database_handler)
        else:
            self.update_stream_runner.run(serial_newest_seen, database_handler=self.database_handler)
        self.database_handler.commit()
        self.database_handler.close()

    def _serial_newest_seen(self) -> Optional[int]:
        query = RPSLDatabaseStatusQuery().source(self.source)
        result = self.database_handler.execute_query(query)
        try:
            return next(result)['serial_newest_seen']
        except StopIteration:
            return None


class MirrorFullImportRunner:
    """
    This runner performs a full import from database dumps for a single
    mirrored source. URLs for full dump file(s), and the URL for the serial
    they match, are provided in configuration.

    Files are downloaded, gunzipped if needed, and then sent through the
    MirrorFullImportParser.
    """
    def __init__(self, source: str) -> None:
        self.source = source

    def run(self, database_handler: DatabaseHandler):
        # TODO: delete old RPSL objects from the DB
        dump_sources = get_setting(f'sources.{self.source}.dump_source').split(',')
        dump_serial_source = get_setting(f'sources.{self.source}.dump_serial_source')

        if not dump_sources or not dump_serial_source:
            logger.debug(f'Skipping full import for {self.source}, dump_source or dump_serial_source not set.')
            return

        logger.info(f'Running full import of {self.source} from {dump_sources}, serial from {dump_serial_source}')

        dump_serial = self._retrieve_file(dump_serial_source, use_tempfile=False)
        dump_filenames = [self._retrieve_file(dump_source, use_tempfile=True) for dump_source in dump_sources]

        database_handler.disable_journaling()
        for dump_filename in dump_filenames:
            MirrorFullImportParser(source=self.source, filename=dump_filename, serial=dump_serial, strict_validation=False,
                                   database_handler=database_handler)
            os.unlink(dump_filename)

    def _retrieve_file(self, url: str, use_tempfile=True) -> str:
        """
        Retrieve a file (currently only from FTP).

        If use_tempfile is False, the file is read, stripped and then the
        contents are returned. If use_tempfile is True, the data is written
        to a temporary file, and the path of this file is returned.
        It is the responsibility of the caller to unlink thi spath later.

        If the URL ends in .gz, the file is gunzipped before being processed.
        """
        url_parsed = urlparse(url)

        if not url_parsed.scheme == 'ftp':
            raise ValueError(f'Invalid URL: {url} - scheme {url_parsed.scheme} is not supported')

        if use_tempfile:
            destination = NamedTemporaryFile(delete=False)
        else:
            destination = BytesIO()

        ftp = FTP(url_parsed.netloc)
        ftp.login()
        ftp.retrbinary(f'RETR {url_parsed.path}', destination.write)
        ftp.quit()

        if use_tempfile:
            if url.endswith('.gz'):
                zipped_file = destination
                zipped_file.close()
                destination = NamedTemporaryFile(delete=False)
                logger.debug(f'Downloaded file is expected to be gzipped, gunzipping from {zipped_file.name}')
                with gzip.open(zipped_file.name, 'rb') as f_in:
                    shutil.copyfileobj(f_in, destination)
                os.unlink(zipped_file.name)

            destination.close()

            logger.info(f'Downloaded {url} to {destination.name}')
            return destination.name
        else:
            value = destination.getvalue().decode('ascii').strip()  # type: ignore
            logger.info(f'Downloaded {url}, contained {value}')
            return value


class NRTMUpdateStreamRunner:
    """
    This runner attempts to pull updates from an NRTM stream for a specific
    mirrored database.
    """
    def __init__(self, source: str) -> None:
        self.source = source

    def run(self, serial_newest_seen: int, database_handler: DatabaseHandler):
        serial_start = serial_newest_seen + 1
        nrtm_host = get_setting(f'sources.{self.source}.nrtm_host')
        nrtm_port = get_setting(f'sources.{self.source}.nrtm_port')
        if not nrtm_host or not nrtm_port:
            logger.debug(f'Skipping NRTM updates for {self.source}, nrtm_host or nrtm_port not set.')
            return

        end_markings = [
            f'\n%END {self.source}\n',
            f'\n% END {self.source}\n',
            '\n%ERROR',
            '\n% ERROR',
        ]

        logger.info(f'Retrieving NRTM updates for {self.source} from serial {serial_start} on {nrtm_host}:{nrtm_port}')
        query = f'-g {self.source}:3:{serial_start}-LAST'
        response = whois_query(nrtm_host, nrtm_port, query, end_markings)
        logger.debug(f'{self.source} Received buffer: {response.strip()}')

        stream_parser = NRTMStreamParser(self.source, response)
        for operation in stream_parser.operations:
            operation.save(database_handler)
