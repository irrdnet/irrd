import socket
from typing import List, Tuple, Optional


def whois_query(host: str, port: int, query: str, end_markings: List[str]=None) -> str:
    query = query.strip() + '\n'
    if end_markings:
        end_markings_bytes = [mark.encode('utf-8') for mark in end_markings]
    else:
        end_markings_bytes = []

    s = socket.socket()
    s.settimeout(5)
    s.connect((host, port))

    s.sendall(query.encode('utf-8'))

    buffer = b''
    while not any([end_marking in buffer for end_marking in end_markings_bytes]):
        try:
            data = s.recv(1024)
        except socket.timeout:
            break
        if not data:
            break
        buffer += data
    s.close()

    return buffer.decode('utf-8', errors='backslashreplace')


def whois_query_irrd(host: str, port: int, query: str) -> str:
    query = query.strip() + '\n'

    s = socket.socket()
    s.settimeout(5)
    s.connect((host, port))

    s.sendall(query.encode('utf-8'))

    buffer = b''
    expected_data_length = None
    data_offset = None
    while True:
        try:
            data = s.recv(1024)
        except socket.timeout:
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
        if expected_data_length and data_offset and len(buffer) > (expected_data_length + data_offset):
            break
    s.close()

    if not expected_data_length or not data_offset:
        raise ValueError(f'Data receiving ended without a valid IRRD-format response.')
    if len(buffer) < (expected_data_length + data_offset):
        raise ValueError(f'Unable to receive all expected {expected_data_length} bytes')

    return buffer[data_offset:expected_data_length+data_offset-1].decode('utf-8', errors='backslashreplace')


def whois_query_source_status(host: str, port: int, source: str) -> Tuple[Optional[bool], int, int, Optional[int]]:
    remote_status = whois_query_irrd(host, port, f'!j{source}')

    # Fields are: source, mirrorable, serials in journal, optional dump serial
    fields = remote_status.split(':')
    match_source = fields[0].upper()
    if match_source != source.upper():
        raise ValueError(f'Received invalid source {match_source}, expecting {source}, in status: {remote_status}')

    mirrorable_choices = {'Y': True, 'N': False}
    mirrorable = mirrorable_choices.get(fields[1].upper())

    serial_oldest, serial_newest = fields[2].split('-')
    dump_serial: Optional[int]
    try:
        dump_serial = int(fields[3])
    except IndexError:
        dump_serial = None

    return mirrorable, int(serial_oldest), int(serial_newest), dump_serial
