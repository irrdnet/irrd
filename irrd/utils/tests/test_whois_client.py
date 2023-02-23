import socket
from typing import Optional
from unittest.mock import Mock

import pytest

from ..test_utils import flatten_mock_calls
from ..whois_client import (
    WhoisQueryError,
    whois_query,
    whois_query_irrd,
    whois_query_source_status,
)


class TestWhoisQuery:
    recv_calls = 0

    def test_query_end_line(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr(
            "irrd.utils.whois_client.socket.create_connection", lambda address, timeout: mock_socket
        )

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            if self.recv_calls > 2:
                return b"END"
            return str(self.recv_calls).encode("utf-8")

        mock_socket.recv = mock_socket_recv
        response = whois_query("192.0.2.1", 43, "query", ["END"])
        assert response == "12END"

        assert flatten_mock_calls(mock_socket) == [["sendall", (b"query\n",), {}], ["close", (), {}]]
        assert self.recv_calls == 3

    def test_no_more_data(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr(
            "irrd.utils.whois_client.socket.create_connection", lambda address, timeout: mock_socket
        )

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            if self.recv_calls > 2:
                return b""
            return str(self.recv_calls).encode("utf-8")

        mock_socket.recv = mock_socket_recv
        response = whois_query("192.0.2.1", 43, "query", ["END"])
        assert response == "12"

        assert flatten_mock_calls(mock_socket) == [["sendall", (b"query\n",), {}], ["close", (), {}]]
        assert self.recv_calls == 3

    def test_query_timeout(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr(
            "irrd.utils.whois_client.socket.create_connection", lambda address, timeout: mock_socket
        )

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            if self.recv_calls > 2:
                raise socket.timeout
            return str(self.recv_calls).encode("utf-8")

        mock_socket.recv = mock_socket_recv
        response = whois_query("192.0.2.1", 43, "query")
        assert response == "12"

        assert flatten_mock_calls(mock_socket) == [["sendall", (b"query\n",), {}], ["close", (), {}]]
        assert self.recv_calls == 3


class TestWhoisQueryIRRD:
    recv_calls = 0

    def test_query_valid(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr(
            "irrd.utils.whois_client.socket.create_connection", lambda address, timeout: mock_socket
        )

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            if self.recv_calls == 1:
                return b"A2\n"
            if self.recv_calls > 2:
                return b"C\n"
            return str(self.recv_calls).encode("utf-8")

        mock_socket.recv = mock_socket_recv
        response = whois_query_irrd("192.0.2.1", 43, "query")
        assert response == "2"

        assert flatten_mock_calls(mock_socket) == [["sendall", (b"query\n",), {}], ["close", (), {}]]
        assert self.recv_calls == 3

    def test_query_valid_empty_c_response(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr(
            "irrd.utils.whois_client.socket.create_connection", lambda address, timeout: mock_socket
        )

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            return b"C\n"

        mock_socket.recv = mock_socket_recv
        response = whois_query_irrd("192.0.2.1", 43, "query")
        assert response is None

        assert flatten_mock_calls(mock_socket) == [["sendall", (b"query\n",), {}], ["close", (), {}]]
        assert self.recv_calls == 1

    def test_query_valid_empty_d_response(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr(
            "irrd.utils.whois_client.socket.create_connection", lambda address, timeout: mock_socket
        )

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            return b"D\n"

        mock_socket.recv = mock_socket_recv
        response = whois_query_irrd("192.0.2.1", 43, "query")
        assert response is None

        assert flatten_mock_calls(mock_socket) == [["sendall", (b"query\n",), {}], ["close", (), {}]]
        assert self.recv_calls == 1

    def test_query_invalid_f_response(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr(
            "irrd.utils.whois_client.socket.create_connection", lambda address, timeout: mock_socket
        )

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            return b"F unrecognized command\n"

        mock_socket.recv = mock_socket_recv
        with pytest.raises(WhoisQueryError) as wqe:
            whois_query_irrd("192.0.2.1", 43, "query")
        assert "unrecognized command" in str(wqe.value)

        assert flatten_mock_calls(mock_socket) == [["sendall", (b"query\n",), {}], ["close", (), {}]]
        assert self.recv_calls == 1

    def test_no_valid_start(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr(
            "irrd.utils.whois_client.socket.create_connection", lambda address, timeout: mock_socket
        )

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            if self.recv_calls > 2:
                return b""
            return str(self.recv_calls).encode("utf-8")

        mock_socket.recv = mock_socket_recv
        with pytest.raises(ValueError) as ve:
            whois_query_irrd("192.0.2.1", 43, "query")
        assert "without a valid IRRD-format response" in str(ve.value)

        assert flatten_mock_calls(mock_socket) == [["sendall", (b"query\n",), {}], ["close", (), {}]]
        assert self.recv_calls == 3

    def test_no_more_data(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr(
            "irrd.utils.whois_client.socket.create_connection", lambda address, timeout: mock_socket
        )

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            if self.recv_calls > 2:
                return b""
            if self.recv_calls == 1:
                return b"A2\n"
            return str(self.recv_calls).encode("utf-8")

        mock_socket.recv = mock_socket_recv
        with pytest.raises(ValueError) as ve:
            whois_query_irrd("192.0.2.1", 43, "query")
        assert "Unable to receive " in str(ve.value)

        assert flatten_mock_calls(mock_socket) == [["sendall", (b"query\n",), {}], ["close", (), {}]]
        assert self.recv_calls == 3

    def test_query_timeout(self, monkeypatch):
        self.recv_calls = 0
        mock_socket = Mock()
        monkeypatch.setattr(
            "irrd.utils.whois_client.socket.create_connection", lambda address, timeout: mock_socket
        )

        def mock_socket_recv(bytes) -> bytes:
            self.recv_calls += 1
            if self.recv_calls > 2:
                raise socket.timeout
            if self.recv_calls == 1:
                return b"A2\n"
            return str(self.recv_calls).encode("utf-8")

        mock_socket.recv = mock_socket_recv
        with pytest.raises(ValueError) as ve:
            whois_query_irrd("192.0.2.1", 43, "query")
        assert "Unable to receive " in str(ve.value)

        assert flatten_mock_calls(mock_socket) == [["sendall", (b"query\n",), {}], ["close", (), {}]]
        assert self.recv_calls == 3


class TestQuerySourceStatus:
    def test_query_valid_with_export(self, monkeypatch):
        def mock_whois_query_irrd(host: str, port: int, query: str) -> Optional[str]:
            assert host == "host"
            assert port == 43
            assert query == "!jTEST"
            return "TEST:Y:1-2:1"

        monkeypatch.setattr("irrd.utils.whois_client.whois_query_irrd", mock_whois_query_irrd)

        mirrorable, serial_oldest, serial_newest, export_serial = whois_query_source_status(
            "host", 43, "TEST"
        )
        assert mirrorable is True
        assert serial_oldest == 1
        assert serial_newest == 2
        assert export_serial == 1

    def test_query_valid_without_export(self, monkeypatch):
        def mock_whois_query_irrd(host: str, port: int, query: str) -> Optional[str]:
            assert host == "host"
            assert port == 43
            assert query == "!jTEST"
            return "TEST:X:1-2"

        monkeypatch.setattr("irrd.utils.whois_client.whois_query_irrd", mock_whois_query_irrd)

        mirrorable, serial_oldest, serial_newest, export_serial = whois_query_source_status(
            "host", 43, "TEST"
        )
        assert mirrorable is None
        assert serial_oldest == 1
        assert serial_newest == 2
        assert export_serial is None

    def test_query_invalid_source(self, monkeypatch):
        def mock_whois_query_irrd(host: str, port: int, query: str) -> Optional[str]:
            assert host == "host"
            assert port == 43
            assert query == "!jTEST"
            return "NOT-TEST:Y:1-2:1"

        monkeypatch.setattr("irrd.utils.whois_client.whois_query_irrd", mock_whois_query_irrd)

        with pytest.raises(ValueError) as ve:
            whois_query_source_status("host", 43, "TEST")
        assert "Received invalid source NOT-TEST" in str(ve.value)

    def test_query_empty_response(self, monkeypatch):
        def mock_whois_query_irrd(host: str, port: int, query: str) -> Optional[str]:
            assert host == "host"
            assert port == 43
            assert query == "!jTEST"
            return None

        monkeypatch.setattr("irrd.utils.whois_client.whois_query_irrd", mock_whois_query_irrd)

        with pytest.raises(ValueError) as ve:
            whois_query_source_status("host", 43, "TEST")
        assert "empty response" in str(ve.value)
