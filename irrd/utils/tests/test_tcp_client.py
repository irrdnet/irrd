import socket
from unittest.mock import Mock

from irrd.utils.test_utils import flatten_mock_calls
from ..whois_client import whois_query


class TestWhoisQuery:
    recv_calls = 0

    def test_query_timeout(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr('irrd.utils.whois_client.socket.socket', lambda: mock_socket)

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            if self.recv_calls > 2:
                raise socket.timeout
            return str(self.recv_calls).encode('utf-8')

        mock_socket.recv = mock_socket_recv
        response = whois_query('192.0.2.1', 43, 'query')
        assert response == '12'

        assert flatten_mock_calls(mock_socket) == [
            ['settimeout', (5,), {}],
            ['connect', (('192.0.2.1', 43),), {}],
            ['sendall', (b'query\n',), {}],
            ['close', (), {}]
        ]
        assert self.recv_calls == 3

    def test_query_end_line(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr('irrd.utils.whois_client.socket.socket', lambda: mock_socket)

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            if self.recv_calls > 2:
                return b'END'
            return str(self.recv_calls).encode('utf-8')

        mock_socket.recv = mock_socket_recv
        response = whois_query('192.0.2.1', 43, 'query', ['END'])
        assert response == '12END'

        assert flatten_mock_calls(mock_socket) == [
            ['settimeout', (5,), {}],
            ['connect', (('192.0.2.1', 43),), {}],
            ['sendall', (b'query\n',), {}],
            ['close', (), {}]
        ]
        assert self.recv_calls == 3

    def test_no_more_data(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr('irrd.utils.whois_client.socket.socket', lambda: mock_socket)

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            if self.recv_calls > 2:
                return b''
            return str(self.recv_calls).encode('utf-8')

        mock_socket.recv = mock_socket_recv
        response = whois_query('192.0.2.1', 43, 'query', ['END'])
        assert response == '12'

        assert flatten_mock_calls(mock_socket) == [
            ['settimeout', (5,), {}],
            ['connect', (('192.0.2.1', 43),), {}],
            ['sendall', (b'query\n',), {}],
            ['close', (), {}]
        ]
        assert self.recv_calls == 3
