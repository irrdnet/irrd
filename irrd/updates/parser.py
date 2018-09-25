import logging
from typing import List, Optional

from irrd.storage.api import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery
from irrd.rpsl.parser import UnknownRPSLObjectClassException, RPSLObject
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.utils.text import splitline_unicodesafe
from .parser_state import UpdateRequestType, UpdateRequestStatus
from .validators import ReferenceValidator, AuthValidator

logger = logging.getLogger(__name__)


class UpdateRequest:
    """
    An UpdateRequest tracks and processes a request for a single update.
    In this context, an update can be creating, modifying or deleting an
    RPSL object.
    """
    rpsl_text_submitted: str
    rpsl_obj_new: Optional[RPSLObject]
    rpsl_obj_current: Optional[RPSLObject] = None
    status = UpdateRequestStatus.PROCESSING
    request_type: Optional[UpdateRequestType] = None

    error_messages: List[str]
    info_messages: List[str]

    def __init__(self, rpsl_text_submitted: str, database_handler: DatabaseHandler, auth_validator: AuthValidator,
                 reference_validator: ReferenceValidator, delete_reason=Optional[str]) -> None:
        """
        Initialise a new update request for a single RPSL object.

        :param rpsl_text_submitted: the object text
        :param database_handler: a DatabaseHandler instance
        :param auth_validator: a AuthValidator instance, to resolve authentication requirements
        :param reference_validator: a ReferenceValidator instance, to resolve references between objects
        :param delete_reason: a string with the deletion reason, if this was a deletion request

        The rpsl_text passed into this function should be cleaned from any
        meta attributes like delete/override/password. Those should be passed
        into this method as delete_reason, or provided to the AuthValidator.

        The passed_mntner_cache and reference_validator must be shared between
        different instances, to benefit from caching, and to resolve references
        between different objects that are part of the same update.

        NOTE: passed_mntner_cache and keycert_obj_pk are trusted without
        further verification. User provided values must never be passed
        into them without prior validation.
        """
        self.database_handler = database_handler
        self.auth_validator = auth_validator
        self.reference_validator = reference_validator
        self.rpsl_text_submitted = rpsl_text_submitted

        try:
            self.rpsl_obj_new = rpsl_object_from_text(rpsl_text_submitted, strict_validation=True)
            if self.rpsl_obj_new.messages.errors():
                self.status = UpdateRequestStatus.ERROR_PARSING
            self.error_messages = self.rpsl_obj_new.messages.errors()
            self.info_messages = self.rpsl_obj_new.messages.infos()

        except UnknownRPSLObjectClassException as exc:
            self.rpsl_obj_new = None
            self.request_type = None
            self.status = UpdateRequestStatus.ERROR_UNKNOWN_CLASS
            self.info_messages = []
            self.error_messages = [str(exc)]

        if self.is_valid():
            self._retrieve_existing_version()

        if delete_reason:
            self.request_type = UpdateRequestType.DELETE
            if not self.rpsl_obj_current:
                self.status = UpdateRequestStatus.ERROR_PARSING
                self.error_messages.append(f"Can not delete object: no object found for this key in this database.")

    def _retrieve_existing_version(self):
        """
        Retrieve the current version of this object, if any, and store it in rpsl_obj_current.
        Update self.status appropriately.
        """
        query = RPSLDatabaseQuery().sources([self.rpsl_obj_new.source()])
        query = query.object_classes([self.rpsl_obj_new.rpsl_object_class]).rpsl_pk(self.rpsl_obj_new.pk())
        results = list(self.database_handler.execute_query(query))

        if not results:
            self.request_type = UpdateRequestType.CREATE
        elif len(results) == 1:
            self.request_type = UpdateRequestType.MODIFY
            self.rpsl_obj_current = rpsl_object_from_text(results[0]['object_text'], strict_validation=False)
        else:  # pragma: no cover
            # This should not be possible, as rpsl_pk/source are a composite unique value in the database scheme.
            # Therefore, a query should not be able to affect more than one row.
            affected_pks = ', '.join([r['pk'] for r in results])
            msg = f'attempted to retrieve current version of object {self.rpsl_obj_new.pk()}/'
            msg += f'{self.rpsl_obj_new.source()}, but multiple '
            msg += f'objects were found, internal pks found: {affected_pks}'
            logger.error(msg)
            raise ValueError(msg)

    def save(self, database_handler: DatabaseHandler) -> None:
        """Save the update to the database."""
        if self.status != UpdateRequestStatus.PROCESSING or not self.rpsl_obj_new:
            raise ValueError("UpdateRequest can only be saved in status PROCESSING")
        if self.request_type == UpdateRequestType.DELETE and self.rpsl_obj_current is not None:
            database_handler.delete_rpsl_object(self.rpsl_obj_current)
        else:
            database_handler.upsert_rpsl_object(self.rpsl_obj_new)
        self.status = UpdateRequestStatus.SAVED

    def user_report(self) -> str:
        """Produce a string suitable for reporting back status and messages to a human user."""
        object_class = self.rpsl_obj_new.rpsl_object_class if self.rpsl_obj_new else '(unreadable object class)'
        pk = self.rpsl_obj_new.pk() if self.rpsl_obj_new else '(unreadable object key)'
        status = 'succeeded' if self.is_valid() else 'FAILED'
        request_type = self.request_type.value.title() if self.request_type else "Request"

        report = f'{request_type} {status}: [{object_class}] {pk}\n'
        if self.info_messages or self.error_messages:
            report += '\n' + self.rpsl_text_submitted + '\n'
            report += ''.join([f'ERROR: {e}\n' for e in self.error_messages])
            report += ''.join([f'INFO: {e}\n' for e in self.info_messages])
        return report

    def is_valid(self):
        return self.status in [UpdateRequestStatus.SAVED, UpdateRequestStatus.PROCESSING]

    def validate(self) -> bool:
        auth_valid = self._check_auth()
        if not auth_valid:
            return False
        references_valid = self._check_references()
        return references_valid

    def _check_auth(self) -> bool:
        assert self.rpsl_obj_new
        auth_result = self.auth_validator.check_auth(self.rpsl_obj_new, self.rpsl_obj_current)
        self.info_messages += auth_result.info_messages

        if not auth_result.is_valid():
            self.status = UpdateRequestStatus.ERROR_AUTH
            self.error_messages += auth_result.error_messages
            return False
        return True

    def _check_references(self) -> bool:
        """
        Check all references from this object to or from other objects.

        For deletions, only references to the deleted object matter, as
        they now become invalid. For other operations, only the validity
        of references from the new object to others matter.
        """
        if self.request_type == UpdateRequestType.DELETE and self.rpsl_obj_current is not None:
            assert self.rpsl_obj_new
            references_result = self.reference_validator.check_references_from_others(self.rpsl_obj_new)
        else:
            assert self.rpsl_obj_new
            references_result = self.reference_validator.check_references_to_others(self.rpsl_obj_new)
        self.info_messages += references_result.info_messages

        if not references_result.is_valid():
            self.error_messages += references_result.error_messages
            if self.is_valid():  # Only update the status if this object was valid prior, so this is the first failure
                self.status = UpdateRequestStatus.ERROR_REFERENCE
                return False
        return True


def parse_update_requests(requests_text: str,
                          database_handler: DatabaseHandler,
                          auth_validator: AuthValidator,
                          reference_validator: ReferenceValidator,
                          ) -> List[UpdateRequest]:
    """
    Parse update requests, a text of RPSL objects along with metadata like
    passwords or deletion requests.

    :param requests_text: a string containing all update requests
    :param database_handler: a DatabaseHandler instance
        :param auth_validator: a AuthValidator instance, to resolve authentication requirements
    :param reference_validator: a ReferenceValidator instance
    :return: a list of UpdateRequest instances
    """
    results = []
    passwords = []
    overrides = []

    requests_text = requests_text.replace('\r', '')
    for object_text in requests_text.split('\n\n'):
        object_text = object_text.strip()
        if not object_text:
            continue

        rpsl_text = ''
        delete_reason = None

        # The attributes password/override/delete are meta attributes
        # and need to be extracted before parsing. Delete refers to a specific
        # object, password/override apply to all included objects.
        for line in splitline_unicodesafe(object_text):
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

        results.append(UpdateRequest(rpsl_text, database_handler, auth_validator, reference_validator,
                                     delete_reason=delete_reason))

    if auth_validator:
        auth_validator.passwords = passwords
        auth_validator.overrides = overrides
    return results
