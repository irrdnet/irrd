import logging

from IPy import IP
from twisted.web import server, resource

from irrd.conf import get_setting
from .request_handlers import DatabaseStatusRequest

logger = logging.getLogger(__name__)


class DatabaseStatusResource(resource.Resource):
    """
    A twisted HTTP server resource for the status of the database.
    """
    isLeaf = True

    def render_GET(self, request: server.Request):  # noqa: N802
        """Render the database status in plain text."""
        if not self.is_client_permitted(request):
            request.setResponseCode(403)
            return b'Access denied'

        result_txt = DatabaseStatusRequest().generate_status()
        request.setHeader(b'Content-Type', b'text/plain; charset=utf-8')
        return result_txt.encode('utf-8')

    def is_client_permitted(self, request) -> bool:
        """
        Determine whether a client is permitted to access this interface,
        based on the server.http.access_list setting.
        """
        try:
            client_ip = IP(request.getClientAddress().host)
        except (ValueError, AttributeError) as e:
            logger.error(f'Rejecting request as HTTP client IP could not be read from '
                         f'{request.getClientAddress()}: {e}')
            return False

        access_list_name = get_setting('server.http.access_list')
        access_list = get_setting(f'access_lists.{access_list_name}')
        if not access_list:
            logger.info(f'Rejecting HTTP request, access list empty or undefined: {client_ip}')
            return False

        allowed = any([client_ip in IP(allowed) for allowed in access_list])
        if not allowed:
            logger.info(f'Rejecting HTTP request, IP not in access list: {client_ip}')
        return allowed


root = resource.Resource()
v1 = resource.Resource()
root.putChild(b'v1', v1)
v1.putChild(b'status', DatabaseStatusResource())

http_site = server.Site(root)
http_site.displayTracebacks = False
