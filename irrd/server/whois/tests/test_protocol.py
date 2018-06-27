from unittest.mock import Mock

from twisted.internet.address import IPv4Address

from ..protocol import WhoisQueryReceiver


def test_whois_protocol():
    # Note that these tests do not mock WhoisQueryParser, on purpose.
    # However, they only run version queries, so no database interaction occurs.
    mock_transport = Mock()
    mock_transport.getPeer = lambda: IPv4Address('TCP', '127.0.0.1', 99999)

    receiver = WhoisQueryReceiver()
    receiver.transport = mock_transport

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
    expected_output_start = b'A24\nIRRD4'
    assert mock_transport.mock_calls[0][1][0][:len(expected_output_start)] == expected_output_start
    assert mock_transport.mock_calls[1][0] == 'loseConnection'
    assert len(mock_transport.mock_calls) == 2
    mock_transport.reset_mock()

    receiver.query_parser.multiple_command_mode = True
    receiver.lineReceived(b' !v ')
    assert mock_transport.mock_calls[0][0] == 'write'
    assert len(mock_transport.mock_calls) == 1
