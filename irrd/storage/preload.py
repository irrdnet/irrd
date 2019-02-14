import itertools
import math
from collections import defaultdict

import logging
import threading
from typing import Optional, List, Set

from .database_handler import DatabaseHandler
from .queries import RPSLDatabaseQuery

_preloader = None

logger = logging.getLogger(__name__)


class Preloader:
    """
    The preloader allows information to be preloaded into memory.

    For queries that repeat often, or repeatedly retrieve nearly the same,
    large data sets, this can improve performance.

    The DatabaseHandler calls reload() when data has been changed, added or
    deleted, which may then schedule a thread to update the store, or
    conclude an update is already pending anyways.
    """
    def __init__(self):
        self._origin_route4_store = defaultdict(set)
        self._origin_route6_store = defaultdict(set)

        self._reload_lock = threading.Lock()
        self._threads = []

        self._store_ready_event = threading.Event()
        self.reload()

    def routes_for_origins(self, origins: List[str], ip_version: Optional[int]=None) -> Set[str]:
        """
        Retrieve all prefixes (in str format) originating from the provided origins.

        Prefixes are guaranteed to be unique. ip_version can be set to 4 or 6
        to restrict responses to IPv4 or IPv6 prefixes. Blocks until the first
        store has been built.
        """
        self._store_ready_event.wait()

        if ip_version and ip_version not in [4, 6]:
            raise ValueError(f'Invalid IP version: {ip_version}')

        prefix_sets = list()
        if not ip_version or ip_version == 4:
            prefix_sets = prefix_sets + [self._origin_route4_store[k] for k in origins]
        if not ip_version or ip_version == 6:
            prefix_sets = prefix_sets + [self._origin_route6_store[k] for k in origins]

        return set(itertools.chain.from_iterable(prefix_sets))

    def reload(self, object_classes_changed: Optional[Set[str]]=None) -> None:
        """
        Perform a (re)load.
        Should be called after changes to the DB have been committed

        This will start a new thread to reload the store. If a thread is
        already running, the new thread will start after the current one
        is done, due to locking.

        If a current thread is running, and a next thread is already
        running as well, waiting for a lock, no action is taken. The
        change that prompted this reload call will already be processed
        by the thread that is currently waiting.

        If object_classes_changed is provided, a reload is only performed
        if those classes are relevant to the data in the preload store.
        """
        relevant_object_classes = {'route', 'route6'}
        if object_classes_changed is not None and not object_classes_changed.intersection(relevant_object_classes):
            return
        self._remove_dead_threads()
        if len(self._threads) > 1:
            # Another thread is already scheduled to follow the current one
            return
        thread = PreloadUpdater(self, self._reload_lock, self._store_ready_event)
        thread.start()
        self._threads.append(thread)

    def _remove_dead_threads(self) -> None:
        """
        Remove dead threads from self.threads(),
        for an accurate count of how many are alive.
        """
        for thread in self._threads:
            if not thread.is_alive():
                self._threads.remove(thread)


class PreloadUpdater(threading.Thread):
    """
    PreloadUpdater is a thread that updates the preload store,
    currently for prefixes per origin per address family.
    """
    def __init__(self, preloader, reload_lock, store_ready_event, *args, **kwargs):
        self.preloader = preloader
        self.reload_lock = reload_lock
        self.store_ready_event = store_ready_event
        super().__init__(*args, **kwargs)

    def run(self) -> None:
        logger.debug(f'Preload store update from thread {self} waiting for lock')
        self.reload_lock.acquire()
        logger.debug(f'Starting preload store update from thread {self}')

        new_origin_route4_store = defaultdict(set)
        new_origin_route6_store = defaultdict(set)

        dh = DatabaseHandler()
        q = RPSLDatabaseQuery(column_names=['ip_version', 'ip_first', 'ip_size', 'asn_first'], skip_all_ordening=True)
        q = q.object_classes(['route', 'route6'])

        for result in dh.execute_query(q):
            prefix = result['ip_first']
            key = 'AS' + str(result['asn_first'])

            if result['ip_version'] == 4:
                length = int(32 - math.log2(result['ip_size']))
                new_origin_route4_store[key].add(f'{prefix}/{length}')
            if result['ip_version'] == 6:
                length = int(128 - math.log2(result['ip_size']))
                new_origin_route6_store[key].add(f'{prefix}/{length}')

        dh.close()

        self.preloader._origin_route4_store = new_origin_route4_store
        self.preloader._origin_route6_store = new_origin_route6_store

        logger.info(f'Completed updating preload store from thread {self}, '
                    f'loaded v4 routes for {len(new_origin_route4_store)} ASes, '
                    f'v6 routes for {len(new_origin_route6_store)} ASes')
        self.reload_lock.release()
        self.store_ready_event.set()


def get_preloader():
    global _preloader
    if not _preloader:
        _preloader = Preloader()
    return _preloader
