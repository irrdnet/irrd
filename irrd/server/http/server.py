# flake8: noqa: E402
"""
Runner for the HTTP server process.
"""
import os
import sys
from pathlib import Path

import uvicorn
from setproctitle import setproctitle
from uvicorn import subprocess

sys.path.append(str(Path(__file__).resolve().parents[3]))

from irrd import __version__
from irrd.conf import get_setting, get_configuration

from irrd.server.graphql import ENV_UVICORN_WORKER_CONFIG_PATH


def run_http_server(config_path: str):
    setproctitle('irrd-http-server-manager')
    configuration = get_configuration()
    assert configuration
    os.environ[ENV_UVICORN_WORKER_CONFIG_PATH] = config_path
    uvicorn.run(
        app="irrd.server.http.app:app",
        host=get_setting('server.http.interface'),
        port=get_setting('server.http.port'),
        workers=get_setting('server.http.workers'),
        forwarded_allow_ips=get_setting('server.http.forwarded_allowed_ips'),
        headers=[['Server', f'IRRd {__version__}']],
        log_config=configuration.logging_config,
    )


def subprocess_started(config, target, sockets, stdin_fileno):
    """
    Uvicorns default method attempts magic with stdin which
    does not work with the IRRd daemon setup. This is an
    override that skips that step.
    """
    config.configure_logging()
    target(sockets=sockets)


uvicorn.subprocess.subprocess_started = subprocess_started
