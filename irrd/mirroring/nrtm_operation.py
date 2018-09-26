import logging
from typing import Optional, List

from irrd.rpsl.parser import UnknownRPSLObjectClassException
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import DatabaseOperation

logger = logging.getLogger(__name__)


class NRTMOperation:
    """
    NRTMOperation represents a single NRTM operation, i.e. an ADD/DEL
    with a serial number and source, from an NRTM stream.
    """
    def __init__(self, source: str, operation: DatabaseOperation, serial: int, object_text: str,
                 object_class_filter: Optional[List[str]] = None) -> None:
        self.source = source
        self.operation = operation
        self.serial = serial
        self.object_text = object_text
        self.object_class_filter = object_class_filter

    def save(self, database_handler: DatabaseHandler) -> bool:
        try:
            obj = rpsl_object_from_text(self.object_text.strip(), strict_validation=False)
        except UnknownRPSLObjectClassException as exc:
            logger.warning(f'Ignoring NRTM from {self.source} operation {self.serial}/{self.operation.value}: {exc}')
            return False

        if self.object_class_filter and obj.rpsl_object_class.lower() not in self.object_class_filter:
            return False

        if obj.messages.errors():
            errors = '; '.join(obj.messages.errors())
            logger.critical(f'Parsing errors occurred while processing NRTM from {self.source}, '
                            f'operation {self.serial}/{self.operation.value}. This operation is ignored, '
                            f'causing potential data inconsistencies. A new operation for this update, without errors, '
                            f'will still be processed and cause the inconsistency to be resolved. '
                            f'Parser error messages: {errors}; original object text follows:\n{self.object_text}')
            database_handler.record_mirror_error(self.source, f'Parsing errors: {obj.messages.errors()}, '
                                                              f'original object text follows:\n{self.object_text}')
            return False

        if 'source' in obj.parsed_data and obj.parsed_data['source'].upper() != self.source:
            msg = (f'Incorrect source in NRTM object: stream has source {self.source}, found object with '
                   f'source {obj.source()} in operation {self.serial}/{self.operation.value}/{obj.pk()}. '
                   f'This operation is ignored, causing potential data inconsistencies.')
            database_handler.record_mirror_error(self.source, msg)
            logger.critical(msg)
            return False

        if self.operation == DatabaseOperation.add_or_update:
            database_handler.upsert_rpsl_object(obj, self.serial)
        elif self.operation == DatabaseOperation.delete:
            database_handler.delete_rpsl_object(obj, self.serial)

        logger.info(f'Completed NRTM operation in {self.source}: {self.serial}/{self.operation.value}/{obj.pk()}')
        return True

    def __repr__(self):
        return f"{self.source}/{self.serial}/{self.operation.value}"
