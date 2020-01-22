#!/usr/bin/env python
# flake8: noqa: E402
import sys
import time
from multiprocessing import Process
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


# This file does not have a unit test, but is instead tested through
# the integration tests. Writing a unit test would be too complex.

def main():
    description = """IRRd main process"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    parser.add_argument('--foreground', dest='foreground', action='store_true',
                        help=f"run IRRd in the foreground, don't detach")
    parser.add_argument('--uid', dest='uid', type=str,
                        help=f"run the process under this UID")
    args = parser.parse_args()

    mirror_frequency = int(os.environ.get('IRRD_SCHEDULER_TIMER_OVERRIDE', 15))

    daemon_kwargs = {
        'umask': 0o022,
    }
    if args.uid:
        daemon_kwargs['uid'] = getpwnam(args.uid).pw_uid
    if args.foreground:
        daemon_kwargs['detach_process'] = False
        daemon_kwargs['stdout'] = sys.stdout
        daemon_kwargs['stderr'] = sys.stderr

    config_init(args.config_file_path, commit=False)

    with daemon.DaemonContext(**daemon_kwargs):
        config_init(args.config_file_path)  # config_init w/ commit may only be called within DaemonContext
        piddir = get_setting('piddir')
        logger.info('IRRd attempting to secure PID')
        try:
            with PidFile(pidname='irrd', piddir=piddir):
                logger.info(f'IRRd {__version__} starting, PID {os.getpid()}, PID file in {piddir}')
                run_irrd(mirror_frequency)
        except PidFileError as pfe:
            logger.error(f'Failed to start IRRd, unable to lock PID file irrd.pid in {piddir}: {pfe}')


def run_irrd(mirror_frequency: int):
    terminated = False

    mirror_scheduler = MirrorScheduler()
    whois_process = Process(target=start_whois_server, name='irrd-whois-server-listener', daemon=True)
    whois_process.start()
    http_process = Process(target=start_http_server, name='irrd-http-server-listener', daemon=True)
    http_process.start()
    preload_manager = PreloadStoreManager(name='irrd-preload-store-manager')
    preload_manager.start()

    def sighup_handler(signum, frame):
        # On SIGHUP, check if the configuration is valid and reload in
        # this process, and if it is valid, signal our two long-running
        # child processes. All other processes are short-lived and forked
        # from those or this process, so any new ones will pick up
        # the new config automatically.
        if get_configuration().reload():
            os.kill(whois_process.pid, signal.SIGHUP)
            os.kill(http_process.pid, signal.SIGHUP)
            os.kill(preload_manager.pid, signal.SIGHUP)
    signal.signal(signal.SIGHUP, sighup_handler)

    def sigterm_handler(signum, frame):
        whois_process.terminate()
        http_process.terminate()
        preload_manager.terminate()
        mirror_scheduler.terminate_children()
        nonlocal terminated
        terminated = True
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Prevent child processes from becoming zombies
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    sleeps = mirror_frequency
    while not terminated:
        # This loops every second to prevent long blocking on SIGTERM.
        if sleeps >= mirror_frequency:
            mirror_scheduler.run()
            sleeps = 0
        time.sleep(1)
        sleeps += 1


if __name__ == '__main__':  # pragma: no cover
    main()
