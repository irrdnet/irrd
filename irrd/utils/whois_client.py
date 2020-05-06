import logging
import socket
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class WhoisQueryError(ValueError):
    pass


def whois_query(host: str, port: int, query: str, end_markings: List[str]=None) -> str:
    """
    Perform a query on a whois server, connecting to the specified host and port.

    Will continue to read until no more data can be read, until no more data has
    been sent for 5 seconds, or until an optional end_marking is encountered.
    The end marking could be e.g. 'END NTTCOM' in case of an NRTM stream.
    """
    query = query.strip() + '\n'
    logger.debug(f'Running whois query {query.strip()} on {host} port {port}')
    if end_markings:
        end_markings_bytes = [mark.encode('utf-8') for mark in end_markings]
    else:
        end_markings_bytes = []

    s = socket.create_connection((host, port), timeout=5)
    s.sendall(query.encode('utf-8'))

    buffer = b''
    while not any([end_marking in buffer for end_marking in end_markings_bytes]):
        try:
            data = s.recv(1024*1024)
        except socket.timeout:
            break
        if not data:
            break
        buffer += data
    s.close()

    return buffer.decode('utf-8', errors='backslashreplace')


def whois_query_irrd(host: str, port: int, query: str) -> Optional[str]:
    """
    Perform a whois query, expecting an IRRD-style output format.

    This is a variant of whois_query(), as it uses the additional metadata
    provided by the IRRD output format to know when the full response has
    been received, and whether the full response has been received.
    """
    query = query.strip() + '\n'
    logger.debug(f'Running IRRD whois query {query.strip()} on {host} port {port}')

    s = socket.create_connection((host, port), timeout=5)
    s.sendall(query.encode('utf-8'))

    buffer = b''
    expected_data_length = None
    data_offset = None
    error = None

    while True:
        try:
            data = s.recv(1024)
        except (socket.timeout, ConnectionError):
            break
        if not data:
            break
        buffer += data
        if not expected_data_length:
            decoded_buffer = buffer.decode('utf-8', errors='backslashreplace')
            if '\n' in decoded_buffer:
                length_line = decoded_buffer.splitlines()[0]
                if length_line.startswith('A'):
                    expected_data_length = int(length_line[1:])
                    data_offset = len(length_line) + 1
                elif length_line in ['C', 'D']:
                    break
                elif length_line.startswith('F'):
                    error = length_line[2:]
                    break
        if expected_data_length and data_offset and len(buffer) > (expected_data_length + data_offset):
            break
    s.close()

    if error:
        raise WhoisQueryError(error)
    if not expected_data_length and buffer in [b'C\n', b'D\n']:
        return None
    if not expected_data_length or not data_offset:
        raise ValueError(f'Data receiving ended without a valid IRRD-format response, query {query},'
                         f'received: {buffer.decode("ascii", "ignore")}')
    if len(buffer) < (expected_data_length + data_offset):
        raise ValueError(f'Unable to receive all expected {expected_data_length} bytes')

    return buffer[data_offset:expected_data_length+data_offset-1].decode('utf-8', errors='backslashreplace')


def whois_query_source_status(host: str, port: int, source: str) -> Tuple[Optional[bool], int, int, Optional[int]]:
    """
    Query the status of a particular source against an NRTM server,
    which supports IRRD-style !j queries.

    Will return a tuple with:
    - is this server mirrorable
    - the oldest serial available
    - the newest serial available
    - the serial of the latest export
    """
    remote_status = whois_query_irrd(host, port, f'!j{source}')

    # Fields are: source, mirrorable, serials in journal, optional last export serial
    if not remote_status:
        raise ValueError(f'Source status query on {host}:{port} failed: empty response')
    fields = remote_status.split(':')
    match_source = fields[0].upper()
    if match_source != source.upper():
        raise ValueError(f'Received invalid source {match_source}, expecting {source}, in status: {remote_status}')

    mirrorable_choices = {'Y': True, 'N': False}
    mirrorable = mirrorable_choices.get(fields[1].upper())

    serial_oldest, serial_newest = fields[2].split('-')
    export_serial: Optional[int]
    try:
        export_serial = int(fields[3])
    except IndexError:
        export_serial = None

    return mirrorable, int(serial_oldest), int(serial_newest), export_serial
