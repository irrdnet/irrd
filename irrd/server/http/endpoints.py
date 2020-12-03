import logging
import time

from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from irrd.server.access_check import is_client_permitted
from .status_generator import StatusGenerator
from ..whois.query_parser import WhoisQueryParser
from ..whois.query_response import WhoisQueryResponseType

logger = logging.getLogger(__name__)


class StatusEndpoint(HTTPEndpoint):
    def get(self, request: Request) -> Response:
        if not is_client_permitted(request.client.host, 'server.http.status_access_list'):
            return PlainTextResponse('Access denied', status_code=403)

        response = StatusGenerator().generate_status()
        return PlainTextResponse(response)


class WhoisQueryEndpoint(HTTPEndpoint):
    def get(self, request: Request) -> Response:
        start_time = time.perf_counter()
        if 'q' not in request.query_params:
            return PlainTextResponse('Missing required query parameter "q"', status_code=400)
        client_str = request.client.host + ':' + str(request.client.port)
        query = request.query_params['q']

        parser = WhoisQueryParser(
            request.client.host,
            client_str,
            request.app.state.preloader,
            request.app.state.database_handler
        )
        response = parser.handle_query(query)
        response.clean_response()

        elapsed = time.perf_counter() - start_time
        length = len(response.result) if response.result else 0
        logger.info(f'{client_str}: sent answer to HTTP query, elapsed {elapsed:.9f}s, '
                    f'{length} chars: {query}')

        if response.response_type == WhoisQueryResponseType.ERROR_INTERNAL:
            return PlainTextResponse(response.result, status_code=500)
        if response.response_type == WhoisQueryResponseType.ERROR_USER:
            return PlainTextResponse(response.result, status_code=400)
        if response.result:
            return PlainTextResponse(response.result)
        else:
            return Response(status_code=204)
