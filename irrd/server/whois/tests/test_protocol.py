from unittest.mock import Mock

from twisted.internet.address import IPv4Address

from ..protocol import WhoisQueryReceiver, WhoisQueryReceiverFactory


def test_whois_protocol():
    # Note that these tests do not mock WhoisQueryParser, on purpose.
    # However, they only run version queries, so no database interaction occurs.
    mock_transport = Mock()
    mock_transport.getPeer = lambda: IPv4Address('TCP', '127.0.0.1', 99999)
    mock_factory = Mock()
    mock_factory.current_connections = 10

    receiver = WhoisQueryReceiver()
    receiver.transport = mock_transport
    receiver.factory = mock_factory

    receiver.connectionMade()
    assert receiver.peer == '[127.0.0.1]:99999'
    mock_transport.reset_mock()

    receiver.lineReceived(b' ')
    receiver.lineReceived(b' !q ')
    assert mock_transport.mock_calls[0][0] == 'loseConnection'
    assert len(mock_transport.mock_calls) == 1
    mock_transport.reset_mock()

    receiver.lineReceived(b' !v ')
    assert mock_transport.mock_calls[0][0] == 'write'
    expected_output_start = b'A23\nIRRD'
    assert mock_transport.mock_calls[0][1][0][:len(expected_output_start)] == expected_output_start
    assert mock_transport.mock_calls[1][0] == 'loseConnection'
    assert len(mock_transport.mock_calls) == 2
    mock_transport.reset_mock()

    receiver.query_parser.multiple_command_mode = True
    receiver.lineReceived(b' !v ')
    assert mock_transport.mock_calls[0][0] == 'write'
    assert len(mock_transport.mock_calls) == 1

    receiver.connectionLost()
    assert mock_factory.current_connections == 9


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
