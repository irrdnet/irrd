import logging
import threading

from irrd.conf import get_setting
from irrd.nrtm.initiator import NRTMInitiatior

logger = logging.getLogger(__name__)


class NRTMScheduler:
    threads = dict()
    running_deferreds = 0

    def run(self) -> None:
        for source in get_setting('databases').keys():
            if not self.is_thread_running(source):
                logger.debug(f'Started new thread for NRTM initiator for {source}')
                initiator = NRTMInitiatior(source=source)
                thread = threading.Thread(target=initiator.run)
                self.threads[source] = thread
                thread.start()

    def is_thread_running(self, source):
        if source not in self.threads:
            return False
        return self.threads[source].is_alive()
