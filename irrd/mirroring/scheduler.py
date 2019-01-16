import time
from collections import defaultdict

import logging
import threading
from typing import Dict

from irrd.conf import get_setting
from irrd.conf.defaults import DEFAULT_SOURCE_IMPORT_TIMER, DEFAULT_SOURCE_EXPORT_TIMER
from .mirror_runners_export import SourceExportRunner
from .mirror_runners_import import MirrorImportUpdateRunner

logger = logging.getLogger(__name__)


class MirrorScheduler:
    """
    Scheduler for mirroring processes.

    For each time run() is called, will start a thread for each mirror database
    unless a thread is still running for that database (which is likely to be
    the case in some full imports).
    """
    threads: Dict[str, threading.Thread]
    last_started_time: Dict[str, int]

    def __init__(self):
        self.threads = dict()
        self.last_started_time = defaultdict(lambda: 0)

    def run(self) -> None:
        for source in get_setting('sources').keys():
            is_mirror = get_setting(f'sources.{source}.import_source') or get_setting(f'sources.{source}.nrtm_host')
            import_timer = int(get_setting(f'sources.{source}.import_timer', DEFAULT_SOURCE_IMPORT_TIMER))

            if is_mirror:
                self.run_if_relevant(source, MirrorImportUpdateRunner, import_timer)

            runs_export = get_setting(f'sources.{source}.export_destination')
            export_timer = int(get_setting(f'sources.{source}.export_timer', DEFAULT_SOURCE_EXPORT_TIMER))

            if runs_export:
                self.run_if_relevant(source, SourceExportRunner, export_timer)

    def run_if_relevant(self, source: str, runner_class, timer: int):
        thread_name = f'Thread-{runner_class.__name__}-{source}'

        current_time = time.time()
        has_expired = (self.last_started_time[thread_name] + timer) < current_time
        if not has_expired or self._is_thread_running(thread_name):
            return

        logger.debug(f'Started new thread {thread_name} for mirror import/export for {source}')
        initiator = runner_class(source=source)
        thread = threading.Thread(target=initiator.run, name=thread_name)
        self.threads[thread_name] = thread
        thread.start()
        self.last_started_time[thread_name] = int(current_time)

    def _is_thread_running(self, thread_name: str):
        if thread_name not in self.threads:
            return False
        return self.threads[thread_name].is_alive()
