import json
import logging
import time
from json import JSONDecodeError

import pydantic
from asgiref.sync import sync_to_async
from IPy import IP
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from irrd.server.access_check import is_client_permitted
from irrd.updates.handler import ChangeSubmissionHandler
from irrd.utils.validators import RPSLChangeSubmission, RPSLSuspensionSubmission

from ... import META_KEY_HTTP_CLIENT_IP
from ...storage.models import AuthoritativeChangeOrigin
from ..whois.query_parser import WhoisQueryParser
from ..whois.query_response import WhoisQueryResponseType
from .status_generator import StatusGenerator

logger = logging.getLogger(__name__)


class StatusEndpoint(HTTPEndpoint):
    def get(self, request: Request) -> Response:
        assert request.client
        if not is_client_permitted(request.client.host, "server.http.status_access_list"):
            return PlainTextResponse("Access denied", status_code=403)

        response = StatusGenerator().generate_status()
        return PlainTextResponse(response)


class WhoisQueryEndpoint(HTTPEndpoint):
    def get(self, request: Request) -> Response:
        assert request.client
        start_time = time.perf_counter()
        if "q" not in request.query_params:
            return PlainTextResponse('Missing required query parameter "q"', status_code=400)
        client_str = request.client.host + ":" + str(request.client.port)
        query = request.query_params["q"]

        parser = WhoisQueryParser(
            request.client.host, client_str, request.app.state.preloader, request.app.state.database_handler
        )
        response = parser.handle_query(query)
        response.clean_response()

        elapsed = time.perf_counter() - start_time
        length = len(response.result) if response.result else 0
        logger.info(
            f"{client_str}: sent answer to HTTP query, elapsed {elapsed:.9f}s, {length} chars: {query}"
        )

        if response.response_type == WhoisQueryResponseType.ERROR_INTERNAL:
            return PlainTextResponse(response.result, status_code=500)
        if response.response_type == WhoisQueryResponseType.ERROR_USER:
            return PlainTextResponse(response.result, status_code=400)
        if response.result:
            return PlainTextResponse(response.result)
        else:
            return Response(status_code=204)


class ObjectSubmissionEndpoint(HTTPEndpoint):
    async def post(self, request: Request) -> Response:
        return await self._handle_submission(request, delete=False)

    async def delete(self, request: Request) -> Response:
        return await self._handle_submission(request, delete=True)

    async def _handle_submission(self, request: Request, delete=False):
        assert request.client
        try:
            request_json = await request.json()
            data = RPSLChangeSubmission.parse_obj(request_json)
        except (JSONDecodeError, pydantic.ValidationError) as error:
            return PlainTextResponse(str(error), status_code=400)

        try:
            meta_json = request.headers["X-irrd-metadata"]
            request_meta = json.loads(meta_json)
        except (JSONDecodeError, KeyError):
            request_meta = {}

        request_meta[META_KEY_HTTP_CLIENT_IP] = request.client.host
        request_meta["HTTP-User-Agent"] = request.headers.get("User-Agent")
        try:
            remote_ip = IP(request.client.host)
        except ValueError:
            remote_ip = None

        handler = ChangeSubmissionHandler()
        await sync_to_async(handler.load_change_submission)(
            data=data,
            origin=AuthoritativeChangeOrigin.webapi,
            delete=delete,
            request_meta=request_meta,
            remote_ip=remote_ip,
        )
        await sync_to_async(handler.send_notification_target_reports)()
        return JSONResponse(handler.submitter_report_json())


class SuspensionSubmissionEndpoint(HTTPEndpoint):
    async def post(self, request: Request) -> Response:
        assert request.client
        try:
            json = await request.json()
            data = RPSLSuspensionSubmission.parse_obj(json)
        except (JSONDecodeError, pydantic.ValidationError) as error:
            return PlainTextResponse(str(error), status_code=400)

        request_meta = {
            META_KEY_HTTP_CLIENT_IP: request.client.host,
            "HTTP-User-Agent": request.headers.get("User-Agent"),
        }
        handler = ChangeSubmissionHandler()
        await sync_to_async(handler.load_suspension_submission)(data=data, request_meta=request_meta)
        return JSONResponse(handler.submitter_report_json())
