import logging
from datetime import datetime
from typing import Optional

from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.preload import Preloader

logger = logging.getLogger(__name__)


class TransactionTimePreloadSignaller:
    """
    Signal a preload based on the last transaction time.
    """

    last_time: Optional[datetime] = None

    def run(self):
        self.database_handler = DatabaseHandler()
        self.preloader = Preloader(enable_queries=False)

        try:
            current_time = self.database_handler.timestamp_last_committed_transaction()
            if not self.last_time or self.last_time != current_time:
                logger.debug(
                    f"Signalling preload reload: last transaction completed {current_time}, previous"
                    f" known last transaction was {self.last_time}",
                )
                self.preloader.signal_reload()
                self.last_time = current_time
        except Exception as exc:
            logger.error(
                "An exception occurred while attempting to check transaction timing, signalling preload"
                f" reload anyways: {exc}",
                exc_info=exc,
            )
            try:
                self.preloader.signal_reload()
            except Exception as exc:
                logger.error(
                    f"Failed to send preload reload signal: {exc}",
                    exc_info=exc,
                )
        finally:
            self.database_handler.close()
