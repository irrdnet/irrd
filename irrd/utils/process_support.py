import ctypes
import logging
import os
import signal
import sys
import threading
import traceback
from multiprocessing import Process

from setproctitle import getproctitle

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


def set_traceback_handler():
    def sigusr1_handler(signal, frame):
        thread_names = {th.ident: th.name for th in threading.enumerate()}
        code = [f"Traceback follows for all threads of process {os.getpid()} ({getproctitle()}):"]
        for thread_id, stack in sys._current_frames().items():
            thread_name = thread_names.get(thread_id, "")
            code.append(f"\n## Thread: {thread_name}({thread_id}) ##\n")
            code += traceback.format_list(traceback.extract_stack(stack))
        logger.info("".join(code))

    signal.signal(signal.SIGUSR1, sigusr1_handler)
