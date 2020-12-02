from starlette.endpoints import HTTPEndpoint
from starlette.responses import PlainTextResponse

from irrd.server.access_check import is_client_permitted
from .status_generator import StatusGenerator


class StatusEndpoint(HTTPEndpoint):
    def get(self, request):
        if not is_client_permitted(request.client.host, 'server.http.status_access_list'):
            return PlainTextResponse('Access denied', status_code=403)

        response = StatusGenerator().generate_status()
        return PlainTextResponse(response)
