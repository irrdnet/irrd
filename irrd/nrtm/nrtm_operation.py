import logging

from irrd.storage.models import DatabaseOperation

logger = logging.getLogger(__name__)


class NRTMOperation:
    def __init__(self, operation: DatabaseOperation, serial: int, object_text: str) -> None:
        self.operation = operation
        self.serial = serial
        self.object_text = object_text

    def __repr__(self):
        return f"{self.operation}/{self.serial}"
