import time

import logging
import signal
import socket
import socketserver
import threading

from IPy import IP
from setproctitle import setproctitle

import multiprocessing as mp
from irrd.conf import get_setting
from irrd.server.access_check import is_client_permitted
from irrd.server.whois.query_parser import WhoisQueryParser
from irrd.storage.database_handler import DatabaseHandler

logger = logging.getLogger(__name__)
mp.allow_connection_pickling()


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
    )

    # When this process receives SIGTERM, shut down the server cleanly.
    def sigterm_handler(signum, frame):
        nonlocal server

        def shutdown(server):
            logging.info('Whois server shutting down')
            server.shutdown()
            server.server_close()
        # Shutdown must be called from a thread to prevent blocking.
        threading.Thread(target=shutdown, args=(server,)).start()
    signal.signal(signal.SIGTERM, sigterm_handler)

    server.serve_forever()


class WhoisConnectionLimitedForkingTCPServer(socketserver.TCPServer):  # pragma: no cover
    """
    Server for whois queries.
    Includes a connection limit and a cleaner shutdown process than included by default.
    """
    allow_reuse_address = True
    request_queue_size = 50

    def __init__(self, server_address, bind_and_activate=True):  # noqa: N803
        self.address_family = socket.AF_INET6 if IP(server_address[0]).version() == 6 else socket.AF_INET
        super().__init__(server_address, None, bind_and_activate)

        self.connection_queue = mp.Queue()
        self.workers = []
        # for i in range(int(get_setting('server.whois.max_connections'))):
        if True:
            worker = WhoisWorker(self.connection_queue)
            worker.start()
            self.workers.append(worker)

    def process_request(self, request, client_address):
        self.connection_queue.put((request, client_address))

    def handle_error(self, request, client_address):
        logger.error(f'Error while handling request from {client_address}', exc_info=True)

    def shutdown(self):
        """
        Shut down the server, by killing all child processes,
        and then deferring to built-in TCPServer shutdown.
        """
        for worker in self.workers:
            try:
                worker.terminate()
                worker.join()
            except Exception:  # pragma: no cover
                pass
        return super().shutdown()


class WhoisWorker(mp.Process, socketserver.StreamRequestHandler):  # TODO: exception logging
    def __init__(self, queue, *args, **kwargs):
        self.queue = queue
        super().__init__(*args, **kwargs)

    def run(self) -> None:
        # Disable the special sigterm_handler defined in start_whois_server()
        # (signal handlers are inherited)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

        DatabaseHandler()  # Initialise the connection pool

        while True:
            setproctitle('irrd-whois-worker')
            self.request, self.client_address = self.queue.get()
            self.setup()
            self.handle_connection()
            self.close_request()

    def close_request(self):
        self.finish()
        # Close the connection in the same way normally done by TCPServer
        try:
            # explicitly shutdown.  socket.close() merely releases
            # the socket and waits for GC to perform the actual close.
            self.request.shutdown(socket.SHUT_WR)
        except OSError:
            pass  # some platforms may raise ENOTCONN here
        self.request.close()

    def handle_connection(self):
        start_time = time.perf_counter()

        client_ip = self.client_address[0]
        self.client_str = client_ip + ':' + str(self.client_address[1])
        setproctitle(f'irrd-whois-worker-{self.client_str}')

        if not self.is_client_permitted(client_ip):
            self.wfile.write(b'%% Access denied')
            return

        self.query_parser = WhoisQueryParser(client_ip, self.client_str)

        data = True
        elapsed = time.perf_counter() - start_time
        logger.info(f'{self.client_str}: ready to read queries {elapsed}s')

        while data:
            timer = threading.Timer(self.query_parser.timeout, self.close_request)
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
        logger.info(f'{self.client_str}: sent answer to query, elapsed {elapsed}s, '
                    f'{len(response_bytes)} bytes: {query}')

        if not self.query_parser.multiple_command_mode:
            logger.debug(f'{self.client_str}: auto-closed connection')
            return False
        return True

    def is_client_permitted(self, ip: str) -> bool:
        """
        Check whether a client is permitted.
        """
        return is_client_permitted(ip, 'server.whois.access_list', default_deny=False)
