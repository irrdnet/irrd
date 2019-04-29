import logging
from twisted.internet import reactor
from twisted.internet.protocol import Factory, connectionDone
from twisted.protocols.basic import LineOnlyReceiver
from twisted.protocols.policies import TimeoutMixin

from irrd.conf import get_setting
from .query_parser import WhoisQueryParser
from .query_pipeline import QueryPipelineThread
from ..access_check import is_client_permitted

logger = logging.getLogger(__name__)


class WhoisQueryReceiver(TimeoutMixin, LineOnlyReceiver):
    """
    The query receiver is created once for each TCP connection.

    It handles interaction with the socket, and passes most work
    off to a query pipeline thread.
    """
    delimiter = b'\n'

    def connectionMade(self) -> None:  # noqa: N802
        """
        Handle a new connection. This includes
        - Access checks
        - Creating a query parser.
        - Creating a query pipeline thread and starting the thread.
        """
        peer = self.transport.getPeer()

        if not self.is_client_permitted(peer):
            self.transport.write(b'%% Access denied')
            self.transport.loseConnection()
            return

        # disable nagle
        self.transport.setTcpNoDelay(True)

        self.peer_str = f'[{peer.host}]:{peer.port}'

        self.query_parser = WhoisQueryParser(peer, self.peer_str)
        self.query_pipeline_thread = QueryPipelineThread(
            peer_str=self.peer_str,
            query_parser=self.query_parser,
            response_callback=self.query_response_callback,
            lose_connection_callback=self.lose_connection_callback,
        )
        self.query_pipeline_thread.start()

        self.setTimeout(self.query_parser.timeout)
        logger.debug(f'{self.peer_str}: new connection opened')

    def lineReceived(self, line_bytes: bytes) -> None:  # noqa: N802
        """
        Handle a line sent by a user. This method is kept as light
        as possible, to off-load most work to the pipeline thread.
        """
        self.resetTimeout()
        self.query_pipeline_thread.add_query(line_bytes)

    def query_response_callback(self, response: bytes) -> None:
        """
        Handle a response to a query, sent by the query pipeline thread.
        This is a small thread-safe wrapping around return_response()
        """
        reactor.callFromThread(self.return_response, response)

    def return_response(self, response: bytes) -> None:
        """
        Process a response. This means sending the response, closing the
        connection if needed, and telling the query pipeline thread
        sending the response completed.
        """
        self.transport.write(response)

        if not self.query_parser.multiple_command_mode:
            self.transport.loseConnection()
            logger.debug(f'{self.peer_str}: auto-closed connection')

        self.setTimeout(self.query_parser.timeout)

        self.query_pipeline_thread.ready_for_next_result()

    def lose_connection_callback(self) -> None:
        """
        Handle a !q query, as detected by the query pipeline thread.
        This is a small thread-safe wrapping around transport.loseConnection()
        """
        reactor.callFromThread(self.transport.loseConnection)

    def connectionLost(self, reason=connectionDone) -> None:  # noqa: N802
        """
        Handle a lost connection, either because transport.loseConnection()
        was called, or the remote side closed it.
        Cancels the pipeline thread, causing it to terminate within two
        seconds.
        """
        self.factory.current_connections -= 1
        self.query_pipeline_thread.cancel()

    def timeoutConnection(self) -> None:  # noqa: N802
        """
        Triggered when the configured timeout occurs. Ignored if queries are
        still running or queued, otherwise the connection is closed.
        """
        if not self.query_pipeline_thread.is_processing_queries():
            self.transport.loseConnection()

    def is_client_permitted(self, peer) -> bool:
        """
        Check whether a client is permitted.
        """
        return is_client_permitted(peer, 'server.whois.access_list', default_deny=False)


class WhoisQueryReceiverFactory(Factory):
    protocol = WhoisQueryReceiver

    def __init__(self):
        self.current_connections = 0
        self.max_connections = get_setting('server.whois.max_connections')

    def buildProtocol(self, addr):  # noqa: N802
        if self.current_connections >= self.max_connections:
            return None
        self.current_connections += 1
        protocol = self.protocol()
        protocol.factory = self
        return protocol
