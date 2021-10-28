import ctypes
import logging
import os
import signal
from multiprocessing import Process

logger = logging.getLogger(__name__)


# Covered by integration tests


class ExceptionLoggingProcess(Process):  # pragma: no cover
    def run(self) -> None:
        try:
            super().run()
        except Exception as e:
            logger.critical(f'Essential IRRd subprocess encountered a fatal error, '
                            f'traceback follows, shutting down: {e}', exc_info=e)
            os.kill(os.getppid(), signal.SIGTERM)


def memory_trim():  # pragma: no cover
    # See https://github.com/irrdnet/irrd/issues/571
    try:
        ctypes.CDLL(None).malloc_trim(0)
    except Exception:
        pass
