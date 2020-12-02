import os

from ariadne.asgi import GraphQL
from setproctitle import setproctitle
from starlette.applications import Starlette
from starlette.routing import Mount

# Relative imports are not allowed in this file
from irrd.conf import config_init
from irrd.server.graphql import ENV_UVICORN_WORKER_CONFIG_PATH
from irrd.server.graphql.extensions import error_formatter, QueryMetadataExtension
from irrd.server.graphql.schema_builder import build_executable_schema
from irrd.server.http.endpoints import StatusEndpoint, WhoisQueryEndpoint
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.preload import Preloader

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
    setproctitle('irrd-http-server-listener')
    global app
    config_path = os.getenv(ENV_UVICORN_WORKER_CONFIG_PATH)
    config_init(config_path)
    app.state.database_handler = DatabaseHandler(readonly=True)
    app.state.preloader = Preloader(enable_queries=True)


async def shutdown():
    global app
    app.state.database_handler.close()
    app.state.preloader = None


graphql = GraphQL(
    build_executable_schema(),
    debug=False,
    extensions=[QueryMetadataExtension],
    error_formatter=error_formatter,
)

routes = [
    Mount("/v1/status", StatusEndpoint),
    Mount("/v1/whois", WhoisQueryEndpoint),
    Mount("/graphql", graphql),
]

app = Starlette(
    debug=False,
    routes=routes,
    on_startup=[startup],
    on_shutdown=[shutdown],
)
