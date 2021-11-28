import time
from collections import defaultdict

import gc
import logging
import multiprocessing

import signal
from setproctitle import setproctitle
from typing import Dict

from irrd.conf import get_setting, RPKI_IRR_PSEUDO_SOURCE
from irrd.conf.defaults import DEFAULT_SOURCE_IMPORT_TIMER, DEFAULT_SOURCE_EXPORT_TIMER
from .mirror_runners_export import SourceExportRunner
from .mirror_runners_import import RPSLMirrorImportUpdateRunner, ROAImportRunner, \
    ScopeFilterUpdateRunner

logger = logging.getLogger(__name__)

MAX_SIMULTANEOUS_RUNS = 3


class ScheduledTaskProcess(multiprocessing.Process):
    def __init__(self, runner, *args, **kwargs):
        self.runner = runner
        super().__init__(*args, **kwargs)

    def close(self):  # pragma: no cover
        """
        close() is not available in Python 3.6,
        use our own implementation if needed.
        """
        if hasattr(super, 'close'):
            return super().close()
        if self._popen is not None:
            if self._popen.poll() is None:
                raise ValueError("Cannot close a process while it is still running. "
                                 "You should first call join() or terminate().")
            self._popen = None
            del self._sentinel
        self._closed = True

    def run(self):
        # Disable the special sigterm_handler defined in main()
        # (signal handlers are inherited)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

        setproctitle(f'irrd-{self.name}')
        self.runner.run()


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
        self.previous_scopefilter_prefixes = None
        self.previous_scopefilter_asns = None
        self.previous_scopefilter_excluded = None

    def run(self) -> None:
        if get_setting('database_readonly'):
            return

        if get_setting('rpki.roa_source'):
            import_timer = int(get_setting('rpki.roa_import_timer'))
            self.run_if_relevant(RPKI_IRR_PSEUDO_SOURCE, ROAImportRunner, import_timer)

        if self._check_scopefilter_change():
            self.run_if_relevant('scopefilter', ScopeFilterUpdateRunner, 0)

        sources_started = 0
        for source in get_setting('sources', {}).keys():
            if sources_started >= MAX_SIMULTANEOUS_RUNS:
                break
            started_import = False
            started_export = False

            is_mirror = get_setting(f'sources.{source}.import_source') or get_setting(f'sources.{source}.nrtm_host')
            import_timer = int(get_setting(f'sources.{source}.import_timer', DEFAULT_SOURCE_IMPORT_TIMER))

            if is_mirror:
                started_import = self.run_if_relevant(source, RPSLMirrorImportUpdateRunner, import_timer)

            runs_export = get_setting(f'sources.{source}.export_destination') or get_setting(f'sources.{source}.export_destination_unfiltered')
            export_timer = int(get_setting(f'sources.{source}.export_timer', DEFAULT_SOURCE_EXPORT_TIMER))

            if runs_export:
                started_export = self.run_if_relevant(source, SourceExportRunner, export_timer)

            if started_import or started_export:
                sources_started += 1

    def _check_scopefilter_change(self) -> bool:
        """
        Check whether the scope filter has changed since last call.
        Always returns True on the first call.
        """
        if not get_setting('scopefilter'):
            return False

        current_prefixes = list(get_setting('scopefilter.prefixes', []))
        current_asns = list(get_setting('scopefilter.asns', []))
        current_exclusions = {
            name
            for name, settings in get_setting('sources', {}).items()
            if settings.get('scopefilter_excluded')
        }

        if any([
            self.previous_scopefilter_prefixes != current_prefixes,
            self.previous_scopefilter_asns != current_asns,
            self.previous_scopefilter_excluded != current_exclusions,
        ]):
            self.previous_scopefilter_prefixes = current_prefixes
            self.previous_scopefilter_asns = current_asns
            self.previous_scopefilter_excluded = current_exclusions
            return True
        return False

    def run_if_relevant(self, source: str, runner_class, timer: int) -> bool:
        process_name = f'{runner_class.__name__}-{source}'

        current_time = time.time()
        has_expired = (self.last_started_time[process_name] + timer) < current_time
        if not has_expired or process_name in self.processes:
            return False

        logger.debug(f'Started new process {process_name} for mirror import/export for {source}')
        initiator = runner_class(source=source)
        process = ScheduledTaskProcess(runner=initiator, name=process_name)
        self.processes[process_name] = process
        process.start()
        self.last_started_time[process_name] = int(current_time)
        return True

    def terminate_children(self) -> None:  # pragma: no cover
        logger.info('MirrorScheduler terminating children')
        for process in self.processes.values():
            try:
                process.terminate()
                process.join()
            except Exception:
                pass

    def update_process_state(self):
        multiprocessing.active_children()  # to reap zombies
        gc_collect_needed = False
        for process_name, process in list(self.processes.items()):
            if process.is_alive():
                continue
            try:
                process.close()
            except Exception as e:  # pragma: no cover
                logging.error(f'Failed to close {process_name} (pid {process.pid}), '
                              f'possible resource leak: {e}')
            del self.processes[process_name]
            gc_collect_needed = True
        if gc_collect_needed:
            # prevents FIFO pipe leak, see #578
            gc.collect()
