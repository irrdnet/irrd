import gzip
import logging
import os
import shutil
import socket
from ftplib import FTP
from io import StringIO, BytesIO
from tempfile import NamedTemporaryFile
from typing import Optional
from urllib.parse import urlparse

from irrd.conf import get_setting
from irrd.nrtm.nrtm_parser import NRTMBulkParser, NRTMStreamParser
from irrd.storage.api import DatabaseHandler, RPSLDatabaseStatusQuery

logger = logging.getLogger(__name__)


class NRTMInitiatior:
    def __init__(self, source: str) -> None:
        self.source = source

    def run(self) -> None:
        self.database_handler = DatabaseHandler()

        serial_newest_seen = self._serial_newest_seen()
        logger.debug(f'Most recent serial seen for {self.source}: {serial_newest_seen}')
        if not serial_newest_seen:
            self._full_import()
        else:
            self._retrieve_updates(serial_newest_seen)
        self.database_handler.commit()
        self.database_handler.close()

    def _serial_newest_seen(self) -> Optional[int]:
        query = RPSLDatabaseStatusQuery().sources([self.source])
        result = self.database_handler.execute_query(query)
        try:
            return next(result)['serial_newest_seen']
        except StopIteration:
            return None

    def _full_import(self):
        dump_sources = get_setting(f'databases.{self.source}.dump_source').split(',')
        dump_serial_source = get_setting(f'databases.{self.source}.dump_serial_source')

        if not dump_sources or not dump_serial_source:
            logger.debug(f'Skipping full import for {self.source}, dump_source or dump_serial_source not set.')

        logger.info(f'Running full import of {self.source} from {dump_sources}, serial from {dump_serial_source}')

        dump_serial = self._retrieve_file(dump_serial_source, use_tempfile=False)
        dump_filenames = [self._retrieve_file(dump_source, use_tempfile=True) for dump_source in dump_sources]

        self.database_handler.disable_journaling()
        for dump_filename in dump_filenames:
            NRTMBulkParser(source=self.source, filename=dump_filename, serial=dump_serial, strict_validation=False,
                           database_handler=self.database_handler)

        os.unlink(dump_filename)

    def _retrieve_file(self, url: str, use_tempfile=True) -> str:
        url_parsed = urlparse(url)

        if not url_parsed.scheme == 'ftp':
            raise ValueError(f'Invalid URL: {url} - scheme {url_parsed.scheme} is not supported')

        if use_tempfile:
            destination = NamedTemporaryFile(delete=False)
        else:
            destination = BytesIO()

        with FTP(url_parsed.netloc) as ftp:
            ftp.login()
            ftp.retrbinary(f'RETR {url_parsed.path}', destination.write)

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
            value = destination.getvalue().decode('ascii').strip()
            logger.info(f'Downloaded {url}, contained {value}')
            return value

    def _retrieve_updates(self, serial_newest_seen: int):
        return
        serial_start = serial_newest_seen + 1
        nrtm_host = get_setting(f'databases.{self.source}.nrtm_host')
        nrtm_port = get_setting(f'databases.{self.source}.nrtm_port')
        if not nrtm_host or not nrtm_port:
            logger.debug(f'Skipping NRTM updates for {self.source}, nrtm_host or nrtm_port not set.')
            return
        logger.info(f'Retrieving NRTM updates for {self.source} from serial {serial_start} on {nrtm_host}:{nrtm_port}')

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((nrtm_host, nrtm_port))
        query = f'-g {self.source}:3:{serial_start}-LAST\n'

        s.sendall(query.encode('ascii'))
        buffer = b''
        end_markings = [
            b'\n%END ' + self.source.encode('ascii') + b'\n',
            b'\n% END ' + self.source.encode('ascii') + b'\n',
            # b'\n%ERROR',
            # b'\n% ERROR',
        ]
        while not any([end_marking in buffer for end_marking in end_markings]):
            try:
                data = s.recv(1024)
            except socket.timeout:
                break
            if not data:
                break
            buffer += data
        s.close()

        stream_parser = NRTMStreamParser(buffer.decode('utf-8', errors='backslashreplace'))
        for operation in stream_parser.operations:
            operation.save(self.database_handler)
