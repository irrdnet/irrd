from collections import defaultdict

import logging
import textwrap
from ordered_set import OrderedSet
from typing import List, Optional, Dict

from irrd.conf import get_setting
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery
from irrd.utils import email
from .parser import parse_change_requests, ChangeRequest
from .parser_state import UpdateRequestStatus, UpdateRequestType
from .validators import ReferenceValidator, AuthValidator

logger = logging.getLogger(__name__)


class ChangeSubmissionHandler:
    """
    The ChangeSubmissionHandler handles the text of one or more requested RPSL changes
    (create, modify or delete), parses, validates and eventually saves
    them. This includes validating references between objects, including
    those part of the same message, and checking authentication.
    """

    def __init__(self, object_texts: str, pgp_fingerprint: str=None, request_meta: Dict[str, Optional[str]]=None) -> None:
        self.database_handler = DatabaseHandler()
        self.request_meta = request_meta if request_meta else {}
        self._pgp_key_id = self._resolve_pgp_key_id(pgp_fingerprint) if pgp_fingerprint else None
        self._handle_object_texts(object_texts)
        self.database_handler.commit()
        self.database_handler.close()

    def _handle_object_texts(self, object_texts: str) -> None:
        reference_validator = ReferenceValidator(self.database_handler)
        auth_validator = AuthValidator(self.database_handler, self._pgp_key_id)
        results = parse_change_requests(object_texts, self.database_handler, auth_validator, reference_validator)

        # When an object references another object, e.g. tech-c referring a person or mntner,
        # an add/update is only valid if those referred objects exist. To complicate matters,
        # the object referred to may be part of this very same submission. For this reason, the
        # reference validator can be provided with all new objects to be added in this submission.
        # However, a possible scenario is that A, B and C are submitted. Object A refers to B,
        # B refers to C, C refers to D and D does not exist - or C fails authentication.
        # At a first scan, A is valid because B exists, B is valid because C exists. C
        # becomes invalid on the first scan, which is why another scan is performed, which
        # will mark B invalid due to the reference to an invalid C, etc. This continues until
        # all references are resolved and repeated scans lead to the same conclusions.
        valid_changes = [r for r in results if r.is_valid()]
        previous_valid_changes: List[ChangeRequest] = []
        loop_count = 0
        loop_max = len(results) + 10

        while valid_changes != previous_valid_changes:
            previous_valid_changes = valid_changes
            reference_validator.preload(valid_changes)
            auth_validator.pre_approve(valid_changes)

            for result in valid_changes:
                result.validate()
            valid_changes = [r for r in results if r.is_valid()]

            loop_count += 1
            if loop_count > loop_max:  # pragma: no cover
                msg = f'Update validity resolver ran an excessive amount of loops, may be stuck, aborting ' \
                      f'processing. Message metadata: {self.request_meta}'
                logger.error(msg)
                raise ValueError(msg)

        for result in results:
            if result.is_valid():
                result.save(self.database_handler)

        self.results = results

    def _resolve_pgp_key_id(self, pgp_fingerprint: str) -> Optional[str]:
        """
        Find a PGP key ID for a given fingerprint.
        This method looks for an actual matching object in the database,
        and then returns the object's PK.
        """
        clean_fingerprint = pgp_fingerprint.replace(' ', '')
        key_id = 'PGPKEY-' + clean_fingerprint[-8:]
        query = RPSLDatabaseQuery().object_classes(['key-cert']).rpsl_pk(key_id)
        results = list(self.database_handler.execute_query(query))

        for result in results:
            if result['parsed_data'].get('fingerpr', '').replace(' ', '') == clean_fingerprint:
                return key_id
        logger.info(f'Message was signed with key {key_id}, but key was not found in the database. Treating message '
                    f'as unsigned. Message metadata: {self.request_meta}')
        return None

    def status(self) -> str:
        """Provide a simple SUCCESS/FAILED string based - former used if all objects were saved."""
        if all([result.status == UpdateRequestStatus.SAVED for result in self.results]):
            return 'SUCCESS'
        return 'FAILED'

    def submitter_report(self) -> str:
        """Produce a human-readable report for the submitter."""
        # flake8: noqa: W293
        successful = [r for r in self.results if r.status == UpdateRequestStatus.SAVED]
        failed = [r for r in self.results if r.status != UpdateRequestStatus.SAVED]
        number_successful_create = len([r for r in successful if r.request_type == UpdateRequestType.CREATE])
        number_successful_modify = len([r for r in successful if r.request_type == UpdateRequestType.MODIFY])
        number_successful_delete = len([r for r in successful if r.request_type == UpdateRequestType.DELETE])
        number_failed_create = len([r for r in failed if r.request_type == UpdateRequestType.CREATE])
        number_failed_modify = len([r for r in failed if r.request_type == UpdateRequestType.MODIFY])
        number_failed_delete = len([r for r in failed if r.request_type == UpdateRequestType.DELETE])

        user_report = self._request_meta_str() + textwrap.dedent(f"""
        SUMMARY OF UPDATE:

        Number of objects found:                  {len(self.results):3}
        Number of objects processed successfully: {len(successful):3}
            Create:      {number_successful_create:3}
            Modify:      {number_successful_modify:3}
            Delete:      {number_successful_delete:3}
        Number of objects processed with errors:  {len(failed):3}
            Create:      {number_failed_create:3}
            Modify:      {number_failed_modify:3}
            Delete:      {number_failed_delete:3}
            
        DETAILED EXPLANATION:
        
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """)
        for result in self.results:
            user_report += '---\n'
            user_report += result.submitter_report()
            user_report += '\n'
        user_report += '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n'
        return user_report

    def send_notification_target_reports(self):
        # First key is e-mail address of recipient, second is UpdateRequestStatus.SAVED
        # or UpdateRequestStatus.ERROR_AUTH
        reports_per_recipient: Dict[str, Dict[UpdateRequestStatus, OrderedSet]] = defaultdict(dict)
        sources: OrderedSet[str] = OrderedSet()

        for result in self.results:
            for target in result.notification_targets():
                if result.status in [UpdateRequestStatus.SAVED, UpdateRequestStatus.ERROR_AUTH]:
                    if result.status not in reports_per_recipient[target]:
                        reports_per_recipient[target][result.status] = OrderedSet()
                    reports_per_recipient[target][result.status].add(result.notification_target_report())
                    sources.add(result.rpsl_obj_new.source())

        sources_str = '/'.join(sources)
        subject = f'Notification of {sources_str} database changes'
        header = get_setting('email.notification_header', '').format(sources_str=sources_str)
        header += '\nThis message is auto-generated.\n'
        header += 'The request was made by email, with the following details:\n'
        header_saved = textwrap.dedent("""
            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            Some objects in which you are referenced have been created,
            deleted or changed.
            
        """)

        header_failed = textwrap.dedent("""
            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            Some objects in which you are referenced were requested
            to be created, deleted or changed, but *failed* the 
            proper authorisation for any of the referenced maintainers.
            
        """)

        for recipient, reports_per_status in reports_per_recipient.items():
            user_report = header + self._request_meta_str()
            if UpdateRequestStatus.ERROR_AUTH in reports_per_status:
                user_report += header_failed
                for report in reports_per_status[UpdateRequestStatus.ERROR_AUTH]:
                    user_report += f'---\n{report}\n'
                user_report += '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n\n'
            if UpdateRequestStatus.SAVED in reports_per_status:
                user_report += header_saved
                for report in reports_per_status[UpdateRequestStatus.SAVED]:
                    user_report += f'---\n{report}\n'
                user_report += '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n\n'

            email.send_email(recipient, subject, user_report)

    def _request_meta_str(self):
        request_meta_str = '\n'.join([f'> {k}: {v}' for k, v in self.request_meta.items() if v])
        if request_meta_str:
            request_meta_str = '\n' + request_meta_str + '\n\n'
        return request_meta_str

