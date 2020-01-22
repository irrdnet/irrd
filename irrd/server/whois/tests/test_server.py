import time

import pytest
from io import BytesIO
from unittest.mock import Mock

from ..server import WhoisRequestHandler


class MockServer:
    def __init__(self):
        self.shutdown_called = False

    def shutdown_request(self, request):
        self.shutdown_called = True


@pytest.fixture()
def create_handler(config_override):
    config_override({
        'redis_url': 'redis://invalid-host.example.com',  # Not actually used
    })
    handler = WhoisRequestHandler.__new__(WhoisRequestHandler)
    handler.client_address = ('192.0.2.1', 99999)
    handler.rfile = BytesIO()
    handler.wfile = BytesIO()
    handler.request = Mock()
    handler.server = MockServer()
    yield handler


class TestWhoisRequestHandler:
    def test_whois_request_handler_no_access_list(self, create_handler):
        handler = create_handler
        # Empty query in first line should be ignored.
        handler.rfile.write(b' \n!v\r\n')
        handler.rfile.seek(0)
        handler.handle()

        assert handler.client_str == '192.0.2.1:99999'
        handler.wfile.seek(0)
        assert b'IRRd -- version' in handler.wfile.read()
        assert not handler.server.shutdown_called

    def test_whois_request_handler_timeout(self, create_handler):
        handler = create_handler

        handler.rfile = Mock()
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
                return b'!!\n'
            if readline_call_count == 2:
                return b'!t1\n'
            if readline_call_count == 3:
                time.sleep(2)
                return b''
        handler.rfile.readline = mock_readline

        handler.rfile.seek(0)
        handler.handle()

        handler.wfile.seek(0)
        assert handler.server.shutdown_called

    def test_whois_request_handler_write_error(self, create_handler, caplog):
        handler = create_handler
        handler.rfile.write(b'!!\n!v\n')
        handler.rfile.seek(0)
        # Write errors are usually due to the connection being
        # dropped, and should cause the connection to be closed
        # from our end.
        handler.wfile.write = Mock(side_effect=OSError('expected'))
        handler.handle()

    def test_whois_request_handler_access_list_permitted(self, config_override, create_handler):
        config_override({
            'redis_url': 'redis://invalid-host.example.com',  # Not actually used
            'server': {
                'whois': {
                    'access_list': 'test-access-list',
                },
            },
            'access_lists': {
                'test-access-list': ['192.0.2.0/25'],
            },
        })

        handler = create_handler
        handler.rfile.write(b'!q\n')
        handler.rfile.seek(0)
        handler.handle()

        handler.wfile.seek(0)
        assert not handler.wfile.read()

    def test_whois_request_handler_access_list_denied(self, config_override, create_handler):
        config_override({
            'redis_url': 'redis://invalid-host.example.com',  # Not actually used
            'server': {
                'whois': {
                    'access_list': 'test-access-list',
                },
            },
            'access_lists': {
                'test-access-list': ['192.0.2.0/25'],
            },
        })

        handler = create_handler
        handler.client_address = ('192.0.2.200', 99999)
        handler.rfile.write(b'!v\n')
        handler.rfile.seek(0)
        handler.handle()

        assert handler.client_str == '192.0.2.200:99999'
        handler.wfile.seek(0)
        assert handler.wfile.read() == b'%% Access denied'
