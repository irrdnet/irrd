import logging
import random
import signal
import sys
import threading
import time
from collections import defaultdict, namedtuple
from typing import Dict, List, Optional, Set, Union

import redis
from setproctitle import setproctitle

from irrd.conf import get_setting
from irrd.routepref.status import RoutePreferenceStatus
from irrd.rpki.status import RPKIStatus
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.utils.process_support import ExceptionLoggingProcess

from .queries import RPSLDatabaseQuery

SENTINEL_HASH_CREATED = b"SENTINEL_HASH_CREATED"
REDIS_ORIGIN_ROUTE4_STORE_KEY = b"irrd-preload-origin-route4"
REDIS_ORIGIN_ROUTE6_STORE_KEY = b"irrd-preload-origin-route6"
REDIS_AS_SET_STORE_KEY = b"irrd-preload-as-set"
REDIS_ROUTE_SET_STORE_KEY = b"irrd-preload-route-set"
REDIS_PRELOAD_RELOAD_CHANNEL = "irrd-preload-reload-channel"
REDIS_PRELOAD_ALL_MESSAGE = "unknown-classes-changed-preload-all"
REDIS_PRELOAD_COMPLETE_CHANNEL = "irrd-preload-complete-channel"
REDIS_CONTENTS_LIST_SEPARATOR = ","
REDIS_KEY_PK_SOURCE_SEPARATOR = "_"

logger = logging.getLogger(__name__)

"""
The preloader allows information to be preloaded into memory.

For queries that repeat often, or repeatedly retrieve nearly the same,
large data sets, this can improve performance.
"""


SetMembers = namedtuple("SetMembers", ["members", "object_class"])


class PersistentPubSubWorkerThread(redis.client.PubSubWorkerThread):  # type: ignore
    """
    This is a variation of PubSubWorkerThread which persists after an error.
    Rather than terminate, the thread will attempt to reconnect periodically
    until the connection is re-established.
    """

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
                logger.error(f"Failed redis pubsub connection, attempting reconnect and reload in 5s: {rce}")
                time.sleep(5)
                self.should_resubscribe = True
            except Exception as exc:  # pragma: no cover
                logger.error(
                    "Error while loading in-memory preload, attempting reconnect and reload in 5s,"
                    f"traceback follows: {exc}",
                    exc_info=exc,
                )
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
        self._redis_conn = redis.Redis.from_url(get_setting("redis_url"))
        if enable_queries:
            self._pubsub = self._redis_conn.pubsub()
            self._pubsub_thread = PersistentPubSubWorkerThread(
                callback=self._load_preload_data_into_memory, pubsub=self._pubsub, sleep_time=5, daemon=True
            )
            self._pubsub_thread.start()
            if get_setting("readonly_standby"):  # pragma: no cover
                # If this instance is readonly, another IRRd process will be updating
                # the store, and likely has already done so, meaning we can try to load
                # from Redis right away instead of waiting for a signal.
                self._load_preload_data_into_memory()

    def signal_reload(self, object_classes_changed: Optional[Set[str]] = None) -> None:
        """
        Perform a (re)load.
        Should be called after changes to the DB have been committed.

        This will signal the process running PreloadStoreManager to reload
        the store.

        If object_classes_changed is provided, a reload is only performed
        if those classes are relevant to the data in the preload store.
        """
        message = (
            REDIS_CONTENTS_LIST_SEPARATOR.join(object_classes_changed)
            if object_classes_changed
            else REDIS_PRELOAD_ALL_MESSAGE
        )
        self._redis_conn.publish(REDIS_PRELOAD_RELOAD_CHANNEL, message)

    def set_members(self, set_pk: str, sources: List[str], object_classes: List[str]) -> Optional[SetMembers]:
        """
        Retrieve all members of set set_pk in given sources from in memory store.

        Returns the members and the found object class if the set exists, otherwise None.
        Will block until the store is loaded.
        """
        while not self._memory_loaded:
            time.sleep(1)  # pragma: no cover
        if not object_classes or "as-set" in object_classes:
            for source in sources:
                try:
                    members = self._as_set_store[source][set_pk].split(REDIS_CONTENTS_LIST_SEPARATOR)
                    return SetMembers(members, "as-set")
                except KeyError:
                    continue
        if not object_classes or "route-set" in object_classes:
            for source in sources:
                try:
                    members = self._route_set_store[source][set_pk].split(REDIS_CONTENTS_LIST_SEPARATOR)
                    return SetMembers(members, "route-set")
                except KeyError:
                    continue
        return None

    def routes_for_origins(
        self, origins: Union[List[str], Set[str]], sources: List[str], ip_version: Optional[int] = None
    ) -> Set[str]:
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
            raise ValueError(f"Invalid IP version: {ip_version}")
        if not origins or not sources:
            return set()

        prefix_sets: Set[str] = set()
        for source in sources:
            for origin in origins:
                if (
                    (not ip_version or ip_version == 4)
                    and source in self._origin_route4_store
                    and origin in self._origin_route4_store[source]
                ):
                    prefix_sets.update(
                        self._origin_route4_store[source][origin].split(REDIS_CONTENTS_LIST_SEPARATOR)
                    )
                if (
                    (not ip_version or ip_version == 6)
                    and source in self._origin_route6_store
                    and origin in self._origin_route6_store[source]
                ):
                    prefix_sets.update(
                        self._origin_route6_store[source][origin].split(REDIS_CONTENTS_LIST_SEPARATOR)
                    )

        return prefix_sets

    def _load_preload_data_into_memory(self, redis_message=None):
        """
        Update the in-memory store. This is called whenever a
        message is sent to REDIS_PRELOAD_COMPLETE_CHANNEL.
        """
        while not self._redis_conn.exists(REDIS_ORIGIN_ROUTE4_STORE_KEY):
            time.sleep(1)  # pragma: no cover

        # Create a bit of randomness in when workers will update
        if not getattr(sys, "_called_from_test", None):
            time.sleep(random.random())  # pragma: no cover

        new_origin_route4_store = dict()
        new_origin_route6_store = dict()
        new_as_set_store = dict()
        new_route_set_store = dict()

        def _load(redis_key, target):
            for key, routes in self._redis_conn.hgetall(redis_key).items():
                if key == SENTINEL_HASH_CREATED:
                    continue
                source, origin = key.decode("ascii").split(REDIS_KEY_PK_SOURCE_SEPARATOR, 1)
                if source not in target:
                    target[source] = dict()
                target[source][origin] = routes.decode("ascii")

        _load(REDIS_ORIGIN_ROUTE4_STORE_KEY, new_origin_route4_store)
        _load(REDIS_ORIGIN_ROUTE6_STORE_KEY, new_origin_route6_store)
        _load(REDIS_AS_SET_STORE_KEY, new_as_set_store)
        _load(REDIS_ROUTE_SET_STORE_KEY, new_route_set_store)

        self._origin_route4_store = new_origin_route4_store
        self._origin_route6_store = new_origin_route6_store
        self._as_set_store = new_as_set_store
        self._route_set_store = new_route_set_store

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
        self._redis_conn = redis.Redis.from_url(get_setting("redis_url"))

    def main(self):
        """
        Main function for the preload manager.

        Monitors a Redis pubsub channel, and triggers a reload when
        a message is received.
        """
        setproctitle("irrd-preload-store-manager")
        try:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
        except ValueError:
            # During tests, this is run from a thread,
            # which does not allow setting signal handlers.
            pass
        logging.info("Starting preload store manager")

        self._clear_existing_data()
        self._pubsub = self._redis_conn.pubsub()

        self._reload_lock = threading.Lock()
        self._threads = []
        self.terminate = False  # Used to exit main() in tests

        while not self.terminate:
            self.perform_reload(REDIS_PRELOAD_ALL_MESSAGE)
            try:
                self._pubsub.subscribe(REDIS_PRELOAD_RELOAD_CHANNEL)
                for item in self._pubsub.listen():
                    if item["type"] == "message":
                        message = item["data"].decode("ascii")
                        logger.debug(f"Reload requested through redis channel for {message}")
                        self.perform_reload(message)
                        if self.terminate:
                            return
            except redis.ConnectionError as rce:  # pragma: no cover
                logger.error(f"Failed redis pubsub connection, attempting reconnect and reload in 5s: {rce}")
                time.sleep(5)

    def _clear_existing_data(self) -> None:
        """
        Clear the existing data. This is done on startup, to ensure no
        queries are being answered with outdated data.
        """
        try:
            self._redis_conn.delete(
                REDIS_ORIGIN_ROUTE4_STORE_KEY, REDIS_ORIGIN_ROUTE6_STORE_KEY, REDIS_AS_SET_STORE_KEY
            )
        except redis.ConnectionError as rce:  # pragma: no cover
            logger.error(
                "Failed to empty preload store due to redis connection error, "
                f"queries may have outdated results until full reload is completed (max 30s): {rce}"
            )

    def perform_reload(self, message: str) -> None:
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
        classes = set(message.split(REDIS_CONTENTS_LIST_SEPARATOR))
        update_routes = message == REDIS_PRELOAD_ALL_MESSAGE or bool(
            classes.intersection({"route", "route6"})
        )
        update_as_sets = message == REDIS_PRELOAD_ALL_MESSAGE or bool(
            classes.intersection({"as-set", "aut-num"})
        )
        update_route_sets = message == REDIS_PRELOAD_ALL_MESSAGE or bool(
            classes.intersection({"route-set", "route", "route6"})
        )

        if not any([update_routes, update_as_sets, update_route_sets]):
            return

        # Update any queued threads to include the correct objects
        for thread in self._threads:
            if update_routes:
                thread.update_routes = True
            if update_as_sets:
                thread.update_as_sets = True
            if update_route_sets:
                thread.update_route_sets = True

        self._remove_dead_threads()
        if len(self._threads) > 1:
            # Another thread is already scheduled to follow the current one
            return
        thread = PreloadUpdater(
            self, self._reload_lock, update_routes, update_as_sets, update_route_sets, daemon=True
        )
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
            origin_route4_str_dict = {
                k: REDIS_CONTENTS_LIST_SEPARATOR.join(v) for k, v in new_origin_route4_store.items()
            }
            origin_route6_str_dict = {
                k: REDIS_CONTENTS_LIST_SEPARATOR.join(v) for k, v in new_origin_route6_store.items()
            }
            # Redis can't handle empty dicts, but the dict needs to be present
            # in order not to block queries.
            origin_route4_str_dict[SENTINEL_HASH_CREATED] = "1"
            origin_route6_str_dict[SENTINEL_HASH_CREATED] = "1"
            pipeline.hset(REDIS_ORIGIN_ROUTE4_STORE_KEY, mapping=origin_route4_str_dict)
            pipeline.hset(REDIS_ORIGIN_ROUTE6_STORE_KEY, mapping=origin_route6_str_dict)
            pipeline.execute()

            return True

        except redis.ConnectionError as rce:  # pragma: no cover
            return self._handle_preload_update_error(rce)

    def update_as_set_store(self, new_as_set_store) -> bool:
        """
        Store the new as-set information in redis. Returns True on success, False on failure.
        """
        return self.update_set_store(new_as_set_store, REDIS_AS_SET_STORE_KEY)

    def update_route_set_store(self, new_route_set_store) -> bool:
        """
        Store the new route-set information in redis. Returns True on success, False on failure.
        """
        return self.update_set_store(new_route_set_store, REDIS_ROUTE_SET_STORE_KEY)

    def update_set_store(self, new_store, redis_key) -> bool:
        try:
            pipeline = self._redis_conn.pipeline(transaction=True)
            pipeline.delete(redis_key)
            # The redis store can't store sets, only strings
            set_str_dict = {k: REDIS_CONTENTS_LIST_SEPARATOR.join(v) for k, v in new_store.items()}
            # Redis can't handle empty dicts, but the dict needs to be present
            # in order not to block queries.
            set_str_dict[SENTINEL_HASH_CREATED] = "1"
            pipeline.hset(redis_key, mapping=set_str_dict)
            pipeline.execute()
            return True
        except redis.ConnectionError as rce:  # pragma: no cover
            return self._handle_preload_update_error(rce)

    def signal_redis_store_updated(self):
        try:
            self._redis_conn.publish(REDIS_PRELOAD_COMPLETE_CHANNEL, "complete")
            return True

        except redis.ConnectionError as rce:  # pragma: no cover
            return self._handle_preload_update_error(rce)

    def _handle_preload_update_error(self, rce):  # pragma: no cover
        logger.error(
            "Failed to update preload store due to redis connection error, "
            f"attempting new reload in 5s: {rce}"
        )
        time.sleep(5)
        self.perform_reload(REDIS_PRELOAD_ALL_MESSAGE)
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

    def __init__(
        self,
        preloader: PreloadStoreManager,
        reload_lock,
        update_routes,
        update_as_sets,
        update_route_sets,
        *args,
        **kwargs,
    ):
        self.preloader = preloader
        self.reload_lock = reload_lock
        self.update_routes = update_routes
        self.update_as_sets = update_as_sets
        self.update_route_sets = update_route_sets
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
            logger.critical(
                f"Updating preload store failed, retrying in 5s, traceback follows: {exc}", exc_info=exc
            )
            time.sleep(5)
            self.preloader.perform_reload(REDIS_PRELOAD_ALL_MESSAGE)
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
        logger.debug(f"Starting preload store update from thread {self}")

        if not mock_database_handler:  # pragma: no cover
            from .database_handler import DatabaseHandler

            dh = DatabaseHandler(readonly=True)
        else:
            dh = mock_database_handler

        if self.update_routes:
            self._update_routes(dh)
        self._update_all_sets(dh)

        if self.preloader.signal_redis_store_updated():
            logger.info(f"Completed preload store update from thread {self}, notified workers")

        dh.close()

    def _update_routes(self, dh):
        new_origin_route4_store: Dict[str, set] = defaultdict(set)
        new_origin_route6_store: Dict[str, set] = defaultdict(set)

        q = RPSLDatabaseQuery(
            column_names=["ip_version", "ip_first", "prefix_length", "asn_first", "source"],
            enable_ordering=False,
        )
        q = q.object_classes(["route", "route6"]).rpki_status([RPKIStatus.not_found, RPKIStatus.valid])
        q = q.scopefilter_status([ScopeFilterStatus.in_scope])
        q = q.route_preference_status([RoutePreferenceStatus.visible])
        for result in dh.execute_query(q):
            prefix = result["ip_first"]
            key = result["source"] + REDIS_KEY_PK_SOURCE_SEPARATOR + "AS" + str(result["asn_first"])
            length = result["prefix_length"]

            if result["ip_version"] == 4:
                new_origin_route4_store[key].add(f"{prefix}/{length}")
            if result["ip_version"] == 6:
                new_origin_route6_store[key].add(f"{prefix}/{length}")
        if self.preloader.update_route_store(new_origin_route4_store, new_origin_route6_store):
            logger.debug(f"Completed updating preload route store from thread {self}")

    def _update_all_sets(self, dh):
        if self.update_as_sets:
            as_set_store = self._update_set(dh, "as-set", ["aut-num"])
            if self.preloader.update_as_set_store(as_set_store):
                logger.debug(f"Completed updating preload as-set store from thread {self}")

        if self.update_route_sets:
            route_set_store = self._update_set(dh, "route-set", ["route", "route6"])
            if self.preloader.update_route_set_store(route_set_store):
                logger.debug(f"Completed updating preload route-set store from thread {self}")

    def _update_set(self, dh, set_class, member_classes):
        q = (
            RPSLDatabaseQuery(
                column_names=["rpsl_pk", "parsed_data", "source"],
                enable_ordering=False,
            )
            .object_classes([set_class])
            .rpki_status([RPKIStatus.not_found, RPKIStatus.valid])
            .scopefilter_status([ScopeFilterStatus.in_scope])
            .route_preference_status([RoutePreferenceStatus.visible])
        )

        member_store: Dict[str, set] = {}
        mbrs_by_ref_per_set = {}

        for row in dh.execute_query(q):
            key = row["source"] + REDIS_KEY_PK_SOURCE_SEPARATOR + str(row["rpsl_pk"])
            member_store[key] = set(
                row["parsed_data"].get("members", []) + row["parsed_data"].get("mp-members", [])
            )
            mbrs_by_ref = set(row["parsed_data"].get("mbrs-by-ref", []))
            if mbrs_by_ref:
                mbrs_by_ref_per_set[(row["source"], row["rpsl_pk"])] = mbrs_by_ref

        # This query retrieves all member objects with a member-of, because it
        # is much faster than the more specific but much larger alternative.
        q = (
            RPSLDatabaseQuery(
                column_names=["rpsl_pk", "parsed_data", "source", "object_class"],
                enable_ordering=False,
            )
            .lookup_attr("member-of", True)
            .object_classes(member_classes)
            .rpki_status([RPKIStatus.not_found, RPKIStatus.valid])
            .scopefilter_status([ScopeFilterStatus.in_scope])
            .route_preference_status([RoutePreferenceStatus.visible])
        )
        for row in dh.execute_query(q):
            for member_of in row["parsed_data"].get("member-of", []):
                try:
                    expected_mntners = mbrs_by_ref_per_set[(row["source"], member_of)]
                except KeyError:
                    continue

                if "ANY" in expected_mntners or expected_mntners.intersection(
                    set(row["parsed_data"]["mnt-by"])
                ):
                    key = row["source"] + REDIS_KEY_PK_SOURCE_SEPARATOR + member_of
                    member_store[key].add(row["parsed_data"][row["object_class"]])

        return member_store
