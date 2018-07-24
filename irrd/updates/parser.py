import logging
from enum import Enum, unique
from typing import List, Optional, Tuple, Set

from irrd.db.api import DatabaseHandler, RPSLDatabaseQuery
from irrd.rpsl.parser import UnknownRPSLObjectClassException, RPSLObject
from irrd.rpsl.rpsl_objects import rpsl_object_from_text

logger = logging.getLogger(__name__)


@unique
class UpdateRequestType(Enum):
    CREATE = 'create'
    MODIFY = 'modify'
    DELETE = 'delete'
    NO_OP = 'no operation'

@unique
class UpdateRequestStatus(Enum):
    SAVED = 'saved'
    PROCESSING = 'processing'
    ERROR_UNKNOWN_CLASS = 'error: unknown RPSL class'
    ERROR_PARSING = 'errors encountered during object parsing'
    ERROR_AUTH = 'error: update not authorised'
    ERROR_REFERENCE = 'error: reference to object that does not exist'
    ERROR_NON_AUTHORITIVE = 'error: attempt to update object in non-authoritive database'


class ReferenceChecker:
    def __init__(self, database_handler: DatabaseHandler):
        self.database_handler = database_handler
        self._cache: Set[Tuple[str, str, str]] = set()
        self._preloaded: Set[Tuple[str, str, str]] = set()

    def check_reference(self, object_classes: List[str], object_pk: str, source: str):
        if self._check_cache(object_classes, object_pk, source):
            return True

        # TODO: this still fails for route objects, where the PK includes the AS, but the reference does not
        query = RPSLDatabaseQuery().sources([source]).object_classes(object_classes).rpsl_pk(object_pk)
        results = list(self.database_handler.execute_query(query))
        for result in results:
            self._cache.add((result['object_class'], object_pk, source))
        if results:
            return True

        return False

    def _check_cache(self, object_classes: List[str], object_pk: str, source: str):
        for object_class in object_classes:
            if (object_class, object_pk, source) in self._cache:
                return True
            if (object_class, object_pk, source) in self._preloaded:
                return True
        return False

    def preload(self, results):
        self._preloaded = set()
        for request in results:
            self._preloaded.add((request.rpsl_obj_new.rpsl_object_class, request.rpsl_obj_new.pk(),
                                 request.rpsl_obj_new.source()))


class UpdateRequest:
    rpsl_text: str
    rpsl_obj_new: RPSLObject
    rpsl_obj_current: Optional[RPSLObject] = None
    status = UpdateRequestStatus.PROCESSING
    request_type: Optional[UpdateRequestType] = UpdateRequestType.NO_OP

    error_messages: List[str]
    info_messages: List[str]

    passwords: List[str]
    overrides: List[str]
    pgp_signature: Optional[str] = None

    def __init__(self,
                 passed_mntner_cache: Set[str],
                 reference_checker: ReferenceChecker,
                 database_handler: DatabaseHandler,
                 rpsl_text: str,
                 delete_reason=Optional[str]
                 ):
        self.passed_mntner_cache = passed_mntner_cache
        self.reference_checker = reference_checker
        self.database_handler = database_handler
        self.rpsl_text = rpsl_text

        try:
            self.rpsl_obj_new = rpsl_object_from_text(rpsl_text, strict_validation=True)
            if self.rpsl_obj_new.messages.errors():
                self.status = UpdateRequestStatus.ERROR_PARSING
            self.error_messages = self.rpsl_obj_new.messages.errors()
            self.info_messages = self.rpsl_obj_new.messages.infos()

        except UnknownRPSLObjectClassException as exc:
            self.rpsl_obj_new = None
            self.status = UpdateRequestStatus.ERROR_UNKNOWN_CLASS
            self.info_messages = []
            self.error_messages = [str(exc)]

        if self.is_valid():
            query = RPSLDatabaseQuery().sources([self.rpsl_obj_new.source()])
            query = query.object_classes([self.rpsl_obj_new.rpsl_object_class]).rpsl_pk(self.rpsl_obj_new.pk())
            results = list(self.database_handler.execute_query(query))
            if not results:
                self.request_type = UpdateRequestType.CREATE
            elif len(results) == 1:
                self.request_type = UpdateRequestType.MODIFY
                self.rpsl_obj_current = rpsl_object_from_text(results[0]['object_text'])
            else:   # pragma: no cover
                # This should not be possible, as rpsl_pk/source are a composite unique value in the database scheme.
                # Therefore, a query should not be able to affect more than one row.
                affected_pks = ', '.join([r['pk'] for r in results])
                msg = f'attempted to retrieve current version of  object {rpsl_object.pk()}/{source}, but multiple '
                msg += f'objects were affected, internal pks affected: {affected_pks}'
                logger.error(msg)
                raise ValueError(msg)

        if delete_reason:
            self.request_type = UpdateRequestType.DELETE
            if not self.rpsl_obj_current:
                self.status = UpdateRequestStatus.ERROR_PARSING
                self.error_messages.append(f"Can not delete object: no object found for this key in this database.")

    def save(self, database_handler: DatabaseHandler) -> None:
        if self.status != UpdateRequestStatus.PROCESSING:
            raise ValueError("UpdateRequest can only be saved in status PROCESSING")
        if self.request_type == UpdateRequestType.DELETE:
            database_handler.delete_rpsl_object(self.rpsl_obj_current)
        else:
            database_handler.upsert_rpsl_object(self.rpsl_obj_new)
        self.status = UpdateRequestStatus.SAVED

    def is_valid(self):
        return self.status in [UpdateRequestStatus.SAVED, UpdateRequestStatus.PROCESSING]

    def user_report(self) -> str:
        object_class = self.rpsl_obj_new.rpsl_object_class if self.rpsl_obj_new else '(unreadable object class)'
        pk = self.rpsl_obj_new.pk() if self.rpsl_obj_new else '(unreadable object key)'
        status = 'succeeded' if self.is_valid() else 'FAILED'
        request_type = self.request_type.value.title()

        report = f'{request_type} {status}: [{object_class}] {pk}\n'
        if self.info_messages or self.error_messages:
            report += '\n' + self.rpsl_text + '\n'
        report += ''.join([f'ERROR: {e}\n' for e in self.error_messages])
        report += ''.join([f'INFO: {e}\n' for e in self.info_messages])
        return report

    def check_references(self) -> bool:
        if self.request_type == UpdateRequestType.DELETE:
            return True

        references = self.rpsl_obj_new.referred_objects()
        source = self.rpsl_obj_new.source()

        for field_name, objects_referred, object_pks in references:
            for object_pk in object_pks:
                if not self.reference_checker.check_reference(objects_referred, object_pk, source):
                    if len(objects_referred) > 1:
                        objects_referred_str = 'one of ' + ', '.join(objects_referred)
                    else:
                        objects_referred_str = objects_referred[0]
                    self.error_messages.append(f'Object {object_pk} referenced in field {field_name} not found in '
                                               f'database {source} - must reference {objects_referred_str} object')

        if self.error_messages:
            self.status = UpdateRequestStatus.ERROR_REFERENCE
            return False
        return True

    def check_auth(self):
        pass


def parse_update_request(passed_mntner_cache: Set[str],
                        reference_checker: ReferenceChecker,
                        database_handler: DatabaseHandler,
                        object_texts: str
                         ) -> List[UpdateRequest]:
    results = []
    passwords = []
    overrides = []

    object_texts = object_texts.replace('\r', '')
    for object_text in object_texts.split('\n\n'):
        object_text = object_text.strip()

        rpsl_text = ''
        delete_reason = None

        # The attributes password/override/delete are magical attributes
        # and need to be extracted before parsing. Delete refers to a specific
        # object, password/override apply to all included objects.
        for line in object_text.splitlines():
            if line.startswith('password:'):
                password = line.split(':', maxsplit=1)[1].strip()
                passwords.append(password)
            elif line.startswith('override:'):
                override = line.split(':', maxsplit=1)[1].strip()
                overrides.append(override)
            elif line.startswith('delete:'):
                delete_reason = line.split(':', maxsplit=1)[1].strip()
            else:
                rpsl_text += line + '\n'

        if not rpsl_text:
            continue

        results.append(UpdateRequest(passed_mntner_cache, reference_checker, database_handler,
                                     rpsl_text, delete_reason=delete_reason))

    for result in results:
        result.passwords = passwords
        result.overrides = overrides
    return results
