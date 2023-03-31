import logging
import os
import signal

from ariadne.asgi import GraphQL
from ariadne.asgi.handlers import GraphQLHTTPHandler
from setproctitle import setproctitle
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.types import ASGIApp, Receive, Scope, Send

# Relative imports are not allowed in this file
from irrd import ENV_MAIN_PROCESS_PID
from irrd.conf import config_init
from irrd.server.graphql import ENV_UVICORN_WORKER_CONFIG_PATH
from irrd.server.graphql.extensions import QueryMetadataExtension, error_formatter
from irrd.server.graphql.schema_builder import build_executable_schema
from irrd.server.http.endpoints import (
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
    try:
        app.state.database_handler = DatabaseHandler(readonly=True)
        app.state.preloader = Preloader(enable_queries=True)
    except Exception as e:
        logger.critical(
            (
                "HTTP worker failed to initialise preloader or database, "
                f"unable to start, terminating IRRd, traceback follows: {e}"
            ),
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


graphql = GraphQL(
    build_executable_schema(),
    debug=False,
    http_handler=GraphQLHTTPHandler(
        extensions=[QueryMetadataExtension],
    ),
    error_formatter=error_formatter,
)

routes = [
    Mount("/v1/status", StatusEndpoint),
    Mount("/v1/whois", WhoisQueryEndpoint),
    Mount("/v1/submit", ObjectSubmissionEndpoint),
    Mount("/v1/suspension", SuspensionSubmissionEndpoint),
    Mount("/graphql", graphql),
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
    middleware=[Middleware(MemoryTrimMiddleware)],
)
