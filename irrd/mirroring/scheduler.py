import time
from collections import defaultdict

import logging
import multiprocessing

import psutil
import signal
from setproctitle import setproctitle
from typing import Dict

from irrd.conf import get_setting, RPKI_IRR_PSEUDO_SOURCE
from irrd.conf.defaults import DEFAULT_SOURCE_IMPORT_TIMER, DEFAULT_SOURCE_EXPORT_TIMER, DEFAULT_RPKI_IMPORT_TIMER
from .mirror_runners_export import SourceExportRunner
from .mirror_runners_import import RPSLMirrorImportUpdateRunner, ROAImportRunner

logger = logging.getLogger(__name__)


class ScheduledTaskProcess(multiprocessing.Process):
    def __init__(self, runner, *args, **kwargs):
        self.runner = runner
        super().__init__(*args, **kwargs)

    def run(self):
        # Disable the special sigterm_handler defined in main()
        # (signal handlers are inherited)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

        setproctitle(f'irrd-{self.name}')
        self.runner.run()

    def resilient_is_alive(self):  # pragma: no cover
        # The built-in is_alive() does not handle cases
        # where SIGCHLD is set to SIG_IGN to prevent zombies.
        return psutil.pid_exists(self.pid)


class MirrorScheduler:
    """
    Scheduler for mirroring processes.

    For each time run() is called, will start a process for each mirror database
    unless a process is still running for that database (which is likely to be
    the case in some full imports).
    """
    processes: Dict[str, ScheduledTaskProcess]
    last_started_time: Dict[str, int]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processes = dict()
        self.last_started_time = defaultdict(lambda: 0)

    def run(self) -> None:
        for source in get_setting('sources', {}).keys():
            is_mirror = get_setting(f'sources.{source}.import_source') or get_setting(f'sources.{source}.nrtm_host')
            import_timer = int(get_setting(f'sources.{source}.import_timer', DEFAULT_SOURCE_IMPORT_TIMER))

            if is_mirror:
                self.run_if_relevant(source, RPSLMirrorImportUpdateRunner, import_timer)

            runs_export = get_setting(f'sources.{source}.export_destination')
            export_timer = int(get_setting(f'sources.{source}.export_timer', DEFAULT_SOURCE_EXPORT_TIMER))

            if runs_export:
                self.run_if_relevant(source, SourceExportRunner, export_timer)

        if get_setting('rpki.roa_source'):
            import_timer = int(get_setting(f'rpki.roa_import_timer', DEFAULT_RPKI_IMPORT_TIMER))
            self.run_if_relevant(RPKI_IRR_PSEUDO_SOURCE, ROAImportRunner, import_timer)

    def run_if_relevant(self, source: str, runner_class, timer: int):
        process_name = f'Process-{runner_class.__name__}-{source}'

        current_time = time.time()
        has_expired = (self.last_started_time[process_name] + timer) < current_time
        if not has_expired or self._is_process_running(process_name):
            return

        logger.debug(f'Started new process {process_name} for mirror import/export for {source}')
        initiator = runner_class(source=source)
        process = ScheduledTaskProcess(runner=initiator, name=process_name)
        self.processes[process_name] = process
        process.start()
        self.last_started_time[process_name] = int(current_time)

    def terminate_children(self) -> None:  # pragma: no cover
        for process in self.processes.values():
            try:
                process.terminate()
                process.join()
            except Exception:
                pass

    def _is_process_running(self, process_name: str) -> bool:
        if process_name not in self.processes:
            return False
        return self.processes[process_name].resilient_is_alive()
