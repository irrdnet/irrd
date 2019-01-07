import logging
from twisted.internet import threads
from twisted.internet.protocol import Factory, connectionDone
from twisted.protocols.basic import LineOnlyReceiver
from twisted.protocols.policies import TimeoutMixin

from irrd.conf import get_setting
from .query_parser import WhoisQueryParser
from ..access_check import is_client_permitted

logger = logging.getLogger(__name__)


class WhoisQueryReceiver(TimeoutMixin, LineOnlyReceiver):
    delimiter = b'\n'
    time_out = 30

    def connectionMade(self):  # noqa: N802
        peer = self.transport.getPeer()

        if not self.is_client_permitted(peer):
            self.transport.write(b'%% Access denied')
            self.transport.loseConnection()
            return

        self.peer_str = f"[{peer.host}]:{peer.port}"

        self.query_parser = WhoisQueryParser(peer, self.peer_str)
        self.setTimeout(self.time_out)
        logger.debug(f'{self.peer_str}: new connection opened')

    def lineReceived(self, line_bytes: bytes):  # noqa: N802
        self.resetTimeout()
        line = line_bytes.decode('utf-8', errors='backslashreplace').strip()

        if not line:
            return

        logger.info(f'{self.peer_str}: received query: {line}')

        if line.upper() == '!Q':
            self.transport.loseConnection()
            logger.debug(f'{self.peer_str}: closed connection per request')
            return

        threads.deferToThread(self.query_parser.handle_query, query=line).addCallback(self.returnResult)

    def returnResult(self, response_obj):  # noqa: N802
        response = response_obj.generate_response()
        self.transport.write(response.encode('utf-8'))

        if not self.query_parser.multiple_command_mode:
            self.transport.loseConnection()
            logger.debug(f'{self.peer_str}: auto-closed connection')

    def connectionLost(self, reason=connectionDone):  # noqa: N802
        self.factory.current_connections -= 1

    def is_client_permitted(self, peer):
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
