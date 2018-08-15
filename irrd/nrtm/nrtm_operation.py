import logging

from irrd.rpsl.parser import UnknownRPSLObjectClassException
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.storage.api import DatabaseHandler
from irrd.storage.models import DatabaseOperation

logger = logging.getLogger(__name__)


class NRTMOperation:
    """
    NRTMOperation represents a single NRTM operation, i.e. an ADD/DEL
    with a serial number and source, from an NRTM stream.
    """
    def __init__(self, source: str, operation: DatabaseOperation, serial: int, object_text: str) -> None:
        self.source = source
        self.operation = operation
        self.serial = serial
        self.object_text = object_text

    def save(self, database_handler: DatabaseHandler) -> bool:
        try:
            obj = rpsl_object_from_text(self.object_text.strip(), strict_validation=False)
        except UnknownRPSLObjectClassException as exc:
            logger.warning(f'Ignoring NRTM from {self.source} operation {self.serial}/{self.operation.value}: {exc}')
            return False

        if obj.messages.errors():
            errors = '; '.join(obj.messages.errors())
            logger.critical(f'Parsing errors occurred while processing NRTM from {self.source}, '
                            f'operation {self.serial}/{self.operation.value}. This operation is ignored, '
                            f'causing potential data inconsistencies. A new operation for this update, without errors, '
                            f'will still be processed and cause the inconsistency to be resolved. '
                            f'Parser error messages: {errors}; original object text follows:\n{self.object_text}')
            return False

        if obj.parsed_data.get('source') != self.source:
            logger.critical(f'Incorrect source in NRTM object: stream has source {self.source}, found object with '
                            f'source {obj.source()} in operation {self.serial}/{self.operation.value}/{obj.pk()}. '
                            f'This operation is ignored, causing potential data inconsistencies.')
            return False

        if self.operation == DatabaseOperation.add_or_update:
            database_handler.upsert_rpsl_object(obj, self.serial)
        elif self.operation == DatabaseOperation.delete:
            database_handler.delete_rpsl_object(obj, self.serial)

        return True

    def __repr__(self):
        return f"{self.operation}/{self.serial}"
