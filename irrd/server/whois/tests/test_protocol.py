import pytest
import queue
from twisted.internet.address import IPv4Address, UNIXAddress
from typing import Callable
from unittest.mock import Mock

from ..protocol import WhoisQueryReceiver, WhoisQueryReceiverFactory


class QueryPipelineMock:
    def __init__(self, peer_str: str, query_parser,
                 response_callback: Callable[[bytes], None], lose_connection_callback: Callable[[], None],
                 *args, **kwargs):
        self.peer_str = peer_str
        self.response_callback = response_callback
        self.lose_connection_callback = lose_connection_callback
        self.pipeline: queue.Queue[bytes] = queue.Queue()
        self.cancelled = False
        self.started = False
        self.ready_for_next_result_flag = False
        self.is_processing_queries_result = False

    def start(self):
        self.started = True

    def add_query(self, query):
        self.pipeline.put(query, block=False)

    def cancel(self):
        self.cancelled = True

    def ready_for_next_result(self):
        self.ready_for_next_result_flag = True

    def is_processing_queries(self):
        return self.is_processing_queries_result


@pytest.fixture()
def mock_pipeline_reactor(monkeypatch):
    def _call_from_thread_mock(callable, *args, **kwargs):
        return callable(*args, **kwargs)

    monkeypatch.setattr('irrd.server.whois.protocol.reactor.callFromThread', _call_from_thread_mock)
    monkeypatch.setattr('irrd.server.whois.protocol.QueryPipelineThread', QueryPipelineMock)


class TestWhoisProtocol:

    def test_whois_protocol_no_access_list(self, config_override, mock_pipeline_reactor):
        config_override({
            'sources': {'TEST1': {}},
        })

        mock_transport = Mock()
        mock_transport.getPeer = lambda: IPv4Address('TCP', '127.0.0.1', 99999)
        mock_factory = Mock()
        mock_factory.current_connections = 10

        receiver = WhoisQueryReceiver()
        receiver.transport = mock_transport
        receiver.factory = mock_factory

        receiver.connectionMade()
        assert receiver.peer_str == '[127.0.0.1]:99999'
        assert receiver.query_pipeline_thread.started
        assert receiver.timeOut == receiver.query_parser.timeout
        mock_transport.reset_mock()

        receiver.lineReceived(b' ')
        receiver.lineReceived(b' !v ')

        assert receiver.query_pipeline_thread.pipeline.get(block=False) == b' '
        assert receiver.query_pipeline_thread.pipeline.get(block=False) == b' !v '

        receiver.query_parser.timeout = 5
        receiver.query_pipeline_thread.response_callback(b'response')
        assert mock_transport.mock_calls[0][0] == 'write'
        assert mock_transport.mock_calls[0][1][0] == b'response'
        assert mock_transport.mock_calls[1][0] == 'loseConnection'
        assert len(mock_transport.mock_calls) == 2
        assert receiver.timeOut == receiver.query_parser.timeout
        mock_transport.reset_mock()

        receiver.query_pipeline_thread.lose_connection_callback()
        assert mock_transport.mock_calls[0][0] == 'loseConnection'
        assert len(mock_transport.mock_calls) == 1
        mock_transport.reset_mock()

        receiver.query_parser.multiple_command_mode = True
        receiver.query_pipeline_thread.response_callback(b'response')
        assert mock_transport.mock_calls[0][0] == 'write'
        assert len(mock_transport.mock_calls) == 1
        mock_transport.reset_mock()

        receiver.connectionLost()
        assert mock_factory.current_connections == 9

        receiver.timeoutConnection()
        assert mock_transport.mock_calls[0][0] == 'loseConnection'
        assert len(mock_transport.mock_calls) == 1
        mock_transport.reset_mock()

        receiver.query_pipeline_thread.is_processing_queries_result = True
        receiver.timeoutConnection()
        assert not len(mock_transport.mock_calls)

    def test_whois_protocol_access_list_permitted(self, config_override, mock_pipeline_reactor):
        config_override({
            'sources': {'TEST1': {}},
            'server': {
                'whois': {
                    'access_list': 'test-access-list',
                },
            },
            'access_lists': {
                'test-access-list': ['192.0.2.0/25'],
            },
        })

        mock_transport = Mock()
        mock_transport.getPeer = lambda: IPv4Address('TCP', '192.0.2.1', 99999)
        mock_factory = Mock()
        mock_factory.current_connections = 10

        receiver = WhoisQueryReceiver()
        receiver.transport = mock_transport
        receiver.factory = mock_factory

        receiver.connectionMade()
        assert len(mock_transport.mock_calls) == 0

    def test_whois_protocol_access_list_denied(self, config_override):
        config_override({
            'sources': {'TEST1': {}},
            'server': {
                'whois': {
                    'access_list': 'test-access-list',
                },
            },
            'access_lists': {
                'test-access-list': ['192.0.2.0/25'],
            },
        })

        mock_transport = Mock()
        mock_transport.getPeer = lambda: IPv4Address('TCP', '192.0.2.129', 99999)
        mock_factory = Mock()
        mock_factory.current_connections = 10

        receiver = WhoisQueryReceiver()
        receiver.transport = mock_transport
        receiver.factory = mock_factory

        receiver.connectionMade()
        assert mock_transport.mock_calls[0][0] == 'write'
        expected_output_start = b'%% Access denied'
        assert mock_transport.mock_calls[0][1][0][:len(expected_output_start)] == expected_output_start
        assert mock_transport.mock_calls[1][0] == 'loseConnection'
        assert len(mock_transport.mock_calls) == 2

    def test_whois_protocol_access_list_denied_unknown_client_address(self, config_override):
        config_override({
            'sources': {'TEST1': {}},
            'server': {
                'whois': {
                    'access_list': 'test-access-list',
                },
            },
            'access_lists': {
                'test-access-list': ['192.0.2.0/25'],
            },
        })

        mock_transport = Mock()
        mock_transport.getPeer = lambda: UNIXAddress(b'not-supported')
        mock_factory = Mock()
        mock_factory.current_connections = 10

        receiver = WhoisQueryReceiver()
        receiver.transport = mock_transport
        receiver.factory = mock_factory

        receiver.connectionMade()
        assert mock_transport.mock_calls[0][0] == 'write'
        expected_output_start = b'%% Access denied'
        assert mock_transport.mock_calls[0][1][0][:len(expected_output_start)] == expected_output_start
        assert mock_transport.mock_calls[1][0] == 'loseConnection'
        assert len(mock_transport.mock_calls) == 2


def test_whois_receiver_factory():
    factory = WhoisQueryReceiverFactory()
    factory.max_connections = 2

    result = factory.buildProtocol(IPv4Address('TCP', '127.0.0.1', 99999))
    assert result is not None
    assert factory.current_connections == 1

    factory.buildProtocol(IPv4Address('TCP', '127.0.0.1', 99999))
    assert result is not None
    assert factory.current_connections == 2

    result = factory.buildProtocol(IPv4Address('TCP', '127.0.0.1', 99999))
    assert result is None
    assert factory.current_connections == 2
