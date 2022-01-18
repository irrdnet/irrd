import logging
import multiprocessing as mp
import os
import signal
import socket
import socketserver
import threading
import time

from IPy import IP
from daemon.daemon import change_process_owner
from setproctitle import setproctitle

from irrd import ENV_MAIN_PROCESS_PID
from irrd.conf import SOCKET_DEFAULT_TIMEOUT, get_setting
from irrd.server.access_check import is_client_permitted
from irrd.server.whois.query_parser import WhoisQueryParser
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.preload import Preloader
from irrd.utils.process_support import memory_trim

logger = logging.getLogger(__name__)
mp.allow_connection_pickling()


# Covered by integration tests
def start_whois_server(uid, gid):  # pragma: no cover
    """
    Start the whois server, listening forever.
    This function does not return, except after SIGTERM is received.
    """
    setproctitle('irrd-whois-server-listener')
    address = (get_setting('server.whois.interface'), get_setting('server.whois.port'))
    logger.info(f'Starting whois server on TCP {address}')
    server = WhoisTCPServer(
        server_address=address,
        uid=uid,
        gid=gid,
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


class WhoisTCPServer(socketserver.TCPServer):  # pragma: no cover
    """
    Server for whois queries.

    Starts a number of worker processes that handle the client connections.
    Whenever a client is connected, the connection is pushed onto a queue,
    from which a worker picks it up. The workers are responsible for the
    connection from then on.
    """
    allow_reuse_address = True
    request_queue_size = 50

    def __init__(self, server_address, uid, gid, bind_and_activate=True):  # noqa: N803
        self.address_family = socket.AF_INET6 if IP(server_address[0]).version() == 6 else socket.AF_INET
        super().__init__(server_address, None, bind_and_activate)
        if uid and gid:
            change_process_owner(uid=uid, gid=gid, initgroups=True)

        self.connection_queue = mp.Queue()
        self.workers = []
        for i in range(int(get_setting('server.whois.max_connections'))):
            worker = WhoisWorker(self.connection_queue)
            worker.start()
            self.workers.append(worker)

    def process_request(self, request, client_address):
        """Push the client connection onto the queue for further handling."""
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


class WhoisWorker(mp.Process, socketserver.StreamRequestHandler):
    """
    A whois worker is a process that handles whois client connections,
    which are retrieved from a queue. After handling a connection,
    the process waits for the next connection from the queue.s
    """
    def __init__(self, connection_queue, *args, **kwargs):
        self.connection_queue = connection_queue
        # Note that StreamRequestHandler.__init__ is not called - the
        # input for that is not available, as it's retrieved from the queue.
        super().__init__(*args, **kwargs)

    def run(self, keep_running=True) -> None:
        """
        Whois worker run loop.
        This method does not return, except if it failed to initialise a preloader,
        or if keep_running is False, after the first request is handled. The latter
        is used in the tests.
        """
        # Disable the special sigterm_handler defined in start_whois_server()
        # (signal handlers are inherited)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

        try:
            self.preloader = Preloader()
            self.database_handler = DatabaseHandler(readonly=True)
        except Exception as e:
            logger.critical(f'Whois worker failed to initialise preloader or database, '
                            f'unable to start, terminating IRRd, traceback follows: {e}',
                            exc_info=e)
            main_pid = os.getenv(ENV_MAIN_PROCESS_PID)
            if main_pid:  # pragma: no cover
                os.kill(int(main_pid), signal.SIGTERM)
            else:
                logger.error('Failed to terminate IRRd, unable to find main process PID')
            return

        while True:
            try:
                setproctitle('irrd-whois-worker')
                self.request, self.client_address = self.connection_queue.get()
                self.request.settimeout(SOCKET_DEFAULT_TIMEOUT)
                self.setup()
                self.handle_connection()
                self.finish()
                self.close_request()
                memory_trim()
            except Exception as e:
                try:
                    self.close_request()
                except Exception:  # pragma: no cover
                    pass
                logger.error(f'Failed to handle whois connection, traceback follows: {e}',
                             exc_info=e)
            if not keep_running:
                break

    def close_request(self):
        # Close the connection in the same way normally done by TCPServer
        try:
            # explicitly shutdown.  socket.close() merely releases
            # the socket and waits for GC to perform the actual close.
            self.request.shutdown(socket.SHUT_RDWR)
        except OSError:  # pragma: no cover
            pass  # some platforms may raise ENOTCONN here
        self.request.close()

    def handle_connection(self):
        """
        Handle an individual whois client connection.
        When this method returns, the connection is closed.
        """
        client_ip = self.client_address[0]
        self.client_str = client_ip + ':' + str(self.client_address[1])
        setproctitle(f'irrd-whois-worker-{self.client_str}')

        if not self.is_client_permitted(client_ip):
            self.wfile.write(b'%% Access denied')
            return

        self.query_parser = WhoisQueryParser(client_ip, self.client_str, self.preloader,
                                             self.database_handler)

        data = True
        while data:
            timer = threading.Timer(self.query_parser.timeout, self.close_request)
            timer.start()
            data = self.rfile.readline()
            timer.cancel()

            query = data.decode('utf-8', errors='backslashreplace').strip()
            if not query:
                continue

            logger.debug(f'{self.client_str}: processing query: {query}')

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
        logger.info(f'{self.client_str}: sent answer to query, elapsed {elapsed:.9f}s, '
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
