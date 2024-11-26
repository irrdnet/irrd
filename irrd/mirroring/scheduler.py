import gc
import logging
import multiprocessing
import signal
import time
from collections import defaultdict
from typing import Optional

from setproctitle import setproctitle

from irrd.conf import get_setting
from irrd.conf.defaults import (
    DEFAULT_SOURCE_EXPORT_TIMER,
    DEFAULT_SOURCE_EXPORT_TIMER_NRTM4,
    DEFAULT_SOURCE_IMPORT_TIMER,
    DEFAULT_SOURCE_IMPORT_TIMER_NRTM4,
)
from irrd.mirroring.jobs import TransactionTimePreloadSignaller

from .mirror_runners_export import SourceExportRunner
from .mirror_runners_import import (
    ROAImportRunner,
    RoutePreferenceUpdateRunner,
    RPSLMirrorImportUpdateRunner,
    ScopeFilterUpdateRunner,
)
from .nrtm4.nrtm4_server import NRTM4Server

logger = logging.getLogger(__name__)

MAX_SIMULTANEOUS_RUNS = 1


class ScheduledTaskProcess(multiprocessing.Process):
    def __init__(self, runner, *args, **kwargs):
        self.runner = runner
        super().__init__(*args, **kwargs)

    def run(self):
        # Disable the special sigterm_handler defined in main()
        # (signal handlers are inherited)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

        setproctitle(f"irrd-{self.name}")
        self.runner.run()


class MirrorScheduler:
    """
    Scheduler for periodic processes, mainly mirroring.

    For each time run() is called, will start a process for each mirror database
    unless a process is still running for that database (which is likely to be
    the case in some full imports).
    """

    processes: dict[str, ScheduledTaskProcess]
    last_started_time: dict[str, int]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processes = dict()
        self.last_started_time = defaultdict(int)
        self.previous_scopefilter_prefixes = None
        self.previous_scopefilter_asns = None
        self.previous_scopefilter_excluded = None
        # This signaller is special in that it does not run in a separate
        # process and keeps state in the instance.
        self.transaction_time_preload_signaller = TransactionTimePreloadSignaller()

    def run(self) -> None:
        if get_setting("readonly_standby"):
            self.transaction_time_preload_signaller.run()
            return

        if get_setting("rpki.roa_source"):
            import_timer = int(get_setting("rpki.roa_import_timer"))
            self.run_if_relevant(None, ROAImportRunner, import_timer)

        if get_setting("sources") and any(
            [
                source_settings.get("route_object_preference")
                for source_settings in get_setting("sources").values()
            ]
        ):
            import_timer = int(get_setting("route_object_preference.update_timer"))
            self.run_if_relevant(None, RoutePreferenceUpdateRunner, import_timer)

        if self._check_scopefilter_change():
            self.run_if_relevant(None, ScopeFilterUpdateRunner, 0)

        sources_started = 0
        for source in get_setting("sources", {}).keys():
            if sources_started >= MAX_SIMULTANEOUS_RUNS:
                break
            started_import = False
            started_export = False

            is_mirror = (
                get_setting(f"sources.{source}.import_source")
                or get_setting(f"sources.{source}.nrtm_host")
                or get_setting(f"sources.{source}.nrtm4_client_notification_file_url")
            )
            default_import_timer = (
                DEFAULT_SOURCE_IMPORT_TIMER_NRTM4
                if get_setting(f"sources.{source}.nrtm4_client_initial_public_key")
                else DEFAULT_SOURCE_IMPORT_TIMER
            )
            import_timer = int(get_setting(f"sources.{source}.import_timer", default_import_timer))

            if is_mirror:
                started_import = self.run_if_relevant(source, RPSLMirrorImportUpdateRunner, import_timer)

            runs_rpsl_export = get_setting(f"sources.{source}.export_destination") or get_setting(
                f"sources.{source}.export_destination_unfiltered"
            )
            export_timer = int(get_setting(f"sources.{source}.export_timer", DEFAULT_SOURCE_EXPORT_TIMER))

            if runs_rpsl_export:
                started_export = self.run_if_relevant(source, SourceExportRunner, export_timer)

            runs_nrtm4_server = get_setting(f"sources.{source}.nrtm4_server_private_key")
            if runs_nrtm4_server:
                started_export = self.run_if_relevant(
                    source, NRTM4Server, DEFAULT_SOURCE_EXPORT_TIMER_NRTM4, allow_multiple=True
                )

            if started_import or started_export:
                sources_started += 1

    def _check_scopefilter_change(self) -> bool:
        """
        Check whether the scope filter has changed since last call.
        Always returns True on the first call.
        """
        if not get_setting("scopefilter"):
            return False

        current_prefixes = list(get_setting("scopefilter.prefixes", []))
        current_asns = list(get_setting("scopefilter.asns", []))
        current_exclusions = {
            name
            for name, settings in get_setting("sources", {}).items()
            if settings.get("scopefilter_excluded")
        }

        if any(
            [
                self.previous_scopefilter_prefixes != current_prefixes,
                self.previous_scopefilter_asns != current_asns,
                self.previous_scopefilter_excluded != current_exclusions,
            ]
        ):
            self.previous_scopefilter_prefixes = current_prefixes
            self.previous_scopefilter_asns = current_asns
            self.previous_scopefilter_excluded = current_exclusions
            return True
        return False

    def run_if_relevant(self, source: Optional[str], runner_class, timer: int, allow_multiple=False) -> bool:
        process_name = runner_class.__name__
        if source:
            process_name += f"-{source}"
        current_time = time.time()
        has_expired = (self.last_started_time[process_name] + timer) < current_time
        if not has_expired or (process_name in self.processes and not allow_multiple):
            return False

        kwargs = {}
        msg = f"Started new scheduled process {process_name}"
        if source:
            msg += f" for mirror import/export for {source}"
            kwargs["source"] = source
        logger.debug(msg)

        initiator = runner_class(**kwargs)
        process = ScheduledTaskProcess(runner=initiator, name=process_name)
        self.processes[process_name] = process
        process.start()
        self.last_started_time[process_name] = int(current_time)
        return True

    def terminate_children(self) -> None:  # pragma: no cover
        logger.info("MirrorScheduler terminating children")
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
                logging.error(
                    f"Failed to close {process_name} (pid {process.pid}), possible resource leak: {e}"
                )
            del self.processes[process_name]
            gc_collect_needed = True
        if gc_collect_needed:
            # prevents FIFO pipe leak, see #578
            gc.collect()
