from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from irrd.server.access_check import is_client_permitted
from .status_generator import StatusGenerator
from ..whois.query_parser import WhoisQueryParser
from ..whois.query_response import WhoisQueryResponseType


class StatusEndpoint(HTTPEndpoint):
    def get(self, request: Request) -> Response:
        if not is_client_permitted(request.client.host, 'server.http.status_access_list'):
            return PlainTextResponse('Access denied', status_code=403)

        response = StatusGenerator().generate_status()
        return PlainTextResponse(response)


class WhoisQueryEndpoint(HTTPEndpoint):
    def get(self, request: Request) -> Response:
        if 'q' not in request.query_params:
            return PlainTextResponse('Missing required query parameter "q"', status_code=400)
        parser = WhoisQueryParser(
            request.client.host,
            request.client.host + ':' + str(request.client.port),
            request.app.state.preloader,
            request.app.state.database_handler
        )
        response = parser.handle_query(request.query_params['q'])
        response.clean_response()

        if response.response_type == WhoisQueryResponseType.ERROR_INTERNAL:
            return PlainTextResponse(response.result, status_code=500)
        if response.response_type == WhoisQueryResponseType.ERROR_USER:
            return PlainTextResponse(response.result, status_code=400)
        if response.result:
            return PlainTextResponse(response.result)
        else:
            return Response(status_code=204)
