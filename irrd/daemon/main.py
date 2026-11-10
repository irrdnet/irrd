#!/usr/bin/env python
import argparse
import grp
import logging
import multiprocessing
import os
import platform
import pwd
import signal
import stat
import sys
import time
import warnings
from pathlib import Path

import psutil
from pid import PidFile, PidFileError

import daemon
from daemon.daemon import change_process_owner

logger = logging.getLogger(__name__)
sys.path.append(str(Path(__file__).resolve().parents[2]))

import sqlalchemy.exc as sa_exc

from irrd import ENV_MAIN_PROCESS_PID, ENV_MAIN_STARTUP_TIME, __version__
from irrd.conf import CONFIG_PATH_DEFAULT, config_init, get_configuration, get_setting
from irrd.mirroring.scheduler import MirrorScheduler
from irrd.server.http.server import run_http_server
from irrd.server.whois.server import start_whois_server
from irrd.storage.preload import PreloadStoreManager
from irrd.utils.process_support import ExceptionLoggingProcess, set_traceback_handler

# This file does not have a unit test, but is instead tested through
# the integration tests. Writing a unit test would be too complex.

MIRROR_FREQUENCY = 3 if not os.environ.get("IRRD_TESTING_FAST_SCHEDULER_OVERRIDE") else 1


def main():
    if platform.python_implementation() == "PyPy":
        print("IRRD can not be run under PyPy. Use CPython instead.")
        sys.exit(1)

    description = """IRRd main process"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        dest="config_file_path",
        type=str,
        help=f"use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})",
    )
    parser.add_argument(
        "--foreground",
        dest="foreground",
        action="store_true",
        help="run IRRd in the foreground, don't detach",
    )
    args = parser.parse_args()

    daemon_kwargs = {
        # by default we set detach_process to true to avoid #848,
        # the python-daemon default of None does not suffice
        "detach_process": True,
        "umask": 0o022,
    }
    if args.foreground:
        daemon_kwargs["detach_process"] = False
        daemon_kwargs["stdout"] = sys.stdout
        daemon_kwargs["stderr"] = sys.stderr

    # Since Python 3.8, the default method is spawn for MacOS,
    # which creates several issues. For consistency, we force to fork.
    multiprocessing.set_start_method("fork")

    # config_init with commit may only be called within DaemonContext,
    # but this call here causes fast failure for most misconfigurations
    config_init(args.config_file_path, commit=False)

    staged_logfile_path = get_configuration().user_config_staging.get("log.logfile_path")
    staged_logging_config_path = get_configuration().user_config_staging.get("log.logging_config_path")
    if not any(
        [
            staged_logfile_path,
            staged_logging_config_path,
            args.foreground,
        ]
    ):
        logger.critical(
            "Unable to start: when not running in the foreground, you must set "
            "either log.logfile_path or log.logging_config_path in the settings"
        )
        return

    uid, gid = get_configured_owner(from_staging=True)
    if uid and gid:
        os.setegid(gid)
        os.seteuid(uid)
        # First check if a writable file already exists, if not,
        # if we have permission to create the file.
        if staged_logfile_path and not os.access(staged_logfile_path, os.W_OK, effective_ids=True):
            staged_logfile_dir = Path(staged_logfile_path).parent
            if not os.access(staged_logfile_dir, os.W_OK, effective_ids=True):
                logger.critical(
                    f"Unable to start: logfile {staged_logfile_path} not writable by UID {uid} / GID"
                    f" {gid}"
                )
                return

    with daemon.DaemonContext(**daemon_kwargs):
        config_init(args.config_file_path)

        uid, gid = get_configured_owner()
        # Running as root is permitted on CI
        if not os.environ.get("CI") and not uid and os.geteuid() == 0:
            logger.critical(
                "Unable to start: user and group must be defined in settings when starting IRRd as root"
            )
            return

        piddir = get_setting("piddir")
        # piddir has to be writable by the IRRD user, so a symlink, hard link
        # or other kind of file there could redirect this write to another
        # path writable by that user. This check is not atomic
        pidfile_path = os.path.abspath(os.path.join(piddir, "irrd.pid"))
        try:
            pidfile_stat = os.lstat(pidfile_path)
        except FileNotFoundError:
            pidfile_stat = None
        except OSError as oe:
            logger.critical(f"Unable to start: unable to check PID file {pidfile_path}: {oe}")
            return
        if pidfile_stat and (not stat.S_ISREG(pidfile_stat.st_mode) or pidfile_stat.st_nlink > 1):
            logger.critical(
                f"Unable to start: PID file {pidfile_path} is not a regular file, or is hard linked"
            )
            return

        logger.info("IRRd attempting to secure PID")
        try:
            with PidFile(pidname="irrd", piddir=piddir):
                logger.info(f"IRRd {__version__} starting, PID {os.getpid()}, PID file in {piddir}")
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=sa_exc.SAWarning)
                    run_irrd(
                        mirror_frequency=MIRROR_FREQUENCY,
                        config_file_path=(
                            args.config_file_path if args.config_file_path else CONFIG_PATH_DEFAULT
                        ),
                        uid=uid,
                        gid=gid,
                    )
        except PidFileError as pfe:
            logger.error(f"Failed to start IRRd, unable to lock PID file irrd.pid in {piddir}: {pfe}")
        except Exception:
            logger.exception("Error occurred in main process, terminating. Error follows:")
            os.kill(os.getpid(), signal.SIGTERM)


def run_irrd(mirror_frequency: int, config_file_path: str, uid: int | None, gid: int | None):
    terminated = False

    if sys.platform == "darwin":
        logger.warning("Running on Mac OS, disabling proxy usage by setting no_proxy=*")
        os.environ["no_proxy"] = " * "

    os.environ[ENV_MAIN_PROCESS_PID] = str(os.getpid())
    os.environ[ENV_MAIN_STARTUP_TIME] = str(int(time.time()))
    set_traceback_handler()

    whois_process = ExceptionLoggingProcess(
        target=start_whois_server, name="irrd-whois-server-listener", kwargs={"uid": uid, "gid": gid}
    )
    whois_process.start()
    if uid and gid:
        change_process_owner(uid=uid, gid=gid, initgroups=True)

    mirror_scheduler = MirrorScheduler()

    preload_manager = PreloadStoreManager(name="irrd-preload-store-manager")
    preload_manager.start()

    uvicorn_process = ExceptionLoggingProcess(
        target=run_http_server, name="irrd-http-server-listener", args=(config_file_path,)
    )
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
                logger.info(
                    "Main process received SIGHUP with valid config, sent SIGHUP to "
                    f"child processes {[c.pid for c in children]}"
                )

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
            logger.info(
                f"Main process received SIGTERM, sent SIGTERM to child processes {[c.pid for c in children]}"
            )

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

    logger.debug("Main process waiting for child processes to terminate")
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
        logger.info(
            "Some processes left alive after SIGTERM, send SIGKILL to "
            f"child processes {[c.pid for c in children]}"
        )

    logger.info("Main process exiting")


def get_configured_owner(from_staging=False) -> tuple[int | None, int | None]:
    uid = gid = None
    if not from_staging:
        user = get_setting("user")
        group = get_setting("group")
    else:
        config = get_configuration()
        assert config
        user = config.user_config_staging.get("user")
        group = config.user_config_staging.get("group")
    if user and group:
        uid = pwd.getpwnam(user).pw_uid
        gid = grp.getgrnam(group).gr_gid
    return uid, gid


if __name__ == "__main__":  # pragma: no cover
    main()
