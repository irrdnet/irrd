import logging
import threading
from typing import Dict

from irrd.conf import get_setting
from .mirror_runners import MirrorUpdateRunner

logger = logging.getLogger(__name__)


class MirrorScheduler:
    """
    Scheduler for mirroring processes.

    For each time run() is called, will start a thread for each mirror database
    unless a thread is still running for that database (which is likely to be
    the case in some full imports).
    """
    threads: Dict[str, threading.Thread] = dict()
    running_deferreds = 0

    def run(self) -> None:
        for source in get_setting('sources').keys():
            is_mirror = get_setting(f'sources.{source}.import_source') or get_setting(f'sources.{source}.nrtm_host')
            if is_mirror and not self._is_thread_running(source):
                logger.debug(f'Started new thread for mirror update for {source}')
                initiator = MirrorUpdateRunner(source=source)
                thread = threading.Thread(target=initiator.run, name=f'Thread-MirrorUpdateRunner-{source}')
                self.threads[source] = thread
                thread.start()

    def _is_thread_running(self, source):
        if source not in self.threads:
            return False
        return self.threads[source].is_alive()
