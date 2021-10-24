#!/usr/bin/env python
# flake8: noqa: E402
import argparse
import grp
import logging
import os
import pwd
import signal
import sys
import time
from pathlib import Path
from typing import Tuple, Optional

import daemon
import psutil
from daemon.daemon import change_process_owner
from pid import PidFile, PidFileError

logger = logging.getLogger(__name__)
sys.path.append(str(Path(__file__).resolve().parents[2]))

from irrd.utils.process_support import ExceptionLoggingProcess
from irrd.storage.preload import PreloadStoreManager
from irrd.server.whois.server import start_whois_server
from irrd.server.http.server import run_http_server
from irrd.mirroring.scheduler import MirrorScheduler
from irrd.conf import config_init, CONFIG_PATH_DEFAULT, get_setting, get_configuration
from irrd import __version__, ENV_MAIN_PROCESS_PID


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

    # config_init with commit may only be called within DaemonContext,
    # but this call here causes fast failure for most misconfigurations
    config_init(args.config_file_path, commit=False)

    if not any([
        get_configuration().user_config_staging.get('log.logfile_path'),
        get_configuration().user_config_staging.get('log.logging_config_path'),
        args.foreground,
    ]):
        logging.critical('Unable to start: when not running in the foreground, you must set '
                         'either log.logfile_path or log.logging_config_path in the settings')
        return

    with daemon.DaemonContext(**daemon_kwargs):
        config_init(args.config_file_path)

        uid, gid = get_configured_owner()
        # Running as root is permitted on CI
        if not os.environ.get('CI') and not uid and os.geteuid() == 0:
            logging.critical('Unable to start: user and group must be defined in settings '
                             'when starting IRRd as root')
            return

        piddir = get_setting('piddir')
        logger.info('IRRd attempting to secure PID')
        try:
            with PidFile(pidname='irrd', piddir=piddir):
                logger.info(f'IRRd {__version__} starting, PID {os.getpid()}, PID file in {piddir}')
                run_irrd(mirror_frequency=mirror_frequency,
                         config_file_path=args.config_file_path if args.config_file_path else CONFIG_PATH_DEFAULT,
                         uid=uid,
                         gid=gid,
                         )
        except PidFileError as pfe:
            logger.error(f'Failed to start IRRd, unable to lock PID file irrd.pid in {piddir}: {pfe}')
        except Exception as e:
            logger.error(f'Error occurred in main process, terminating. Error follows:')
            logger.exception(e)
            os.kill(os.getpid(), signal.SIGTERM)


def run_irrd(mirror_frequency: int, config_file_path: str, uid: Optional[int], gid: Optional[int]):
    terminated = False
    os.environ[ENV_MAIN_PROCESS_PID] = str(os.getpid())

    whois_process = ExceptionLoggingProcess(
        target=start_whois_server,
        name='irrd-whois-server-listener',
        kwargs={'uid': uid, 'gid': gid}
    )
    whois_process.start()
    if uid and gid:
        change_process_owner(uid=uid, gid=gid, initgroups=True)

    mirror_scheduler = MirrorScheduler()

    preload_manager = None
    if not get_setting(f'database_readonly'):
        preload_manager = PreloadStoreManager(name='irrd-preload-store-manager')
        preload_manager.start()

    uvicorn_process = ExceptionLoggingProcess(target=run_http_server, name='irrd-http-server-listener', args=(config_file_path, ))
    uvicorn_process.start()

    def sighup_handler(signum, frame):
        # On SIGHUP, check if the configuration is valid and reload in
        # this process, and if it is valid, signal SIGHUP to all
        # child processes.
        if get_configuration().reload():
            parent = psutil.Process(os.getpid())
            children = parent.children(recursive=True)
            for process in children:
                process.send_signal(signal.SIGHUP)
            if children:
                logging.info('Main process received SIGHUP with valid config, sent SIGHUP to '
                             f'child processes {[c.pid for c in children]}')
    signal.signal(signal.SIGHUP, sighup_handler)

    def sigterm_handler(signum, frame):
        mirror_scheduler.terminate_children()
        parent = psutil.Process(os.getpid())
        children = parent.children(recursive=True)
        for process in children:
            try:
                process.send_signal(signal.SIGTERM)
            except Exception:
                # If we can't SIGTERM some of the processes,
                # do the best we can.
                pass
        if children:
            logging.info('Main process received SIGTERM, sent SIGTERM to '
                         f'child processes {[c.pid for c in children]}')

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
    for child_process in whois_process, uvicorn_process, preload_manager:
        if child_process:
            child_process.join(timeout=3)

    parent = psutil.Process(os.getpid())
    children = parent.children(recursive=True)
    for process in children:
        try:
            process.send_signal(signal.SIGKILL)
        except Exception:
            pass
    if children:
        logging.info('Some processes left alive after SIGTERM, send SIGKILL to '
                     f'child processes {[c.pid for c in children]}')

    logging.info(f'Main process exiting')


def get_configured_owner() -> Tuple[Optional[int], Optional[int]]:
    uid = gid = None
    user = get_setting('user')
    group = get_setting('group')
    if user and group:
        uid = pwd.getpwnam(user).pw_uid
        gid = grp.getgrnam(group).gr_gid
    return uid, gid


if __name__ == '__main__':  # pragma: no cover
    main()
