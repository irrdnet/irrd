import logging
from multiprocessing import Process

logger = logging.getLogger(__name__)


# Covered by integration tests
class ExceptionLoggingProcess(Process):  # pragma: no cover
    def run(self) -> None:
        try:
            super().run()
        except Exception as e:
            logger.critical(f'Essential IRRd subprocess encountered a fatal error: {e}')
            logger.exception(e)
