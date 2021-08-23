import logging
import random
import signal
import threading
import time
from collections import defaultdict
from typing import Optional, List, Set, Dict, Union

import redis
from setproctitle import setproctitle

from irrd.conf import get_setting
from irrd.rpki.status import RPKIStatus
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.utils.process_support import ExceptionLoggingProcess
from .queries import RPSLDatabaseQuery

SENTINEL_HASH_CREATED = b'SENTINEL_HASH_CREATED'
REDIS_ORIGIN_ROUTE4_STORE_KEY = b'irrd-preload-origin-route4'
REDIS_ORIGIN_ROUTE6_STORE_KEY = b'irrd-preload-origin-route6'
REDIS_PRELOAD_RELOAD_CHANNEL = 'irrd-preload-reload-channel'
REDIS_PRELOAD_COMPLETE_CHANNEL = 'irrd-preload-complete-channel'
REDIS_ORIGIN_LIST_SEPARATOR = ','
REDIS_KEY_ORIGIN_SOURCE_SEPARATOR = '_'
MAX_MEMORY_LIFETIME = 60

logger = logging.getLogger(__name__)

"""
The preloader allows information to be preloaded into memory.

For queries that repeat often, or repeatedly retrieve nearly the same,
large data sets, this can improve performance.
"""


class PersistentPubSubWorkerThread(redis.client.PubSubWorkerThread):  # type: ignore
    def __init__(self, callback, *args, **kwargs):
        self.callback = callback
        self.should_resubscribe = True
        super().__init__(*args, **kwargs)

    def run(self):
        self._running.set()
        while self._running.is_set():
            try:
                if self.should_resubscribe:
                    self.pubsub.subscribe(**{REDIS_PRELOAD_COMPLETE_CHANNEL: self.callback})
                    self.should_resubscribe = False
                self.pubsub.get_message(ignore_subscribe_messages=True, timeout=self.sleep_time)
            except redis.ConnectionError as rce:  # pragma: no cover
                logger.error(f'Failed redis pubsub connection, '
                             f'attempting reconnect and reload in 5s: {rce}')
                time.sleep(5)
                self.should_resubscribe = True
            except Exception as exc:  # pragma: no cover
                logger.error(
                    f'Error while loading in-memory preload, attempting reconnect and reload in 5s,'
                    f'traceback follows: {exc}', exc_info=exc)
                time.sleep(5)
                self.should_resubscribe = True
        self.pubsub.close()  # pragma: no cover


class Preloader:
    """
    A preloader object provides access to the preload store.
    It can be used to query the store, or signal that the store
    needs to be updated. This interface can be used from any thread
    or process.
    """
    _memory_loaded = False

    def __init__(self, enable_queries=True):
        """
        Initialise the preloader.
        If this instance is only used for signalling that the store needs to be
        updated, set enable_queries=False.
        Otherwise, this method starts a background thread that keeps an in-memory store,
        which is automatically updated.
        """
        self._redis_conn = redis.Redis.from_url(get_setting('redis_url'))
        if enable_queries:
            self._pubsub = self._redis_conn.pubsub()
            self._pubsub_thread = PersistentPubSubWorkerThread(
                callback=self._load_routes_into_memory,
                pubsub=self._pubsub,
                sleep_time=5,
                daemon=True
            )
            self._pubsub_thread.start()
            if get_setting('database_readonly'):  # pragma: no cover
                # If this instance is readonly, another IRRd process will be updating
                # the store, and likely has already done so, meaning we can try to load
                # from Redis right away instead of waiting for a signal.
                self._load_routes_into_memory()

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
        if object_classes_changed is None or object_classes_changed.intersection(relevant_object_classes):
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
        This call will block until the preload store is loaded.
        """
        while not self._memory_loaded:
            time.sleep(1)  # pragma: no cover
        if ip_version and ip_version not in [4, 6]:
            raise ValueError(f'Invalid IP version: {ip_version}')
        if not origins or not sources:
            return set()

        prefix_sets: Set[str] = set()
        for source in sources:
            for origin in origins:
                if (not ip_version or ip_version == 4) and source in self._origin_route4_store and origin in self._origin_route4_store[source]:
                    prefix_sets.update(self._origin_route4_store[source][origin].split(REDIS_ORIGIN_LIST_SEPARATOR))
                if (not ip_version or ip_version == 6) and source in self._origin_route6_store and origin in self._origin_route6_store[source]:
                    prefix_sets.update(self._origin_route6_store[source][origin].split(REDIS_ORIGIN_LIST_SEPARATOR))

        return prefix_sets

    def _load_routes_into_memory(self, redis_message=None):
        """
        Update the in-memory store. This is called whenever a
        message is sent to REDIS_PRELOAD_COMPLETE_CHANNEL.
        """
        while not self._redis_conn.exists(REDIS_ORIGIN_ROUTE4_STORE_KEY):
            time.sleep(1)  # pragma: no cover

        # Create a bit of randomness in when workers will update
        time.sleep(random.random())

        new_origin_route4_store = dict()
        new_origin_route6_store = dict()

        def _load(redis_key, target):
            for key, routes in self._redis_conn.hgetall(redis_key).items():
                if key == SENTINEL_HASH_CREATED:
                    continue
                source, origin = key.decode('ascii').split(REDIS_KEY_ORIGIN_SOURCE_SEPARATOR)
                if source not in target:
                    target[source] = dict()
                target[source][origin] = routes.decode('ascii')

        _load(REDIS_ORIGIN_ROUTE4_STORE_KEY, new_origin_route4_store)
        _load(REDIS_ORIGIN_ROUTE6_STORE_KEY, new_origin_route6_store)

        self._origin_route4_store = new_origin_route4_store
        self._origin_route6_store = new_origin_route6_store

        self._memory_loaded = True


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
        try:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
        except ValueError:
            # During tests, this is run from a thread,
            # which does not allow setting signal handlers.
            pass
        logging.info('Starting preload store manager')

        self._clear_existing_data()
        self._pubsub = self._redis_conn.pubsub()

        self._reload_lock = threading.Lock()
        self._threads = []
        self.terminate = False  # Used to exit main() in tests

        while not self.terminate:
            self.perform_reload()
            try:
                self._pubsub.subscribe(REDIS_PRELOAD_RELOAD_CHANNEL)
                for item in self._pubsub.listen():
                    if item['type'] == 'message':
                        logger.debug('Reload requested through redis channel')
                        self.perform_reload()
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

    def perform_reload(self) -> None:
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
            # hmset causes a deprecation warning, but is required for Redis 3 compatibility
            pipeline.hmset(REDIS_ORIGIN_ROUTE4_STORE_KEY, origin_route4_str_dict)
            pipeline.hmset(REDIS_ORIGIN_ROUTE6_STORE_KEY, origin_route6_str_dict)
            pipeline.execute()

            self._redis_conn.publish(REDIS_PRELOAD_COMPLETE_CHANNEL, 'complete')
            return True

        except redis.ConnectionError as rce:  # pragma: no cover
            logger.error(f'Failed to update preload store due to redis connection error, '
                         f'attempting new reload in 5s: {rce}')
            time.sleep(5)
            self.perform_reload()
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

        The reload_lock ensures only a single instance can run at the same
        time, i.e. if two threads are started, one will wait for the other
        to finish.

        For tests, mock_database_handler can be used to provide a mock.
        """
        self.reload_lock.acquire()
        try:
            self.update(mock_database_handler)
        except Exception as exc:
            logger.critical(f'Updating preload store failed, retrying in 5s, '
                            f'traceback follows: {exc}', exc_info=exc)
            time.sleep(5)
            self.preloader.perform_reload()
        finally:
            self.reload_lock.release()

    def update(self, mock_database_handler=None) -> None:
        """
        Update the store.

        After loading the data from the database, sets the two new stores
        on the provided preloader object.
        The lock is then released to allow another thread to start, and
        the store_ready_event set to indicate that the store has been
        loaded at least once, and answers can be provided based on it.
        """
        logger.debug(f'Starting preload store update from thread {self}')

        new_origin_route4_store: Dict[str, set] = defaultdict(set)
        new_origin_route6_store: Dict[str, set] = defaultdict(set)

        if not mock_database_handler:  # pragma: no cover
            from .database_handler import DatabaseHandler
            dh = DatabaseHandler(readonly=True)
        else:
            dh = mock_database_handler

        q = RPSLDatabaseQuery(column_names=['ip_version', 'ip_first', 'prefix_length', 'asn_first', 'source'], enable_ordering=False)
        q = q.object_classes(['route', 'route6']).rpki_status([RPKIStatus.not_found, RPKIStatus.valid])
        q = q.scopefilter_status([ScopeFilterStatus.in_scope])

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
