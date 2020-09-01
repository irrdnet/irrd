import logging
from typing import Optional, List

from irrd.rpki.validators import SingleRouteROAValidator
from irrd.rpsl.parser import UnknownRPSLObjectClassException
from irrd.rpsl.rpsl_objects import rpsl_object_from_text, RPSLKeyCert
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import DatabaseOperation, JournalEntryOrigin

logger = logging.getLogger(__name__)


class NRTMOperation:
    """
    NRTMOperation represents a single NRTM operation, i.e. an ADD/DEL
    with a serial number and source, from an NRTM stream.

    Note that the operation may contain an incomplete object, without a
    source attribute, but with other PK attribute(s) present.
    For deletion operations, this is permitted.
    """
    def __init__(self, source: str, operation: DatabaseOperation, serial: int, object_text: str,
                 strict_validation_key_cert: bool, rpki_aware: bool = False,
                 object_class_filter: Optional[List[str]] = None) -> None:
        self.source = source
        self.operation = operation
        self.serial = serial
        self.object_text = object_text
        self.strict_validation_key_cert = strict_validation_key_cert
        self.rpki_aware = rpki_aware
        self.object_class_filter = object_class_filter

    def save(self, database_handler: DatabaseHandler) -> bool:
        default_source = self.source if self.operation == DatabaseOperation.delete else None
        try:
            object_text = self.object_text.strip()
            # If an object turns out to be a key-cert, and strict_import_keycert_objects
            # is set, parse it again with strict validation to load it in the GPG keychain.
            obj = rpsl_object_from_text(object_text, strict_validation=False, default_source=default_source)
            if self.strict_validation_key_cert and obj.__class__ == RPSLKeyCert:
                obj = rpsl_object_from_text(object_text, strict_validation=True, default_source=default_source)

        except UnknownRPSLObjectClassException as exc:
            # Unknown object classes are only logged if they have not been filtered out.
            if not self.object_class_filter or exc.rpsl_object_class.lower() in self.object_class_filter:
                logger.info(f'Ignoring NRTM operation {str(self)}: {exc}')
            return False

        if self.object_class_filter and obj.rpsl_object_class.lower() not in self.object_class_filter:
            return False

        if obj.messages.errors():
            errors = '; '.join(obj.messages.errors())
            logger.critical(f'Parsing errors occurred while processing NRTM operation {str(self)}. '
                            f'This operation is ignored, causing potential data inconsistencies. '
                            f'A new operation for this update, without errors, '
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
            if self.rpki_aware and obj.rpki_relevant and obj.prefix and obj.asn_first:
                roa_validator = SingleRouteROAValidator(database_handler)
                obj.rpki_status = roa_validator.validate_route(obj.prefix, obj.asn_first, obj.source())
            scope_validator = ScopeFilterValidator()
            obj.scopefilter_status, _ = scope_validator.validate_rpsl_object(obj)
            database_handler.upsert_rpsl_object(obj, JournalEntryOrigin.mirror,
                                                source_serial=self.serial)
        elif self.operation == DatabaseOperation.delete:
            database_handler.delete_rpsl_object(rpsl_object=obj, origin=JournalEntryOrigin.mirror,
                                                source_serial=self.serial)

        log = f'Completed NRTM operation {str(self)}/{obj.rpsl_object_class}/{obj.pk()}'
        if self.rpki_aware and obj.rpki_relevant:
            log += f', RPKI status {obj.rpki_status.value}'
        logger.info(log)
        return True

    def __repr__(self):
        return f'{self.source}/{self.serial}/{self.operation.value}'
