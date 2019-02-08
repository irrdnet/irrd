import time

import logging
import queue
import threading
from typing import Callable

from .query_parser import WhoisQueryParser

logger = logging.getLogger(__name__)


class QueryPipelineThread(threading.Thread):
    """
    The query pipeline thread is a thread in charge of running queries.

    IRRd queries need to be run sequentially, and support a large amount of
    queries being sent at once, which then need be answered one by one,
    in the order they were sent.
    """
    def __init__(self, peer_str: str, query_parser: WhoisQueryParser,
                 response_callback: Callable[[bytes], None], lose_connection_callback: Callable[[], None],
                 *args, **kwargs):
        """
        :param peer_str: a string representing the connection's peer
        :param query_parser: an instance of WhoisQueryParser
        :param response_callback: a method to call with a bytes argument,
               when a response must be sent
        :param lose_connection_callback: a method to call when the connection
               should be closed
        """
        self.peer_str = peer_str
        self.query_parser = query_parser
        self.response_callback = response_callback
        self.lose_connection_callback = lose_connection_callback

        self.pipeline: queue.Queue[bytes] = queue.Queue()
        self.ready_to_send_result = threading.Event()
        self.ready_to_send_result.set()
        self.cancelled = False
        self.processing_query = False

        super().__init__(*args, **kwargs)

    def add_query(self, query: bytes) -> None:
        """
        Add a query to the pipeline to be processed.
        Thread safe. Typically called from twisted's main thread,
        when a query is received.
        """
        self.pipeline.put(query, block=False)

    def is_processing_queries(self) -> bool:
        """
        Check whether this thread is processing a query and/or still has
        queries in the pipeline.
        """
        return self.processing_query or not self.pipeline.empty()

    def cancel(self) -> None:
        """
        Schedule this thread for cancellation, possibly with a delay.
        Thread safe. Typically called from twisted's main thread,
        when the connection is closed for whatever reason.
        (Threads can't otherwise be killed easily in Python.)
        """
        self.cancelled = True

    def run(self) -> None:  # pragma: no cover
        """
        Main thread running method. Attempts to process newly added queries
        one by one, until self.cancelled is set.
        """
        while not self.cancelled:
            self._fetch_process_query()

    def _fetch_process_query(self) -> None:
        """
        Attempt to fetch and process a query.

        Returns either when a query was processed, or every 2 seconds if no
        queries are in the queue. This allows the outer loop in run() to check
        whether this thread should be cancelled due to a closed connection.

        See also ready_for_next_result().
        """
        try:
            query_bytes = self.pipeline.get(block=True, timeout=2)
        except queue.Empty:
            return

        self.processing_query = True
        start_time = time.perf_counter()
        query = query_bytes.decode('utf-8', errors='backslashreplace').strip()

        if not query:
            self.processing_query = False
            return

        logger.info(f'{self.peer_str}: processing query: {query}')

        if query.upper() == '!Q':
            self.lose_connection_callback()
            logger.debug(f'{self.peer_str}: closed connection per request')
            self.cancel()
            self.processing_query = False
            return

        response = self.query_parser.handle_query(query)
        response_bytes = response.generate_response().encode('utf-8')

        self.ready_to_send_result.wait()
        self.ready_to_send_result.clear()
        self.response_callback(response_bytes)

        elapsed = time.perf_counter() - start_time
        logger.info(f'{self.peer_str}: sent answer to query, elapsed {elapsed}s, {len(response_bytes)} bytes: {query}')
        self.processing_query = False

    def ready_for_next_result(self) -> None:
        """
        Reset the lock, allowing a new call to response_callback.

        To not overwhelm the Twisted main thread, the response_callback will
        only be called once at first. After that, the lock needs to be cleared
        by calling this method.
        """
        self.ready_to_send_result.set()
