import json
import logging
import time
from json import JSONDecodeError

import limits
import pydantic
from asgiref.sync import sync_to_async
from IPy import IP
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from irrd.conf import get_setting
from irrd.server.access_check import (
    STARLETTE_TEST_CLIENT_HOST,
    is_client_permitted,
    rate_limit_host_key,
)
from irrd.updates.handler import ChangeSubmissionHandler
from irrd.utils.text import remove_control_chars
from irrd.utils.validators import RPSLChangeSubmission, RPSLSuspensionSubmission

from ... import META_KEY_HTTP_CLIENT_IP, META_KEYS_INTERNAL
from ...storage.models import AuthoritativeChangeOrigin
from ..whois.query_parser import WhoisQueryParser
from ..whois.query_response import WhoisQueryResponseType
from .metrics_generator import MetricsGenerator
from .status_generator import StatusGenerator

logger = logging.getLogger(__name__)

# Kept separate from the web interface limit, so one can not consume the other
RATE_LIMIT_SUBMISSION_AUTH_FAILURE_NAMESPACE = "irrd-submission-auth-failure"


def _rate_limit_args(host: str):
    rate_limit = limits.parse(get_setting("auth.submission_auth_failure_rate_limit"))
    return rate_limit, RATE_LIMIT_SUBMISSION_AUTH_FAILURE_NAMESPACE, rate_limit_host_key(host)


class StatusEndpoint(HTTPEndpoint):
    def get(self, request: Request) -> Response:
        host = request.client.host if request.client else STARLETTE_TEST_CLIENT_HOST
        if not is_client_permitted(host, "server.http.status_access_list"):
            return PlainTextResponse("Access denied", status_code=403)

        response = StatusGenerator().generate()
        return PlainTextResponse(response)


class MetricsEndpoint(HTTPEndpoint):
    def get(self, request: Request) -> Response:
        host = request.client.host if request.client else STARLETTE_TEST_CLIENT_HOST
        if not is_client_permitted(host, "server.http.status_access_list"):
            return PlainTextResponse("Access denied", status_code=403)

        response = MetricsGenerator().generate()
        return PlainTextResponse(response)


def clean_request_meta(request_meta: dict) -> dict:
    """Drop the metadata keys that IRRD fills itself from client provided metadata."""
    internal_keys = {key.lower() for key in META_KEYS_INTERNAL}
    cleaned = {}
    for key, value in request_meta.items():
        key = remove_control_chars(str(key)).strip()
        if key and value is not None and key.lower() not in internal_keys:
            cleaned[key] = value
    return cleaned


class WhoisQueryEndpoint(HTTPEndpoint):
    def get(self, request: Request) -> Response:
        host = request.client.host if request.client else STARLETTE_TEST_CLIENT_HOST
        port = request.client.port if request.client else 0
        start_time = time.perf_counter()
        if "q" not in request.query_params:
            return PlainTextResponse('Missing required query parameter "q"', status_code=400)
        client_str = host + ":" + str(port)
        query = request.query_params["q"]
        if not query.isprintable():
            return PlainTextResponse("Queries may not contain non-printable characters", status_code=400)

        parser = WhoisQueryParser(
            host, client_str, request.app.state.preloader, request.app.state.database_handler
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
        host = request.client.host if request.client else STARLETTE_TEST_CLIENT_HOST
        limiter = request.app.state.rate_limiter
        rate_limit_args = _rate_limit_args(host)
        if not await limiter.test(*rate_limit_args):
            logger.info(f"{host}: rejecting submission due to rate limiting")
            return PlainTextResponse("Request denied due to rate limiting", status_code=429)

        try:
            request_json = await request.json()
            data = RPSLChangeSubmission.model_validate(request_json)
        except (JSONDecodeError, pydantic.ValidationError) as error:
            return PlainTextResponse(str(error), status_code=400)

        try:
            meta_json = request.headers["X-irrd-metadata"]
            request_meta = json.loads(meta_json)
        except (JSONDecodeError, KeyError):
            request_meta = {}
        if not isinstance(request_meta, dict):
            request_meta = {}
        meta = clean_request_meta(request_meta)

        meta[META_KEY_HTTP_CLIENT_IP] = host
        meta["HTTP-User-Agent"] = request.headers.get("User-Agent")
        try:
            remote_ip = IP(host)
        except ValueError:
            remote_ip = None

        handler = ChangeSubmissionHandler()
        await sync_to_async(handler.load_change_submission)(
            data=data,
            origin=AuthoritativeChangeOrigin.webapi,
            delete=delete,
            request_meta=meta,
            remote_ip=remote_ip,
        )
        if handler.has_authentication_failures():
            await limiter.hit(*rate_limit_args)
        await sync_to_async(handler.send_notification_target_reports)()
        return JSONResponse(handler.submitter_report_json())


class SuspensionSubmissionEndpoint(HTTPEndpoint):
    async def post(self, request: Request) -> Response:
        host = request.client.host if request.client else STARLETTE_TEST_CLIENT_HOST
        limiter = request.app.state.rate_limiter
        rate_limit_args = _rate_limit_args(host)
        if not await limiter.test(*rate_limit_args):
            logger.info(f"{host}: rejecting suspension submission due to rate limiting")
            return PlainTextResponse("Request denied due to rate limiting", status_code=429)

        try:
            json = await request.json()
            data = RPSLSuspensionSubmission.model_validate(json)
        except (JSONDecodeError, pydantic.ValidationError) as error:
            return PlainTextResponse(str(error), status_code=400)

        request_meta = {
            META_KEY_HTTP_CLIENT_IP: host,
            "HTTP-User-Agent": request.headers.get("User-Agent"),
        }
        handler = ChangeSubmissionHandler()
        await sync_to_async(handler.load_suspension_submission)(data=data, request_meta=request_meta)
        if handler.has_authentication_failures():
            await limiter.hit(*rate_limit_args)
        return JSONResponse(handler.submitter_report_json())
