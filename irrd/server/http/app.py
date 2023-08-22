import logging
import os
import signal
from pathlib import Path

import limits
from ariadne.asgi import GraphQL
from ariadne.asgi.handlers import GraphQLHTTPHandler
from asgi_logger import AccessLoggerMiddleware
from setproctitle import setproctitle
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
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

"""
Starlette app and GraphQL sub-app.

This module is imported once for each Uvicorn worker process,
and then the app is started in each process.
"""


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


graphql = GraphQL(
    build_executable_schema(),
    debug=False,
    http_handler=GraphQLHTTPHandler(
        extensions=[QueryMetadataExtension],
    ),
    error_formatter=error_formatter,
)

STATIC_DIR = templates = Path(__file__).parent.parent.parent / "webui" / "static"


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
    app.user_middleware = [
        # Use asgi-log to work around https://github.com/encode/uvicorn/issues/1384
        Middleware(
            AccessLoggerMiddleware,
            logger=logger,
            format='%(client_addr)s - "%(request_line)s" %(status_code)s - %(L)ss',
        ),
        Middleware(MemoryTrimMiddleware),
        Middleware(SessionMiddleware, secret_key=secret_key_derive("web.session_middleware")),
        Middleware(
            CSRFProtectMiddleware, csrf_secret=secret_key_derive("web.csrf_middleware"), enabled=not testing
        ),
        auth_middleware,
    ]
    app.middleware_stack = app.build_middleware_stack()
