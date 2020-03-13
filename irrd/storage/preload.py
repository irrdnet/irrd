import time
from collections import defaultdict

import logging
import redis
import threading
from setproctitle import setproctitle
from typing import Optional, List, Set, Dict, Union

from irrd.conf import get_setting
from irrd.rpki.status import RPKIStatus
from irrd.utils.process_support import ExceptionLoggingProcess
from .queries import RPSLDatabaseQuery

SENTINEL_HASH_CREATED = b'SENTINEL_HASH_CREATED'
REDIS_ORIGIN_ROUTE4_STORE_KEY = b'irrd-preload-origin-route4'
REDIS_ORIGIN_ROUTE6_STORE_KEY = b'irrd-preload-origin-route6'
REDIS_PRELOAD_RELOAD_CHANNEL = b'irrd-preload-reload-channel'
REDIS_ORIGIN_LIST_SEPARATOR = ','
REDIS_KEY_ORIGIN_SOURCE_SEPARATOR = '_'
MAX_MEMORY_LIFETIME = 60

logger = logging.getLogger(__name__)

"""
The preloader allows information to be preloaded into memory.

For queries that repeat often, or repeatedly retrieve nearly the same,
large data sets, this can improve performance.
"""


class Preloader:
    """
    A preloader object provides access to the preload store.
    It can be used to query the store, or signal that the store
    needs to be updated. This interface can be used from any thread
    or process.
    """
    _loaded_in_memory_time = False

    def __init__(self):
        self._redis_conn = redis.Redis.from_url(get_setting('redis_url'))

    def signal_reload(self, object_classes_changed: Optional[Set[str]]=None) -> None:
        """
        Perform a (re)load.
        Should be called after changes to the DB have been committed.

        This will signal the process running PreloadStoreManager to reload
        the store.

        If object_classes_changed is provided, a reload is only performed
        if those classes are relevant to the data in the preload store.
        """
        relevant_object_classes = {'route', 'route6'}
        if object_classes_changed is not None and not object_classes_changed.intersection(relevant_object_classes):
            return
        self._redis_conn.publish(REDIS_PRELOAD_RELOAD_CHANNEL, 'reload')

    def routes_for_origins(self, origins: Union[List[str], Set[str]], sources: List[str],
                           ip_version: Optional[int] = None) -> Set[str]:
        """
        Retrieve all prefixes (in str format) originating from the provided origins,
        from the given sources.

        Prefixes are guaranteed to be unique. ip_version can be set to 4 or 6
        to restrict responses to IPv4 or IPv6 prefixes. Blocks until the first
        store has been built.
        Origins must be strings in a cleaned format, e.g. AS65537, but not
        AS065537 or as65537.
        """
        if ip_version and ip_version not in [4, 6]:
            raise ValueError(f'Invalid IP version: {ip_version}')
        if not origins or not sources:
            return set()

        if self._loaded_in_memory_time:
            return self._routes_for_origins_memory(origins, sources, ip_version)
        else:
            return self._routes_for_origins_redis(origins, sources, ip_version)

    def _routes_for_origins_memory(self, origins: Union[List[str], Set[str]],
                                   sources: List[str], ip_version: Optional[int]=None) -> Set[str]:
        """
        Implementation of routes_for_origins() when retrieving from memory.
        Updates the in-memory store if it's older than MAX_MEMORY_LIFETIME.
        """
        # The in-memory store is a snapshot, and therefore has a limited lifetime,
        # so that long-running connections don't end up serving very outdated data.
        if time.time() - self._loaded_in_memory_time > MAX_MEMORY_LIFETIME:
            self.load_routes_into_memory()

        prefix_sets: Set[str] = set()
        for origin in origins:
            for source in sources:
                if not ip_version or ip_version == 4:
                    prefix_sets.update(self._origin_route4_store[origin][source])
                if not ip_version or ip_version == 6:
                    prefix_sets.update(self._origin_route6_store[origin][source])

        return prefix_sets

    def _routes_for_origins_redis(self, origins: Union[List[str], Set[str]],
                                  sources: List[str], ip_version: Optional[int]=None) -> Set[str]:
        """
        Implementation of routes_for_origins() when retrieving directly from redis.
        """
        while not self._redis_conn.exists(REDIS_ORIGIN_ROUTE4_STORE_KEY):
            time.sleep(1)  # pragma: no cover

        prefixes: Set[str] = set()
        redis_keys = []
        for source in sources:
            for origin in origins:
                redis_keys.append(f'{source}{REDIS_KEY_ORIGIN_SOURCE_SEPARATOR}{origin}'.encode('ascii'))

        def _load(hmap_key):
            prefixes_for_origins = self._redis_conn.hmget(hmap_key, redis_keys)
            for prefixes_for_origin in prefixes_for_origins:
                if prefixes_for_origin:
                    prefixes.update(prefixes_for_origin.decode('ascii').split(REDIS_ORIGIN_LIST_SEPARATOR))

        if not ip_version or ip_version == 4:
            _load(REDIS_ORIGIN_ROUTE4_STORE_KEY)

        if not ip_version or ip_version == 6:
            _load(REDIS_ORIGIN_ROUTE6_STORE_KEY)

        return prefixes

    def load_routes_into_memory(self):
        """
        Pre-preload all routes into memory. This increases performance for
        routes_for_origins() by up to 100x, but takes about 0.2-0.5s.
        It also means origins are no longer updated as long as this object exists.
        """
        while not self._redis_conn.exists(REDIS_ORIGIN_ROUTE4_STORE_KEY):
            time.sleep(1)  # pragma: no cover
        logger.debug(f'Preloader pre-pre(re)loading routes into memory')

        self._origin_route4_store = defaultdict(lambda: defaultdict(set))
        self._origin_route6_store = defaultdict(lambda: defaultdict(set))

        def _load(redis_key, target):
            for key, routes in self._redis_conn.hgetall(redis_key).items():
                if key == SENTINEL_HASH_CREATED:
                    continue
                source, origin = key.decode('ascii').split(REDIS_KEY_ORIGIN_SOURCE_SEPARATOR)
                target[origin][source].update(routes.decode('ascii').split(REDIS_ORIGIN_LIST_SEPARATOR))

        _load(REDIS_ORIGIN_ROUTE4_STORE_KEY, self._origin_route4_store)
        _load(REDIS_ORIGIN_ROUTE6_STORE_KEY, self._origin_route6_store)

        self._loaded_in_memory_time = time.time()


class PreloadStoreManager(ExceptionLoggingProcess):
    """
    The preload store manager manages the preloaded data store, and ensures
    it is created and updated.
    There should only be one of these per IRRd instance.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._target = self.main
        self._redis_conn = redis.Redis.from_url(get_setting('redis_url'))

    def main(self):
        """
        Main function for the preload manager.

        Monitors a Redis pubsub channel, and triggers a reload when
        a message is received.
        """
        setproctitle('irrd-preload-store-manager')
        logging.info('Starting preload store manager')

        self._clear_existing_data()
        self._pubsub = self._redis_conn.pubsub()

        self._reload_lock = threading.Lock()
        self._threads = []
        self.terminate = False  # Used to exit main() in tests

        while not self.terminate:
            self._perform_reload()
            try:
                self._pubsub.subscribe(REDIS_PRELOAD_RELOAD_CHANNEL)
                for item in self._pubsub.listen():
                    if item['type'] == 'message':
                        logger.debug(f'Reload requested through redis channel')
                        self._perform_reload()
                        if self.terminate:
                            return
            except redis.ConnectionError as rce:  # pragma: no cover
                logger.error(f'Failed redis pubsub connection, attempting reconnect and reload in 5s: {rce}')
                time.sleep(5)

    def _clear_existing_data(self) -> None:
        """
        Clear the existing data. This is done on startup, to ensure no
        queries are being answered with outdated data.
        """
        try:
            self._redis_conn.delete(REDIS_ORIGIN_ROUTE4_STORE_KEY, REDIS_ORIGIN_ROUTE6_STORE_KEY)
        except redis.ConnectionError as rce:  # pragma: no cover
            logger.error(f'Failed to empty preload store due to redis connection error, '
                         f'queries may have outdated results until full reload is completed (max 30s): {rce}')

    def _perform_reload(self) -> None:
        """
        Perform a (re)load.
        Should be called after changes to the DB have been committed.

        This will start a new thread to reload the store. If a thread is
        already running, the new thread will start after the current one
        is done, due to locking.

        If a current thread is running, and a next thread is already
        running as well (waiting for a lock) no action is taken. The
        change that prompted this reload call will already be processed
        by the thread that is currently waiting.
        """
        self._remove_dead_threads()
        if len(self._threads) > 1:
            # Another thread is already scheduled to follow the current one
            return
        thread = PreloadUpdater(self, self._reload_lock)
        thread.start()
        self._threads.append(thread)

    def update_route_store(self, new_origin_route4_store, new_origin_route6_store) -> bool:
        """
        Store the new route information in redis. Returns True on success, False on failure.
        """
        try:
            pipeline = self._redis_conn.pipeline(transaction=True)
            pipeline.delete(REDIS_ORIGIN_ROUTE4_STORE_KEY, REDIS_ORIGIN_ROUTE6_STORE_KEY)
            # The redis store can't store sets, only strings
            origin_route4_str_dict = {k: REDIS_ORIGIN_LIST_SEPARATOR.join(v) for k, v in new_origin_route4_store.items()}
            origin_route6_str_dict = {k: REDIS_ORIGIN_LIST_SEPARATOR.join(v) for k, v in new_origin_route6_store.items()}
            # Redis can't handle empty dicts, but the dict needs to be present
            # in order not to block queries.
            origin_route4_str_dict[SENTINEL_HASH_CREATED] = '1'
            origin_route6_str_dict[SENTINEL_HASH_CREATED] = '1'
            pipeline.hmset(REDIS_ORIGIN_ROUTE4_STORE_KEY, origin_route4_str_dict)
            pipeline.hmset(REDIS_ORIGIN_ROUTE6_STORE_KEY, origin_route6_str_dict)
            pipeline.execute()
            return True

        except redis.ConnectionError as rce:  # pragma: no cover
            logger.error(f'Failed to update preload store due to redis connection error, '
                         f'attempting new reload in 5s: {rce}')
            time.sleep(5)
            self._perform_reload()
            return False

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
    It is started by PreloadStoreManager.
    """
    def __init__(self, preloader, reload_lock, *args, **kwargs):
        self.preloader = preloader
        self.reload_lock = reload_lock
        super().__init__(*args, **kwargs)

    def run(self, mock_database_handler=None) -> None:
        """
        Main thread runner function.

        The reload_lock ensures only a single instance can main at the same
        time, i.e. if two threads are started, one will wait for the other
        to finish.

        After loading the data from the database, sets the two new stores
        on the provided preloader object.
        The lock is then released to allow another thread to start, and
        the store_ready_event set to indicate that the store has been
        loaded at least once, and answers can be provided based on it.

        For tests, mock_database_handler can be used to provide a mock.
        """
        self.reload_lock.acquire()
        logger.debug(f'Starting preload store update from thread {self}')

        new_origin_route4_store: Dict[str, set] = defaultdict(set)
        new_origin_route6_store: Dict[str, set] = defaultdict(set)

        if not mock_database_handler:  # pragma: no cover
            from .database_handler import DatabaseHandler
            dh = DatabaseHandler()
        else:
            dh = mock_database_handler

        q = RPSLDatabaseQuery(column_names=['ip_version', 'ip_first', 'prefix_length', 'asn_first', 'source'], enable_ordering=False)
        q = q.object_classes(['route', 'route6']).rpki_status([RPKIStatus.not_found, RPKIStatus.valid])

        for result in dh.execute_query(q):
            prefix = result['ip_first']
            key = result['source'] + REDIS_KEY_ORIGIN_SOURCE_SEPARATOR + 'AS' + str(result['asn_first'])
            length = result['prefix_length']

            if result['ip_version'] == 4:
                new_origin_route4_store[key].add(f'{prefix}/{length}')
            if result['ip_version'] == 6:
                new_origin_route6_store[key].add(f'{prefix}/{length}')

        dh.close()

        if self.preloader.update_route_store(new_origin_route4_store, new_origin_route6_store):
            logger.info(f'Completed updating preload store from thread {self}')
        self.reload_lock.release()
