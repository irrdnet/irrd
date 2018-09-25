import logging

from twisted.web import server, resource

from .request_handlers import DatabaseStatusRequest

logger = logging.getLogger(__name__)


class DatabaseStatusResource(resource.Resource):
    """
    A twisted HTTP server resource for the status of the database.
    """
    isLeaf = True

    def render_GET(self, request):  # noqa: N802
        """Render the database status in plain text."""
        result_txt = DatabaseStatusRequest().generate_status()
        request.setHeader("Content-Type", "text/plain; charset=utf-8")
        return result_txt.encode('utf-8')


root = resource.Resource()
v1 = resource.Resource()
root.putChild(b'v1', v1)
v1.putChild(b'status', DatabaseStatusResource())

http_site = server.Site(root)
http_site.displayTracebacks = False
