import socket
from typing import List


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
