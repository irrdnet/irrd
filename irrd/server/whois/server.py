import time

import logging
import os
import signal
import socket
import socketserver
import threading
from setproctitle import setproctitle

from irrd.conf import get_setting
from irrd.server.access_check import is_client_permitted
from irrd.server.whois.query_parser import WhoisQueryParser

logger = logging.getLogger(__name__)


# Covered by integration tests
def start_whois_server():  # pragma: no cover
    """
    Start the whois server, listening forever.
    This function does not return, except after SIGTERM is received.
    """
    setproctitle('irrd-whois-server-listener')
    address = (get_setting('server.whois.interface'), get_setting('server.whois.port'))
    logger.info(f'Starting whois server on TCP {address}')
    server = WhoisConnectionLimitedForkingTCPServer(
        server_address=address,
        RequestHandlerClass=WhoisRequestHandler,
    )

    # When this process receives SIGTERM, shut down the server cleanly.
    def sigterm_handler(signum, frame):
        nonlocal server

        def shutdown(server):
            server.shutdown()
            server.server_close()
        # Shutdown must be called from a thread to prevent blocking.
        threading.Thread(target=shutdown, args=(server,)).start()
    signal.signal(signal.SIGTERM, sigterm_handler)

    server.serve_forever()


class WhoisConnectionLimitedForkingTCPServer(socketserver.ForkingMixIn, socketserver.TCPServer):  # pragma: no cover
    """
    Server for whois queries.
    Includes a connection limit and a cleaner shutdown process than included by default.
    """
    address_family = socket.AF_INET6
    allow_reuse_address = True
    request_queue_size = 50

    def verify_request(self, request, client_address):
        active_children = len(self.active_children) if self.active_children else 0
        return active_children < int(get_setting('server.whois.max_connections'))

    def handle_error(self, request, client_address):
        logger.error(f'Error while handling request from {client_address}', exc_info=True)

    def shutdown(self):
        """
        Shut down the server, by killing all child processes,
        and then deferring to built-in TCPServer shutdown.
        """
        if self.active_children:
            for pid in self.active_children:
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:  # pragma: no cover
                    pass
        return super().shutdown()


class WhoisRequestHandler(socketserver.StreamRequestHandler):
    def handle(self):
        """
        Handle a whois connection.
        Upon return, the connection is closed by StreamRequestHandler.
        """
        # Disable the special sigterm_handler defined in start_whois_server()
        # (signal handlers are inherited)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

        client_ip = self.client_address[0]
        self.client_str = client_ip + ':' + str(self.client_address[1])
        setproctitle(f'irrd-whois-server-{self.client_str}')

        if not self.is_client_permitted(client_ip):
            self.wfile.write(b'%% Access denied')
            return

        self.query_parser = WhoisQueryParser(client_ip, self.client_str)

        data = True
        while data:
            timer = threading.Timer(self.query_parser.timeout, self.server.shutdown_request, args=[self.request])
            timer.start()
            data = self.rfile.readline()

            timer.cancel()

            query = data.decode('utf-8', errors='backslashreplace').strip()
            if not query:
                continue

            logger.info(f'{self.client_str}: processing query: {query}')

            if not self.handle_query(query):
                return

    def handle_query(self, query: str) -> bool:
        """
        Handle an individual query.
        Returns False when the connection should be closed,
        True when more queries should be read.
        """
        start_time = time.perf_counter()
        if query.upper() == '!Q':
            logger.debug(f'{self.client_str}: closed connection per request')
            return False

        response = self.query_parser.handle_query(query)
        response_bytes = response.generate_response().encode('utf-8')
        try:
            self.wfile.write(response_bytes)
        except OSError:
            return False

        elapsed = time.perf_counter() - start_time
        logger.info(f'{self.client_str}: sent answer to query, elapsed {elapsed}s, {len(response_bytes)} bytes: {query}')

        if not self.query_parser.multiple_command_mode:
            logger.debug(f'{self.client_str}: auto-closed connection')
            return False
        return True

    def is_client_permitted(self, ip: str) -> bool:
        """
        Check whether a client is permitted.
        """
        return is_client_permitted(ip, 'server.whois.access_list', default_deny=False)
