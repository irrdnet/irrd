import logging
from twisted.web import server, resource

from .request_handlers import DatabaseStatusRequest
from ..access_check import is_client_permitted

logger = logging.getLogger(__name__)


class DatabaseStatusResource(resource.Resource):
    """
    A twisted HTTP server resource for the status of the database.
    """
    isLeaf = True  # noqa: N815

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
        return is_client_permitted(request.getClientAddress(), 'server.http.access_list')


root = resource.Resource()
v1 = resource.Resource()
root.putChild(b'v1', v1)
v1.putChild(b'status', DatabaseStatusResource())

http_site = server.Site(root)
http_site.displayTracebacks = False
