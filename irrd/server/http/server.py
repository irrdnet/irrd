import logging
import signal

from IPy import IP
from setproctitle import setproctitle
import socket

import socketserver
from http import HTTPStatus
# http.server is generally not recommended for production use,
# but as we only use small parts, this is not a significant concern
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Tuple

from irrd import __version__
from irrd.conf import get_setting
from irrd.server.access_check import is_client_permitted
from irrd.server.http.status_generator import StatusGenerator

logger = logging.getLogger(__name__)
HTTP_TIMEOUT = 30

# The start_http_server method and IRRdHTTPRequestHandler are
# difficult to test in a unit test, and therefore only included
# in integration tests. They should be kept as small as possible.


def start_http_server():  # pragma: no cover
    """
    Start the HTTP server, listening forever. This function does not return.
    """
    setproctitle('irrd-http-server-listener')
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    address = (get_setting('server.http.interface'), get_setting('server.http.port'))
    logger.info(f'Starting http server on TCP {address}')
    httpd = HTTPServerForkingIPv6(address, IRRdHTTPRequestHandler)
    httpd.serve_forever()


class HTTPServerForkingIPv6(socketserver.ThreadingMixIn, HTTPServer):  # pragma: no cover
    # Default HTTP server only supports IPv4
    allow_reuse_address = True
    timeout = HTTP_TIMEOUT

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):  # noqa: N803
        self.address_family = socket.AF_INET6 if IP(server_address[0]).version() == 6 else socket.AF_INET
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)

    def handle_error(self, request, client_address):
        logger.error(f'Error while handling request from {client_address}', exc_info=True)


class IRRdHTTPRequestHandler(BaseHTTPRequestHandler):  # pragma: no cover
    """
    Request handler, called for each HTTP request, in its own process.

    Kept as lightweight as possible, and offloads most work to
    IRRdHTTPRequestProcessor, as that class is unit-testable.
    """
    server_version = f'irrd/{__version__}'

    def handle_one_request(self) -> None:
        # Sockets for client connections don't inherit the timeout,
        # this wrapper sets it before any data is read.
        self.connection.settimeout(HTTP_TIMEOUT)
        return super().handle_one_request()

    def do_GET(self):  # noqa: N802
        processor = IRRdHTTPRequestProcessor(self.client_address[0], self.client_address[1])
        status, content = processor.handle_get(self.path)
        self.generate_response(status, content)

    def log_message(self, format, *args):
        logger.info('HTTP request served: %s: %s' % (self.address_string(), format % args))

    def generate_response(self, response_status, content):
        content_bytes = content.encode('utf-8')
        self.send_response(response_status)
        self.send_header('Content-type', 'text/plain;charset=utf-8')
        self.send_header('Content-Length', len(content_bytes))
        self.end_headers()
        self.wfile.write(content_bytes)


class IRRdHTTPRequestProcessor:
    """
    Request processor for HTTP queries.
    Split from IRRdHTTPRequestHandler for easier testing.
    """
    def __init__(self, client_ip: str, client_port: int):
        self.client_ip = client_ip
        self.client_str = client_ip + ':' + str(client_port)

    def handle_get(self, path) -> Tuple[HTTPStatus, str]:
        if not is_client_permitted(self.client_ip, 'server.http.access_list'):
            return HTTPStatus.FORBIDDEN, 'Access denied'

        if path.rstrip('/') != '/v1/status':
            return HTTPStatus.NOT_FOUND, 'Not found'

        content = StatusGenerator().generate_status()
        return HTTPStatus.OK, content
