import difflib
import logging
from typing import List, Optional, Set, Dict, Union

from irrd.conf import get_setting
from irrd.rpki.status import RPKIStatus
from irrd.rpki.validators import SingleRouteROAValidator
from irrd.rpsl.parser import UnknownRPSLObjectClassException, RPSLObject
from irrd.rpsl.rpsl_objects import rpsl_object_from_text, RPSLMntner
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import JournalEntryOrigin
from irrd.storage.queries import RPSLDatabaseQuery
from irrd.utils.text import splitline_unicodesafe
from .parser_state import UpdateRequestType, UpdateRequestStatus
from .validators import ReferenceValidator, AuthValidator

logger = logging.getLogger(__name__)


class ChangeRequest:
    """
    A ChangeRequest tracks and processes a request for a single change.
    In this context, a change can be creating, modifying or deleting an
    RPSL object.
    """
    rpsl_text_submitted: str
    rpsl_obj_new: Optional[RPSLObject]
    rpsl_obj_current: Optional[RPSLObject] = None
    status = UpdateRequestStatus.PROCESSING
    request_type: Optional[UpdateRequestType] = None
    mntners_notify: List[RPSLMntner]

    error_messages: List[str]
    info_messages: List[str]

    def __init__(self, rpsl_text_submitted: str, database_handler: DatabaseHandler, auth_validator: AuthValidator,
                 reference_validator: ReferenceValidator, delete_reason=Optional[str]) -> None:
        """
        Initialise a new change request for a single RPSL object.

        :param rpsl_text_submitted: the object text
        :param database_handler: a DatabaseHandler instance
        :param auth_validator: a AuthValidator instance, to resolve authentication requirements
        :param reference_validator: a ReferenceValidator instance, to resolve references between objects
        :param delete_reason: a string with the deletion reason, if this was a deletion request

        The rpsl_text passed into this function should be cleaned from any
        meta attributes like delete/override/password. Those should be passed
        into this method as delete_reason, or provided to the AuthValidator.

        The auth_validator and reference_validator must be shared between
        different instances, to benefit from caching, and to resolve references
        between different objects that are part of the same submission with
        possibly multiple changes.
        """
        self.database_handler = database_handler
        self.auth_validator = auth_validator
        self.reference_validator = reference_validator
        self.rpsl_text_submitted = rpsl_text_submitted
        self.mntners_notify = []
        self.used_override = False
        self._cached_roa_validity: Optional[bool] = None
        self.roa_validator = SingleRouteROAValidator(database_handler)
        self.scopefilter_validator = ScopeFilterValidator()

        try:
            self.rpsl_obj_new = rpsl_object_from_text(rpsl_text_submitted, strict_validation=True)
            if self.rpsl_obj_new.messages.errors():
                self.status = UpdateRequestStatus.ERROR_PARSING
            self.error_messages = self.rpsl_obj_new.messages.errors()
            self.info_messages = self.rpsl_obj_new.messages.infos()
            logger.debug(f'{id(self)}: Processing new ChangeRequest for object {self.rpsl_obj_new}: request {id(self)}')

        except UnknownRPSLObjectClassException as exc:
            self.rpsl_obj_new = None
            self.request_type = None
            self.status = UpdateRequestStatus.ERROR_UNKNOWN_CLASS
            self.info_messages = []
            self.error_messages = [str(exc)]

        if self.is_valid() and self.rpsl_obj_new:
            source = self.rpsl_obj_new.source()
            if not get_setting(f'sources.{source}.authoritative'):
                logger.debug(f'{id(self)}: change is for non-authoritative source {source}, rejected')
                self.error_messages.append(f'This instance is not authoritative for source {source}')
                self.status = UpdateRequestStatus.ERROR_NON_AUTHORITIVE
                return

            self._retrieve_existing_version()

        if delete_reason:
            self.request_type = UpdateRequestType.DELETE
            if not self.rpsl_obj_current:
                self.status = UpdateRequestStatus.ERROR_PARSING
                self.error_messages.append('Can not delete object: no object found for this key in this database.')
                logger.debug(f'{id(self)}: Request attempts to delete object {self.rpsl_obj_new}, '
                             f'but no existing object found.')

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
            logger.debug(f'{id(self)}: Did not find existing version for object {self.rpsl_obj_new}, request is CREATE')
        elif len(results) == 1:
            self.request_type = UpdateRequestType.MODIFY
            self.rpsl_obj_current = rpsl_object_from_text(results[0]['object_text'], strict_validation=False)
            logger.debug(f'{id(self)}: Retrieved existing version for object '
                         f'{self.rpsl_obj_current}, request is MODIFY/DELETE')
        else:  # pragma: no cover
            # This should not be possible, as rpsl_pk/source are a composite unique value in the database scheme.
            # Therefore, a query should not be able to affect more than one row.
            affected_pks = ', '.join([r['pk'] for r in results])
            msg = f'{id(self)}: Attempted to retrieve current version of object {self.rpsl_obj_new.pk()}/'
            msg += f'{self.rpsl_obj_new.source()}, but multiple '
            msg += f'objects were found, internal pks found: {affected_pks}'
            logger.error(msg)
            raise ValueError(msg)

    def save(self, database_handler: DatabaseHandler) -> None:
        """Save the change to the database."""
        if self.status != UpdateRequestStatus.PROCESSING or not self.rpsl_obj_new:
            raise ValueError('ChangeRequest can only be saved in status PROCESSING')
        if self.request_type == UpdateRequestType.DELETE and self.rpsl_obj_current is not None:
            logger.info(f'{id(self)}: Saving change for {self.rpsl_obj_new}: deleting current object')
            database_handler.delete_rpsl_object(rpsl_object=self.rpsl_obj_current, origin=JournalEntryOrigin.auth_change)
        else:
            logger.info(f'{id(self)}: Saving change for {self.rpsl_obj_new}: inserting/updating current object')
            database_handler.upsert_rpsl_object(self.rpsl_obj_new, JournalEntryOrigin.auth_change)
        self.status = UpdateRequestStatus.SAVED

    def is_valid(self) -> bool:
        return self.status in [UpdateRequestStatus.SAVED, UpdateRequestStatus.PROCESSING]

    def submitter_report_human(self) -> str:
        """Produce a string suitable for reporting back status and messages to the human submitter."""
        status = 'succeeded' if self.is_valid() else 'FAILED'

        report = f'{self.request_type_str().title()} {status}: [{self.object_class_str()}] {self.object_pk_str()}\n'
        if self.info_messages or self.error_messages:
            if not self.rpsl_obj_new or self.error_messages:
                report += '\n' + self.rpsl_text_submitted + '\n'
            else:
                report += '\n' + self.rpsl_obj_new.render_rpsl_text() + '\n'
            report += ''.join([f'ERROR: {e}\n' for e in self.error_messages])
            report += ''.join([f'INFO: {e}\n' for e in self.info_messages])
        return report

    def submitter_report_json(self) -> Dict[str, Union[None, bool, str, List[str]]]:
        """Produce a dict suitable for reporting back status and messages in JSON."""
        new_object_text = None
        if self.rpsl_obj_new and not self.error_messages:
            new_object_text = self.rpsl_obj_new.render_rpsl_text()
        return {
            'successful': self.is_valid(),
            'type': str(self.request_type.value) if self.request_type else None,
            'object_class': self.object_class_str(),
            'rpsl_pk': self.object_pk_str(),
            'info_messages': self.info_messages,
            'error_messages': self.error_messages,
            'new_object_text': new_object_text,
            'submitted_object_text': self.rpsl_text_submitted,
        }

    def notification_target_report(self):
        """
        Produce a string suitable for reporting back status and messages
        to a human notification target, i.e. someone listed
        in notify/upd-to/mnt-nfy.
        """
        if not self.is_valid() and self.status != UpdateRequestStatus.ERROR_AUTH:
            raise ValueError('Notification reports can only be made for changes that are valid '
                             'or have failed authorisation.')

        status = 'succeeded' if self.is_valid() else 'FAILED AUTHORISATION'
        report = f'{self.request_type_str().title()} {status} for object below: '
        report += f'[{self.object_class_str()}] {self.object_pk_str()}:\n\n'

        if self.request_type == UpdateRequestType.MODIFY:
            current_text = list(splitline_unicodesafe(self.rpsl_obj_current.render_rpsl_text()))
            new_text = list(splitline_unicodesafe(self.rpsl_obj_new.render_rpsl_text()))
            diff = list(difflib.unified_diff(current_text, new_text, lineterm=''))

            report += '\n'.join(diff[2:])  # skip the lines from the diff which would have filenames
            if self.status == UpdateRequestStatus.ERROR_AUTH:
                report += '\n\n*Rejected* new version of this object:\n\n'
            else:
                report += '\n\nNew version of this object:\n\n'

        if self.request_type == UpdateRequestType.DELETE:
            report += self.rpsl_obj_current.render_rpsl_text()
        else:
            report += self.rpsl_obj_new.render_rpsl_text()
        return report

    def request_type_str(self) -> str:
        return self.request_type.value if self.request_type else 'request'

    def object_pk_str(self) -> str:
        return self.rpsl_obj_new.pk() if self.rpsl_obj_new else '(unreadable object key)'

    def object_class_str(self) -> str:
        return self.rpsl_obj_new.rpsl_object_class if self.rpsl_obj_new else '(unreadable object class)'

    def notification_targets(self) -> Set[str]:
        """
        Produce a set of e-mail addresses that should be notified
        about the change to this object.
        May include mntner upd-to or mnt-nfy, and notify of existing object.
        """
        targets: Set[str] = set()
        status_qualifies_notification = self.is_valid() or self.status == UpdateRequestStatus.ERROR_AUTH
        if self.used_override or not status_qualifies_notification:
            return targets

        mntner_attr = 'upd-to' if self.status == UpdateRequestStatus.ERROR_AUTH else 'mnt-nfy'
        for mntner in self.mntners_notify:
            for email in mntner.parsed_data.get(mntner_attr, []):
                targets.add(email)

        if self.rpsl_obj_current:
            for email in self.rpsl_obj_current.parsed_data.get('notify', []):
                targets.add(email)

        return targets

    def validate(self) -> bool:
        if self.rpsl_obj_new and self.request_type == UpdateRequestType.CREATE:
            if not self.rpsl_obj_new.clean_for_create():
                self.error_messages += self.rpsl_obj_new.messages.errors()
                self.status = UpdateRequestStatus.ERROR_PARSING
                return False
        auth_valid = self._check_auth()
        if not auth_valid:
            return False
        references_valid = self._check_references()
        rpki_valid = self._check_conflicting_roa()
        scopefilter_valid = self._check_scopefilter()
        return references_valid and rpki_valid and scopefilter_valid

    def _check_auth(self) -> bool:
        assert self.rpsl_obj_new
        auth_result = self.auth_validator.process_auth(self.rpsl_obj_new, self.rpsl_obj_current)
        self.info_messages += auth_result.info_messages
        self.mntners_notify = auth_result.mntners_notify

        if not auth_result.is_valid():
            self.status = UpdateRequestStatus.ERROR_AUTH
            self.error_messages += auth_result.error_messages
            logger.debug(f'{id(self)}: Authentication check failed: {list(auth_result.error_messages)}')
            return False

        self.used_override = auth_result.used_override

        logger.debug(f'{id(self)}: Authentication check succeeded')
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
            references_result = self.reference_validator.check_references_from_others(self.rpsl_obj_current)
        else:
            assert self.rpsl_obj_new
            references_result = self.reference_validator.check_references_to_others(self.rpsl_obj_new)
        self.info_messages += references_result.info_messages

        if not references_result.is_valid():
            self.error_messages += references_result.error_messages
            logger.debug(f'{id(self)}: Reference check failed: {list(references_result.error_messages)}')
            if self.is_valid():  # Only change the status if this object was valid prior, so this is the first failure
                self.status = UpdateRequestStatus.ERROR_REFERENCE
            return False

        logger.debug(f'{id(self)}: Reference check succeeded')
        return True

    def _check_conflicting_roa(self) -> bool:
        """
        Check whether there are any conflicting ROAs with the new object.
        Result is cached, as validate() may be called multiple times,
        but the result of this check will not change. Always returns
        True when not in RPKI-aware mode.
        """
        assert self.rpsl_obj_new
        if self._cached_roa_validity is not None:
            return self._cached_roa_validity
        if not get_setting('rpki.roa_source') or not self.rpsl_obj_new.rpki_relevant:
            return True
        # Deletes are permitted for RPKI-invalids, other operations are not
        if self.request_type == UpdateRequestType.DELETE:
            return True

        assert self.rpsl_obj_new.asn_first
        validation_result = self.roa_validator.validate_route(
            self.rpsl_obj_new.prefix, self.rpsl_obj_new.asn_first, self.rpsl_obj_new.source()
        )
        if validation_result == RPKIStatus.invalid:
            import_timer = get_setting('rpki.roa_import_timer')
            user_message = 'RPKI ROAs were found that conflict with this object. '
            user_message += f'(This IRRd refreshes ROAs every {import_timer} seconds.)'
            logger.debug(f'{id(self)}: Conflicting ROAs found')
            if self.is_valid():  # Only change the status if this object was valid prior, so this is first failure
                self.status = UpdateRequestStatus.ERROR_ROA
            self.error_messages.append(user_message)
            self._cached_roa_validity = False
            return False
        else:
            logger.debug(f'{id(self)}: No conflicting ROAs found')
        self._cached_roa_validity = True
        return True

    def _check_scopefilter(self) -> bool:
        if self.request_type == UpdateRequestType.DELETE or not self.rpsl_obj_new:
            return True
        result, comment = self.scopefilter_validator.validate_rpsl_object(self.rpsl_obj_new)
        if result in [ScopeFilterStatus.out_scope_prefix, ScopeFilterStatus.out_scope_as]:
            user_message = 'Contains out of scope information: ' + comment
            if self.request_type == UpdateRequestType.CREATE:
                logger.debug(f'{id(self)}: object out of scope: ' + comment)
                if self.is_valid():  # Only change the status if this object was valid prior, so this is first failure
                    self.status = UpdateRequestStatus.ERROR_SCOPEFILTER
                self.error_messages.append(user_message)
                return False
            elif self.request_type == UpdateRequestType.MODIFY:
                self.info_messages.append(user_message)
        return True


def parse_change_requests(requests_text: str,
                          database_handler: DatabaseHandler,
                          auth_validator: AuthValidator,
                          reference_validator: ReferenceValidator,
                          ) -> List[ChangeRequest]:
    """
    Parse change requests, a text of RPSL objects along with metadata like
    passwords or deletion requests.

    :param requests_text: a string containing all change requests
    :param database_handler: a DatabaseHandler instance
        :param auth_validator: a AuthValidator instance, to resolve authentication requirements
    :param reference_validator: a ReferenceValidator instance
    :return: a list of ChangeRequest instances
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

        results.append(ChangeRequest(rpsl_text, database_handler, auth_validator, reference_validator,
                                     delete_reason=delete_reason))

    if auth_validator:
        auth_validator.passwords = passwords
        auth_validator.overrides = overrides
    return results
