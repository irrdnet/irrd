import socket
import time
from io import BytesIO
from queue import Queue
from unittest.mock import Mock

import pytest

from irrd.storage.preload import Preloader

from ..server import WhoisWorker


class MockSocket:
    def __init__(self):
        # rfile (for read) and wfile (for write) are from the perspective
        # of the WhoisWorker, opposite of the test's perspective
        self.rfile = BytesIO()
        self.wfile = BytesIO()
        self.shutdown_called = False
        self.close_called = False
        self.timeout_set = None

    def makefile(self, mode, bufsize):
        return self.wfile if "w" in mode else self.rfile

    def sendall(self, bytes):
        self.wfile.write(bytes)

    def shutdown(self, flags):
        self.shutdown_called = True

    def close(self):
        self.close_called = True

    def settimeout(self, timeout):
        self.timeout_set = timeout


@pytest.fixture()
def create_worker(config_override, monkeypatch):
    mock_preloader = Mock(spec=Preloader)
    monkeypatch.setattr("irrd.server.whois.server.Preloader", lambda: mock_preloader)

    config_override(
        {
            "redis_url": "redis://invalid-host.example.com",  # Not actually used
        }
    )
    queue = Queue()
    worker = WhoisWorker(queue)
    request = MockSocket()
    queue.put((request, ("192.0.2.1", 99999)))
    yield worker, request


class TestWhoisWorker:
    def test_whois_request_worker_no_access_list(self, create_worker):
        worker, request = create_worker
        # Empty query in first line should be ignored.
        request.rfile.write(b" \n!v\r\n")
        request.rfile.seek(0)
        worker.run(keep_running=False)

        assert worker.client_str == "192.0.2.1:99999"
        request.wfile.seek(0)
        assert b"IRRd -- version" in request.wfile.read()
        assert request.shutdown_called
        assert request.close_called
        assert request.timeout_set == 5

    def test_whois_request_worker_exception(self, create_worker, monkeypatch, caplog):
        monkeypatch.setattr(
            "irrd.server.whois.server.WhoisQueryParser", Mock(side_effect=OSError("expected"))
        )

        worker, request = create_worker
        request.rfile.write(b"!v\r\n")
        request.rfile.seek(0)
        worker.run(keep_running=False)

        request.wfile.seek(0)
        assert not request.wfile.read()
        assert request.shutdown_called
        assert request.close_called
        assert "Failed to handle whois connection" in caplog.text

    def test_whois_request_worker_preload_failed(self, create_worker, monkeypatch, caplog):
        monkeypatch.setattr("irrd.server.whois.server.Preloader", Mock(side_effect=OSError("expected")))

        worker, request = create_worker
        request.rfile.write(b"!v\r\n")
        request.rfile.seek(0)
        worker.run(keep_running=False)

        request.wfile.seek(0)
        assert not request.wfile.read()
        assert "worker failed to initialise preloader" in caplog.text

    def test_whois_request_worker_timeout(self, create_worker):
        worker, request = create_worker

        request.rfile = Mock()
        readline_call_count = 0

        # This mock implementation simulates user behaviour that
        # should trigger a timeout.
        # First, !! is sent to prevent the connection from closing right away.
        # Then, !t1 is used to set a very short timeout.
        # Third, readline() blocks for 2s, simulating a user not sending
        # any query to IRRd, triggering the shutdown call by the timeout.
        def mock_readline():
            nonlocal readline_call_count
            readline_call_count += 1
            if readline_call_count == 1:
                return b"!!\n"
            if readline_call_count == 2:
                return b"!t1\n"
            if readline_call_count == 3:
                time.sleep(2)
                return b""

        request.rfile.readline = mock_readline

        request.rfile.seek(0)
        worker.run(keep_running=False)

        request.wfile.seek(0)
        assert request.shutdown_called

    def test_whois_request_worker_write_error(self, create_worker, caplog):
        worker, request = create_worker
        request.rfile.write(b"!!\n!v\n")
        request.rfile.seek(0)
        # Write errors are usually due to the connection being
        # dropped, and should cause the connection to be closed
        # from our end.
        request.sendall = Mock(side_effect=socket.error("expected"))
        worker.run(keep_running=False)

    def test_whois_request_worker_access_list_permitted(self, config_override, create_worker):
        config_override(
            {
                "redis_url": "redis://invalid-host.example.com",  # Not actually used
                "server": {
                    "whois": {
                        "access_list": "test-access-list",
                    },
                },
                "access_lists": {
                    "test-access-list": ["192.0.2.0/25"],
                },
            }
        )

        worker, request = create_worker
        request.rfile.write(b"!q\n")
        request.rfile.seek(0)
        worker.run(keep_running=False)

        request.wfile.seek(0)
        assert not request.wfile.read()

    def test_whois_request_worker_access_list_denied(self, config_override, create_worker):
        config_override(
            {
                "redis_url": "redis://invalid-host.example.com",  # Not actually used
                "server": {
                    "whois": {
                        "access_list": "test-access-list",
                    },
                },
                "access_lists": {
                    "test-access-list": ["192.0.2.128/25"],
                },
            }
        )

        worker, request = create_worker
        request.rfile.write(b"!v\n")
        request.rfile.seek(0)
        worker.run(keep_running=False)

        assert worker.client_str == "192.0.2.1:99999"
        request.wfile.seek(0)
        assert request.wfile.read() == b"%% Access denied"
