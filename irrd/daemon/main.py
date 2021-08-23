#!/usr/bin/env python
# flake8: noqa: E402
import sys
import time
from pwd import getpwnam

import argparse
import daemon
import logging
import os
import signal
from pathlib import Path
from pid import PidFile, PidFileError


logger = logging.getLogger(__name__)
sys.path.append(str(Path(__file__).resolve().parents[2]))

from irrd import __version__
from irrd.conf import config_init, CONFIG_PATH_DEFAULT, get_setting, get_configuration
from irrd.mirroring.scheduler import MirrorScheduler
from irrd.server.http.server import start_http_server
from irrd.server.whois.server import start_whois_server
from irrd.storage.preload import PreloadStoreManager
from irrd.utils.process_support import ExceptionLoggingProcess
from irrd.storage.preload import PreloadStoreManager
from irrd.server.whois.server import start_whois_server
from irrd.server.http.server import start_http_server
from irrd.mirroring.scheduler import MirrorScheduler
from irrd.conf import config_init, CONFIG_PATH_DEFAULT, get_setting, get_configuration
from irrd import __version__


# This file does not have a unit test, but is instead tested through
# the integration tests. Writing a unit test would be too complex.

def main():
    description = """IRRd main process"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    parser.add_argument('--foreground', dest='foreground', action='store_true',
                        help=f"run IRRd in the foreground, don't detach")
    args = parser.parse_args()

    mirror_frequency = int(os.environ.get('IRRD_SCHEDULER_TIMER_OVERRIDE', 15))

    daemon_kwargs = {
        'umask': 0o022,
    }
    if args.foreground:
        daemon_kwargs['detach_process'] = False
        daemon_kwargs['stdout'] = sys.stdout
        daemon_kwargs['stderr'] = sys.stderr

    # config_init w/ commit may only be called within DaemonContext
    config_init(args.config_file_path, commit=False)

    with daemon.DaemonContext(**daemon_kwargs):
        config_init(args.config_file_path)
        piddir = get_setting('piddir')
        logger.info('IRRd attempting to secure PID')
        try:
            with PidFile(pidname='irrd', piddir=piddir):
                logger.info(f'IRRd {__version__} starting, PID {os.getpid()}, PID file in {piddir}')
                run_irrd(mirror_frequency)
        except PidFileError as pfe:
            logger.error(f'Failed to start IRRd, unable to lock PID file irrd.pid in {piddir}: {pfe}')
        except Exception as e:
            logger.error(f'Error occurred in main process, terminating. Error follows:')
            logger.exception(e)
            os.kill(os.getpid(), signal.SIGTERM)


def run_irrd(mirror_frequency: int):
    terminated = False

    mirror_scheduler = MirrorScheduler()
    whois_process = ExceptionLoggingProcess(target=start_whois_server, name='irrd-whois-server-listener')
    whois_process.start()
    http_process = ExceptionLoggingProcess(target=start_http_server, name='irrd-http-server-listener')
    http_process.start()

    preload_manager = None
    if not get_setting(f'database_readonly'):
        preload_manager = PreloadStoreManager(name='irrd-preload-store-manager')
        preload_manager.start()

    def sighup_handler(signum, frame):
        # On SIGHUP, check if the configuration is valid and reload in
        # this process, and if it is valid, signal our three long-running
        # child processes. All other processes are short-lived and forked
        # from those or this process, so any new ones will pick up
        # the new config automatically.
        if get_configuration().reload():
            pids = [whois_process.pid, http_process.pid, preload_manager.pid]
            logging.info('Main process received SIGHUP with valid config, sending SIGHUP to '
                         f'child processes {pids}')
            for pid in pids:
                os.kill(pid, signal.SIGHUP)
    signal.signal(signal.SIGHUP, sighup_handler)

    def sigterm_handler(signum, frame):
        logging.info(f'Main process received SIGTERM, sending SIGTERM to all child processes')
        mirror_scheduler.terminate_children()
        try:
            whois_process.terminate()
        except Exception:  # pragma no cover
            pass
        try:
            http_process.terminate()
        except Exception:  # pragma no cover
            pass
        try:
            preload_manager.terminate()
        except Exception:  # pragma no cover
            pass
        nonlocal terminated
        terminated = True
    signal.signal(signal.SIGTERM, sigterm_handler)

    sleeps = mirror_frequency
    while not terminated:
        # This loops every second to prevent long blocking on SIGTERM.
        mirror_scheduler.update_process_state()
        if sleeps >= mirror_frequency:
            mirror_scheduler.run()
            sleeps = 0
        time.sleep(1)
        sleeps += 1

    logging.debug(f'Main process waiting for child processes to terminate')
    whois_process.join()
    http_process.join()
    if preload_manager:
        preload_manager.join()
    logging.info(f'Main process exiting')


if __name__ == '__main__':  # pragma: no cover
    main()
