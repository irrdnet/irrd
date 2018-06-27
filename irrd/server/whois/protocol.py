import logging

from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineOnlyReceiver

from .query_parser import WhoisQueryParser

logger = logging.getLogger(__name__)


class WhoisQueryReceiver(LineOnlyReceiver):
    delimiter = b'\n'

    def connectionMade(self):  # noqa: N802
        peer = self.transport.getPeer()
        self.peer = f"[{peer.host}]:{peer.port}"
        self.query_parser = WhoisQueryParser(self.peer)
        logger.info(f'{self.peer}: new connection opened')

    def lineReceived(self, line_bytes: bytes):  # noqa: N802
        line = line_bytes.decode('utf-8').strip()

        if not line:
            return

        logger.debug(f'{self.peer}: received query: {line}')

        if line.upper() == '!Q':
            self.transport.loseConnection()
            logger.debug(f'{self.peer}: closed connection per request')
            return

        response = self.query_parser.handle_query(line).generate_response()
        self.transport.write(response.encode('utf-8'))

        if not self.query_parser.multiple_command_mode:
            self.transport.loseConnection()
            logger.debug(f'{self.peer}: auto-closed connection')


class WhoisQueryReceiverFactory(Factory):
    protocol = WhoisQueryReceiver
