import os

from ariadne.asgi import GraphQL
from setproctitle import setproctitle
from starlette.applications import Starlette
from starlette.endpoints import HTTPEndpoint
from starlette.responses import PlainTextResponse
from starlette.routing import Mount

from irrd.server.access_check import is_client_permitted
from irrd.server.graphql import ENV_UVICORN_WORKER_CONFIG_PATH
from irrd.server.graphql.extensions import error_formatter, QueryMetadataExtension
from irrd.server.graphql.resolvers import init_resolvers, close_resolvers
from irrd.server.graphql.schema_builder import build_executable_schema
from irrd.server.http.status_generator import StatusGenerator

"""
Starlette app and GraphQL sub-app.

This module is imported once for each Uvicorn worker process,
and then the app is started in each process.
"""


async def startup():
    setproctitle('irrd-http-server-listener')
    # As these are run in a separate process, the config file
    # is read from the environment.
    init_resolvers(os.getenv(ENV_UVICORN_WORKER_CONFIG_PATH))


async def shutdown():
    close_resolvers()


graphql = GraphQL(
    build_executable_schema(),
    debug=False,
    extensions=[QueryMetadataExtension],
    error_formatter=error_formatter,
)


class StatusApp(HTTPEndpoint):
    def get(self, request):
        if not is_client_permitted(request.client.host, 'server.http.status_access_list'):
            return PlainTextResponse('Access denied', status_code=403)

        response = StatusGenerator().generate_status()
        return PlainTextResponse(response)


routes = [
    Mount("/v1/status", StatusApp),
    Mount("/graphql", graphql),
]

app = Starlette(
    debug=False,
    routes=routes,
    on_startup=[startup],
    on_shutdown=[shutdown],
)
