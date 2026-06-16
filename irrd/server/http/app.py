import logging
import os
import signal
from pathlib import Path
from urllib.parse import urlparse

import limits
from ariadne.asgi import GraphQL
from ariadne.asgi.handlers import GraphQLHTTPHandler
from asgi_logger import AccessLoggerMiddleware
from setproctitle import setproctitle
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette_wtf import CSRFProtectMiddleware

# Relative imports are not allowed in this file
from irrd import ENV_MAIN_PROCESS_PID
from irrd.conf import config_init, get_setting
from irrd.server.graphql import ENV_UVICORN_WORKER_CONFIG_PATH
from irrd.server.graphql.extensions import QueryMetadataExtension, error_formatter
from irrd.server.graphql.graphiql_csp import GRAPHIQL_CDN_ORIGIN, build_explorer
from irrd.server.graphql.schema_builder import build_executable_schema
from irrd.server.http.endpoints_api import (
    ObjectSubmissionEndpoint,
    StatusEndpoint,
    SuspensionSubmissionEndpoint,
    WhoisQueryEndpoint,
)
from irrd.server.http.event_stream import (
    EventStreamEndpoint,
    EventStreamInitialDownloadEndpoint,
)
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.preload import Preloader
from irrd.utils.process_support import memory_trim, set_traceback_handler
from irrd.webui.auth.users import auth_middleware
from irrd.webui.helpers import secret_key_derive
from irrd.webui.routes import UI_ROUTES

logger = logging.getLogger(__name__)


# Starlette app and GraphQL sub-app. This module is imported once for each
# Uvicorn worker process, and then the app is started in each process.


async def startup():
    """
    Prepare the database connection and preloader, which
    is shared between different queries in this process.
    As these are run in a separate process, the config file
    is read from the environment.
    """
    setproctitle("irrd-http-server-listener")
    set_traceback_handler()
    global app
    config_path = os.getenv(ENV_UVICORN_WORKER_CONFIG_PATH)
    config_init(config_path)
    set_middleware(app)
    try:
        app.state.database_handler = DatabaseHandler(readonly=True)
        app.state.preloader = Preloader(enable_queries=True)
        async_redis_prefix = ""
        if get_setting("redis_url").startswith("redis://"):
            async_redis_prefix = "async+"
        elif get_setting("redis_url").startswith("unix://"):
            async_redis_prefix = "async+redis+"
        app.state.rate_limiter_storage = limits.storage.storage_from_string(
            async_redis_prefix + get_setting("redis_url"),
            protocol_version=2,
        )
        app.state.rate_limiter = limits.aio.strategies.MovingWindowRateLimiter(app.state.rate_limiter_storage)
    except Exception as e:
        logger.critical(
            "HTTP worker failed to initialise preloader, database or rate limiter, "
            f"unable to start, terminating IRRd, traceback follows: {e}",
            exc_info=e,
        )
        main_pid = os.getenv(ENV_MAIN_PROCESS_PID)
        if main_pid:
            os.kill(int(main_pid), signal.SIGTERM)
        else:
            logger.error("Failed to terminate IRRd, unable to find main process PID")
        return


async def shutdown():
    global app
    app.state.database_handler.close()
    app.state.preloader = None
    app.state.rate_limiter = None


_graphiql = build_explorer()

graphql = GraphQL(
    build_executable_schema(),
    debug=False,
    http_handler=GraphQLHTTPHandler(
        extensions=[QueryMetadataExtension],
    ),
    explorer=_graphiql.explorer,
    error_formatter=error_formatter,
)

STATIC_DIR = Path(__file__).parent.parent.parent / "webui" / "static"


routes = [
    Route("/", lambda request: RedirectResponse("/ui/", status_code=302)),
    Mount("/v1/status", StatusEndpoint),
    Mount("/v1/whois", WhoisQueryEndpoint),
    Mount("/v1/submit", ObjectSubmissionEndpoint),
    Mount("/v1/suspension", SuspensionSubmissionEndpoint),
    Mount("/graphql", graphql),
    Mount("/ui", name="ui", routes=UI_ROUTES),
    Mount("/static", name="static", app=StaticFiles(directory=STATIC_DIR)),
    WebSocketRoute("/v1/event-stream/", EventStreamEndpoint),
    Route("/v1/event-stream/initial/", EventStreamInitialDownloadEndpoint),
]


class MemoryTrimMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)
        memory_trim()


CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'none'",
        # GraphiQL's inline <script>/<style> blocks (emitted by ariadne's stock
        # ExplorerGraphiQL) are allowed by content hash so we don't need
        # 'unsafe-inline'. The React + GraphiQL bundles and stylesheets loaded
        # from the CDN are pinned via SRI integrity attributes injected by
        # build_explorer().
        " ".join(["script-src 'self'", *_graphiql.script_hashes, GRAPHIQL_CDN_ORIGIN]),
        " ".join(["style-src 'self'", *_graphiql.style_hashes, GRAPHIQL_CDN_ORIGIN]),
        "img-src 'self'",
        "font-src 'self'",
        "connect-src 'self'",
        "form-action 'self'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
    ]
)


PERMISSIONS_POLICY = ", ".join(
    [
        # publickey-credentials-* are required for WebAuthn registration and
        # authentication; everything else IRRD does not use.
        "publickey-credentials-create=(self)",
        "publickey-credentials-get=(self)",
        "accelerometer=()",
        "ambient-light-sensor=()",
        "autoplay=()",
        "battery=()",
        "camera=()",
        "display-capture=()",
        "document-domain=()",
        "encrypted-media=()",
        "fullscreen=()",
        "gamepad=()",
        "geolocation=()",
        "gyroscope=()",
        "hid=()",
        "idle-detection=()",
        "magnetometer=()",
        "microphone=()",
        "midi=()",
        "otp-credentials=()",
        "payment=()",
        "picture-in-picture=()",
        "screen-wake-lock=()",
        "serial=()",
        "speaker-selection=()",
        "usb=()",
        "web-share=()",
        "xr-spatial-tracking=()",
    ]
)


SECURITY_HEADERS = {
    b"content-security-policy": CONTENT_SECURITY_POLICY.encode(),
    b"permissions-policy": PERMISSIONS_POLICY.encode(),
    b"x-content-type-options": b"nosniff",
    b"x-frame-options": b"DENY",
    b"referrer-policy": b"strict-origin-when-cross-origin",
    b"origin-agent-cluster": b"?1",
    b"cross-origin-opener-policy": b"same-origin",
    # same-origin is correct for the web UI. If CORS is ever added to the API routes
    # (/graphql, /v1/*), this header must be changed to cross-origin for those routes,
    # otherwise CORP will override CORS and block cross-origin browser clients.
    b"cross-origin-resource-policy": b"same-origin",
    b"cross-origin-embedder-policy": b"require-corp",
    b"x-permitted-cross-domain-policies": b"none",
}


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, session_cookie_name: str) -> None:
        self.app = app
        self.session_cookie_name = session_cookie_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        has_session_cookie = self.session_cookie_name in Request(scope).cookies

        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                response_headers = message.get("headers", [])
                sets_session_cookie = any(
                    v.startswith(self.session_cookie_name + "=")
                    for v in Headers(raw=response_headers).getlist("set-cookie")
                )
                headers = SECURITY_HEADERS.copy()
                if has_session_cookie or sets_session_cookie:
                    headers[b"cache-control"] = b"no-store"
                # Keep all existing headers except those we're overriding,
                # preserving duplicates (e.g. multiple Set-Cookie headers)
                merged = [(k, v) for k, v in response_headers if k.lower() not in headers]
                merged.extend(headers.items())
                message = {**message, "headers": merged}
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


app = Starlette(
    debug=False,
    routes=routes,
    on_startup=[startup],
    on_shutdown=[shutdown],
)


def set_middleware(app):
    testing = os.environ.get("TESTING", False)
    if testing:
        logger.info("Running in testing mode, disabling CSRF.")

    configured_url = urlparse(get_setting("server.http.url"))
    allowed_host = configured_url.hostname
    https_only = configured_url.scheme == "https"
    if not https_only and not testing:
        logger.warning(
            "server.http.url is not https://; the session cookie will be sent without the"
            " Secure flag and without the __Host- prefix. Set server.http.url to your"
            " external https:// URL for any production deployment."
        )
    # __Host- is browser-enforced: the cookie is rejected unless Set-Cookie has
    # Secure, no Domain attribute, and Path=/. We pass path="/" and rely on
    # SessionMiddleware's domain=None default; https_only=True provides Secure.
    session_cookie_name = "__Host-session" if https_only else "session"

    app.user_middleware = [
        # Use asgi-log to work around https://github.com/encode/uvicorn/issues/1384
        Middleware(
            AccessLoggerMiddleware,
            logger=logger,
            format='%(client_addr)s - "%(request_line)s" %(status_code)s - %(L)ss',
        ),
        Middleware(TrustedHostMiddleware, allowed_hosts=[allowed_host]),
        Middleware(SecurityHeadersMiddleware, session_cookie_name=session_cookie_name),
        Middleware(MemoryTrimMiddleware),
        Middleware(
            SessionMiddleware,
            secret_key=secret_key_derive("web.session_middleware"),
            session_cookie=session_cookie_name,
            path="/",
            same_site="lax",
            https_only=https_only,
        ),
        Middleware(
            CSRFProtectMiddleware, csrf_secret=secret_key_derive("web.csrf_middleware"), enabled=not testing
        ),
        auth_middleware,
    ]
    app.middleware_stack = app.build_middleware_stack()
