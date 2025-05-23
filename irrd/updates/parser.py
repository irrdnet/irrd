import datetime
import difflib
import logging
from typing import Optional, Union

import sqlalchemy.orm as saorm

from irrd.conf import get_object_class_filter_for_source, get_setting
from irrd.rpki.status import RPKIStatus
from irrd.rpki.validators import SingleRouteROAValidator
from irrd.rpsl.parser import RPSLObject, UnknownRPSLObjectClassException
from irrd.rpsl.rpsl_objects import RPSLMntner, rpsl_object_from_text
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import JournalEntryOrigin
from irrd.storage.queries import RPSLDatabaseQuery
from irrd.utils.text import remove_auth_hashes, splitline_unicodesafe

from .. import META_KEY_HTTP_CLIENT_IP
from .parser_state import SuspensionRequestType, UpdateRequestStatus, UpdateRequestType
from .suspension import reactivate_for_mntner, suspend_for_mntner
from .validators import (
    AuthValidator,
    ReferenceValidator,
    RulesValidator,
    ValidatorResult,
)

logger = logging.getLogger(__name__)
DATETIME_SENTINEL = datetime.datetime(1970, 1, 1)


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

    error_messages: list[str]
    info_messages: list[str]

    def __init__(
        self,
        rpsl_text_submitted: str,
        database_handler: DatabaseHandler,
        auth_validator: AuthValidator,
        reference_validator: ReferenceValidator,
        delete_reason: Optional[str],
        request_meta: dict[str, Optional[str]],
    ) -> None:
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
        self._auth_result: Optional[ValidatorResult] = None
        self._cached_roa_validity: Optional[bool] = None
        self.roa_validator = SingleRouteROAValidator(database_handler)
        self.scopefilter_validator = ScopeFilterValidator()
        self.rules_validator = RulesValidator(database_handler)
        self.request_meta = request_meta
        self.non_strict_mode = False

        if delete_reason:
            self.request_type = UpdateRequestType.DELETE

        try:
            self.rpsl_obj_new = rpsl_object_from_text(rpsl_text_submitted, strict_validation=True)
            try:
                self.non_strict_mode = get_setting(
                    f"sources.{self.rpsl_obj_new.source()}.authoritative_non_strict_mode_dangerous", False
                )
            except ValueError:
                pass
            if self.non_strict_mode or self.request_type == UpdateRequestType.DELETE:
                self.rpsl_obj_new = rpsl_object_from_text(rpsl_text_submitted, strict_validation=False)

            if self.rpsl_obj_new.messages.errors():
                self.status = UpdateRequestStatus.ERROR_PARSING
            self.error_messages = self.rpsl_obj_new.messages.errors()
            self.info_messages = self.rpsl_obj_new.messages.infos()
            msg = (
                f"{id(self)}: Processing new ChangeRequest for object {self.rpsl_obj_new}: request {id(self)}"
            )
            if self.non_strict_mode:
                msg += " in non-strict mode"
            logger.debug(msg)

        except UnknownRPSLObjectClassException as exc:
            self.rpsl_obj_new = None
            self.request_type = None
            self.status = UpdateRequestStatus.ERROR_UNKNOWN_CLASS
            self.info_messages = []
            self.error_messages = [str(exc)]

        if self.is_valid() and self.rpsl_obj_new:
            source = self.rpsl_obj_new.source()
            if not get_setting(f"sources.{source}.authoritative"):
                logger.debug(f"{id(self)}: change is for non-authoritative source {source}, rejected")
                self.error_messages.append(f"This instance is not authoritative for source {source}")
                self.status = UpdateRequestStatus.ERROR_NON_AUTHORITIVE
                return

            object_class_filter = get_object_class_filter_for_source(source)
            if object_class_filter and self.rpsl_obj_new.rpsl_object_class.lower() not in object_class_filter:
                logger.debug(
                    f"{id(self)}: change is for object class {self.rpsl_obj_new.rpsl_object_class}, not in"
                    " object_class_filter, rejected"
                )
                self.error_messages.append(
                    f"Can not make changes to {self.rpsl_obj_new.rpsl_object_class.lower()} objects in this"
                    " database"
                )
                self.status = UpdateRequestStatus.ERROR_OBJECT_FILTER
                return

            self._retrieve_existing_version()

        if self.request_type == UpdateRequestType.DELETE and not self.rpsl_obj_current:
            self.status = UpdateRequestStatus.ERROR_PARSING
            self.error_messages.append(
                "Can not delete object: no object found for this key in this database."
            )
            logger.debug(
                f"{id(self)}: Request attempts to delete object {self.rpsl_obj_new}, "
                "but no existing object found."
            )

    def _retrieve_existing_version(self):
        """
        Retrieve the current version of this object, if any, and store it in rpsl_obj_current.
        Update self.status appropriately.
        """
        query = RPSLDatabaseQuery().sources([self.rpsl_obj_new.source()])
        query = query.object_classes([self.rpsl_obj_new.rpsl_object_class]).rpsl_pk(self.rpsl_obj_new.pk())
        results = list(self.database_handler.execute_query(query))

        if not results:
            self.request_type = UpdateRequestType.CREATE if not self.request_type else self.request_type
            logger.debug(
                f"{id(self)}: Did not find existing version for object {self.rpsl_obj_new}, request is CREATE"
            )
        elif len(results) == 1:
            self.request_type = UpdateRequestType.MODIFY if not self.request_type else self.request_type
            self.rpsl_obj_current = rpsl_object_from_text(results[0]["object_text"], strict_validation=False)
            logger.debug(
                f"{id(self)}: Retrieved existing version for object "
                f"{self.rpsl_obj_current}, request is MODIFY/DELETE"
            )
        else:  # pragma: no cover
            # This should not be possible, as rpsl_pk/source are a composite unique value in the database scheme.
            # Therefore, a query should not be able to affect more than one row.
            affected_pks = ", ".join([r["pk"] for r in results])
            msg = f"{id(self)}: Attempted to retrieve current version of object {self.rpsl_obj_new.pk()}/"
            msg += f"{self.rpsl_obj_new.source()}, but multiple "
            msg += f"objects were found, internal pks found: {affected_pks}"
            logger.error(msg)
            raise ValueError(msg)

    def save(self) -> None:
        """Save the change to the database."""
        if self.status != UpdateRequestStatus.PROCESSING or not self.rpsl_obj_new:
            raise ValueError("ChangeRequest can only be saved in status PROCESSING")
        if self.request_type == UpdateRequestType.DELETE and self.rpsl_obj_current is not None:
            logger.info(f"{id(self)}: Saving change for {self.rpsl_obj_new}: deleting current object")
            self.database_handler.delete_rpsl_object(
                rpsl_object=self.rpsl_obj_current,
                origin=JournalEntryOrigin.auth_change,
                protect_rpsl_name=True,
            )
        elif self.rpsl_obj_current and self.rpsl_obj_new.render_rpsl_text(
            last_modified=DATETIME_SENTINEL
        ) == self.rpsl_obj_current.render_rpsl_text(last_modified=DATETIME_SENTINEL):
            self.info_messages.append("Submitted object was identical to current object, no change recorded.")
            logger.info(f"{id(self)}: Not saving change for {self.rpsl_obj_new}: identical to current object")
            self.status = UpdateRequestStatus.SAVED
            return  # Do not create auth log entry
        else:
            logger.info(
                f"{id(self)}: Saving change for {self.rpsl_obj_new}: inserting/updating current object"
            )
            self.database_handler.upsert_rpsl_object(self.rpsl_obj_new, JournalEntryOrigin.auth_change)

        if self._auth_result:
            session = saorm.Session(bind=self.database_handler._connection)
            change_log = self._auth_result.to_change_log()
            change_log.from_ip = self.request_meta.get(META_KEY_HTTP_CLIENT_IP, None)
            change_log.from_email = self.request_meta.get("From", None)
            change_log.rpsl_target_request_type = self.request_type
            change_log.rpsl_target_pk = self.rpsl_obj_new.pk()
            change_log.rpsl_target_source = self.rpsl_obj_new.source()
            change_log.rpsl_target_object_class = self.rpsl_obj_new.rpsl_object_class
            if self.rpsl_obj_current:
                change_log.rpsl_target_object_text_old = self.rpsl_obj_current.render_rpsl_text()
            if self.request_type != UpdateRequestType.DELETE:
                change_log.rpsl_target_object_text_new = self.rpsl_obj_new.render_rpsl_text()
            session.add(change_log)
            session.flush()

        self.status = UpdateRequestStatus.SAVED

    def is_valid(self) -> bool:
        return self.status in [UpdateRequestStatus.SAVED, UpdateRequestStatus.PROCESSING]

    def submitter_report_human(self) -> str:
        """Produce a string suitable for reporting back status and messages to the human submitter."""
        status = "succeeded" if self.is_valid() else "FAILED"

        report = (
            f"{self.request_type_str().title()} {status}: [{self.object_class_str()}]"
            f" {self.object_pk_str()}\n"
        )
        if self.info_messages or self.error_messages:
            if not self.rpsl_obj_new or self.error_messages:
                report += "\n" + remove_auth_hashes(self.rpsl_text_submitted) + "\n"
            else:
                report += "\n" + remove_auth_hashes(self.rpsl_obj_new.render_rpsl_text()) + "\n"
            report += "".join([f"ERROR: {e}\n" for e in self.error_messages])
            report += "".join([f"INFO: {e}\n" for e in self.info_messages])
        return report

    def submitter_report_json(self) -> dict[str, Union[None, bool, str, list[str]]]:
        """Produce a dict suitable for reporting back status and messages in JSON."""
        new_object_text = None
        if self.rpsl_obj_new and not self.error_messages:
            new_object_text = self.rpsl_obj_new.render_rpsl_text()
        return {
            "successful": self.is_valid(),
            "type": str(self.request_type.value) if self.request_type else None,
            "object_class": self.object_class_str(),
            "rpsl_pk": self.object_pk_str(),
            "info_messages": self.info_messages,
            "error_messages": self.error_messages,
            "new_object_text": remove_auth_hashes(new_object_text),
            "submitted_object_text": remove_auth_hashes(self.rpsl_text_submitted),
        }

    def notification_target_report(self):
        """
        Produce a string suitable for reporting back status and messages
        to a human notification target, i.e. someone listed
        in notify/upd-to/mnt-nfy.
        """
        if not self.is_valid() and self.status != UpdateRequestStatus.ERROR_AUTH:
            raise ValueError(
                "Notification reports can only be made for changes that are valid "
                "or have failed authorisation."
            )

        status = "succeeded" if self.is_valid() else "FAILED AUTHORISATION"
        report = f"{self.request_type_str().title()} {status} for object below: "
        report += f"[{self.object_class_str()}] {self.object_pk_str()}:\n\n"

        if self.request_type == UpdateRequestType.MODIFY:
            current_text = list(splitline_unicodesafe(self.rpsl_obj_current.render_rpsl_text()))
            new_text = list(splitline_unicodesafe(self.rpsl_obj_new.render_rpsl_text()))
            diff = list(difflib.unified_diff(current_text, new_text, lineterm=""))

            report += "\n".join(diff[2:])  # skip the lines from the diff which would have filenames
            if self.status == UpdateRequestStatus.ERROR_AUTH:
                report += "\n\n*Rejected* new version of this object:\n\n"
            else:
                report += "\n\nNew version of this object:\n\n"

        if self.request_type == UpdateRequestType.DELETE:
            report += self.rpsl_obj_current.render_rpsl_text()
        else:
            report += self.rpsl_obj_new.render_rpsl_text()
        return remove_auth_hashes(report)

    def request_type_str(self) -> str:
        return self.request_type.value if self.request_type else "request"

    def object_pk_str(self) -> str:
        return self.rpsl_obj_new.pk() if self.rpsl_obj_new else "(unreadable object key)"

    def object_class_str(self) -> str:
        return self.rpsl_obj_new.rpsl_object_class if self.rpsl_obj_new else "(unreadable object class)"

    def notification_targets(self) -> set[str]:
        """
        Produce a set of e-mail addresses that should be notified
        about the change to this object.
        May include mntner upd-to or mnt-nfy, and notify of existing object.
        """
        targets: set[str] = set()
        status_qualifies_notification = self.is_valid() or self.status == UpdateRequestStatus.ERROR_AUTH
        used_override = self._auth_result and self._auth_result.auth_method.used_override()
        if used_override or not status_qualifies_notification:
            return targets

        mntner_attr = "upd-to" if self.status == UpdateRequestStatus.ERROR_AUTH else "mnt-nfy"
        if self._auth_result:
            for mntner in self._auth_result.mntners_notify:
                for email in mntner.parsed_data.get(mntner_attr, []):
                    targets.add(email)

        if self.rpsl_obj_current:
            for email in self.rpsl_obj_current.parsed_data.get("notify", []):
                targets.add(email)

        return targets

    def validate(self) -> bool:
        if self.rpsl_obj_new and self.request_type == UpdateRequestType.CREATE:
            if not self.rpsl_obj_new.clean_for_create():
                self.error_messages += self.rpsl_obj_new.messages.errors()
                self.status = UpdateRequestStatus.ERROR_PARSING
                return False
        if self.rpsl_obj_new and self.request_type and self.request_type != UpdateRequestType.DELETE:
            rules_result = self.rules_validator.validate(self.rpsl_obj_new, self.request_type)
            self.info_messages += rules_result.info_messages
            self.error_messages += rules_result.error_messages
            if not rules_result.is_valid():
                logger.debug(f"{id(self)}: Rules check failed: {rules_result.error_messages}")
                self.status = UpdateRequestStatus.ERROR_RULES
                return False

        auth_valid = self._check_auth()
        if not auth_valid:
            return False
        references_valid = self._check_references()
        protected_name_valid = self._check_protected_names()
        rpki_valid = self._check_conflicting_roa()
        scopefilter_valid = self._check_scopefilter()
        return all([references_valid, rpki_valid, scopefilter_valid, protected_name_valid])

    def _check_auth(self) -> bool:
        assert self.rpsl_obj_new
        self._auth_result = self.auth_validator.process_auth(self.rpsl_obj_new, self.rpsl_obj_current)
        self.info_messages += self._auth_result.info_messages

        if not self._auth_result.is_valid():
            self.status = UpdateRequestStatus.ERROR_AUTH
            self.error_messages += self._auth_result.error_messages
            logger.debug(f"{id(self)}: Authentication check failed: {list(self._auth_result.error_messages)}")
            return False

        logger.debug(f"{id(self)}: Authentication check succeeded")
        return True

    def _check_references(self) -> bool:
        """
        Check all references from this object to or from other objects.

        For deletions, only references to the deleted object matter, as
        they now become invalid. For other operations, only the validity
        of references from the new object to others matter.
        """
        if self.non_strict_mode:
            return True
        override = self._auth_result.auth_method.used_override() if self._auth_result else False
        if self.request_type == UpdateRequestType.DELETE and self.rpsl_obj_current is not None:
            assert self.rpsl_obj_new
            references_result = self.reference_validator.check_references_from_others_for_deletion(
                rpsl_obj=self.rpsl_obj_current,
                used_override=override,
            )
        else:
            assert self.rpsl_obj_new
            references_result = self.reference_validator.check_references_to_others(self.rpsl_obj_new)
        self.info_messages += references_result.info_messages

        if not references_result.is_valid():
            self.error_messages += references_result.error_messages
            logger.debug(f"{id(self)}: Reference check failed: {list(references_result.error_messages)}")
            if (
                self.is_valid()
            ):  # Only change the status if this object was valid prior, so this is the first failure
                self.status = UpdateRequestStatus.ERROR_REFERENCE
            return False

        logger.debug(f"{id(self)}: Reference check succeeded")
        return True

    def _check_protected_names(self) -> bool:
        """
        Check whether an object creation uses a protected name (#616).
        """
        if self.request_type == UpdateRequestType.CREATE and self.rpsl_obj_new is not None:
            override = self._auth_result.auth_method.used_override() if self._auth_result else False
            references_result = self.reference_validator.check_protected_name(
                self.rpsl_obj_new, used_override=override
            )
            self.info_messages += references_result.info_messages

            if not references_result.is_valid():
                self.error_messages += references_result.error_messages
                logger.debug(
                    f"{id(self)}: Protected name check failed: {list(references_result.error_messages)}"
                )
                if (
                    self.is_valid()
                ):  # Only change the status if this object was valid prior, so this is the first failure
                    self.status = UpdateRequestStatus.ERROR_PROTECTED_NAME
                return False

            logger.debug(f"{id(self)}: Protected name check succeeded")
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
        if not get_setting("rpki.roa_source") or not self.rpsl_obj_new.is_route:
            return True
        # Deletes are permitted for RPKI-invalids, other operations are not
        if self.request_type == UpdateRequestType.DELETE:
            return True

        assert self.rpsl_obj_new.asn_first
        validation_result = self.roa_validator.validate_route(
            self.rpsl_obj_new.prefix, self.rpsl_obj_new.asn_first, self.rpsl_obj_new.source()
        )
        if validation_result == RPKIStatus.invalid:
            import_timer = get_setting("rpki.roa_import_timer")
            user_message = "RPKI ROAs were found that conflict with this object. "
            user_message += f"(This IRRd refreshes ROAs every {import_timer} seconds.)"
            logger.debug(f"{id(self)}: Conflicting ROAs found")
            if (
                self.is_valid()
            ):  # Only change the status if this object was valid prior, so this is first failure
                self.status = UpdateRequestStatus.ERROR_ROA
            self.error_messages.append(user_message)
            self._cached_roa_validity = False
            return False
        else:
            logger.debug(f"{id(self)}: No conflicting ROAs found")
        self._cached_roa_validity = True
        return True

    def _check_scopefilter(self) -> bool:
        if self.request_type == UpdateRequestType.DELETE or not self.rpsl_obj_new:
            return True
        result, comment = self.scopefilter_validator.validate_rpsl_object(self.rpsl_obj_new)
        if result in [ScopeFilterStatus.out_scope_prefix, ScopeFilterStatus.out_scope_as]:
            user_message = "Contains out of scope information: " + comment
            if self.request_type == UpdateRequestType.CREATE:
                logger.debug(f"{id(self)}: object out of scope: " + comment)
                if (
                    self.is_valid()
                ):  # Only change the status if this object was valid prior, so this is first failure
                    self.status = UpdateRequestStatus.ERROR_SCOPEFILTER
                self.error_messages.append(user_message)
                return False
            elif self.request_type == UpdateRequestType.MODIFY:
                self.info_messages.append(user_message)
        return True


class SuspensionRequest:
    """
    A SuspensionRequest is a special variant of ChangeRequest that
    deals with object suspension/reactivation. Its API matches
    that of ChangeRequest so that ChangeSubmissionHandler
    can use it.
    """

    rpsl_text_submitted: str
    rpsl_obj_new: Optional[RPSLObject]
    status = UpdateRequestStatus.PROCESSING

    error_messages: list[str]
    info_messages: list[str]

    def __init__(
        self,
        rpsl_text_submitted: str,
        database_handler: DatabaseHandler,
        auth_validator: AuthValidator,
        suspension_state=Optional[str],
    ) -> None:
        """
        Initialise a new suspension/reactivation request.

        :param rpsl_text_submitted: the object text
        :param database_handler: a DatabaseHandler instance
        :param auth_validator: a AuthValidator instance, to resolve authentication requirements
        :param suspension_state: the desired suspension state: suspend/reactivate
        """
        self.database_handler = database_handler
        self.auth_validator = auth_validator
        self.rpsl_text_submitted = rpsl_text_submitted
        self.rpsl_obj_new = None
        self.request_type = None
        self.info_messages = []

        try:
            self.request_type = getattr(SuspensionRequestType, suspension_state.upper())
        except AttributeError:
            self.status = UpdateRequestStatus.ERROR_PARSING
            self.error_messages = [f"Unknown suspension type: {suspension_state}"]
            return

        try:
            self.rpsl_obj_new = rpsl_object_from_text(rpsl_text_submitted, strict_validation=False)
            if self.rpsl_obj_new.messages.errors():
                self.status = UpdateRequestStatus.ERROR_PARSING
            self.error_messages = self.rpsl_obj_new.messages.errors()
            self.info_messages = self.rpsl_obj_new.messages.infos()
            logger.debug(
                f"{id(self)}: Processing new SuspensionRequest for object {self.rpsl_obj_new}: request"
                f" {id(self)}"
            )
        except UnknownRPSLObjectClassException as exc:
            self.status = UpdateRequestStatus.ERROR_UNKNOWN_CLASS
            self.error_messages = [str(exc)]

        if self.error_messages or not self.rpsl_obj_new:
            return

        source = self.rpsl_obj_new.source()
        if not get_setting(f"sources.{source}.suspension_enabled"):
            logger.debug(
                f"{id(self)}: source of suspension request is {source}, does not have suspension support"
                " enabled, request rejected"
            )
            self.error_messages.append(
                f"This instance is not authoritative for source {source} or suspension is not enabled"
            )
            self.status = UpdateRequestStatus.ERROR_NON_AUTHORITIVE
            return

        if self.rpsl_obj_new.__class__ != RPSLMntner:
            logger.debug(f"{id(self)}: suspension is for invalid object class, rejected")
            self.error_messages.append("Suspensions/reactivations can only be done on mntner objects")
            self.status = UpdateRequestStatus.ERROR_PARSING
            return

    def save(self) -> None:
        """Save the state change to the database."""
        mntner: RPSLMntner = self.rpsl_obj_new  # type: ignore
        if self.status != UpdateRequestStatus.PROCESSING or not self.rpsl_obj_new:
            raise ValueError("SuspensionRequest can only be saved in status PROCESSING")
        try:
            if self.request_type == SuspensionRequestType.SUSPEND:
                logger.info(f"{id(self)}: Suspending mntner {self.rpsl_obj_new}")
                suspended_objects = suspend_for_mntner(self.database_handler, mntner)
                self.info_messages += [
                    f"Suspended {r['object_class']}/{r['rpsl_pk']}/{r['source']}" for r in suspended_objects
                ]
            elif self.request_type == SuspensionRequestType.REACTIVATE:
                logger.info(f"{id(self)}: Reactivating mntner {self.rpsl_obj_new}")
                (restored, info_messages) = reactivate_for_mntner(self.database_handler, mntner)
                self.info_messages += info_messages
                self.info_messages += [f"Restored {r}" for r in restored]
        except ValueError as ve:
            self.status = UpdateRequestStatus.ERROR_PARSING
            self.error_messages.append(str(ve))
            return

        self.status = UpdateRequestStatus.SAVED

    def is_valid(self) -> bool:
        self.validate()
        return self.status in [UpdateRequestStatus.SAVED, UpdateRequestStatus.PROCESSING]

    def submitter_report_human(self) -> str:
        """Produce a string suitable for reporting back status and messages to the human submitter."""
        status = "succeeded" if self.is_valid() else "FAILED"

        report = (
            f"{self.request_type_str().title()} {status}: [{self.object_class_str()}]"
            f" {self.object_pk_str()}\n"
        )
        if self.info_messages or self.error_messages:
            if self.error_messages:
                report += "\n" + self.rpsl_text_submitted + "\n"
            report += "".join([f"ERROR: {e}\n" for e in self.error_messages])
            report += "".join([f"INFO: {e}\n" for e in self.info_messages])
        return report

    def submitter_report_json(self) -> dict[str, Union[None, bool, str, list[str]]]:
        """Produce a dict suitable for reporting back status and messages in JSON."""
        return {
            "successful": self.is_valid(),
            "type": str(self.request_type.value) if self.request_type else None,
            "object_class": self.object_class_str(),
            "rpsl_pk": self.object_pk_str(),
            "info_messages": self.info_messages,
            "error_messages": self.error_messages,
        }

    def notification_target_report(self):
        # We never message notification targets
        raise NotImplementedError

    def request_type_str(self) -> str:
        return self.request_type.value if self.request_type else "request"

    def object_pk_str(self) -> str:
        return self.rpsl_obj_new.pk() if self.rpsl_obj_new else "(unreadable object key)"

    def object_class_str(self) -> str:
        return self.rpsl_obj_new.rpsl_object_class if self.rpsl_obj_new else "(unreadable object class)"

    def notification_targets(self) -> set[str]:
        # We never message notification targets
        return set()

    def validate(self) -> bool:
        override_method = self.auth_validator.check_override()
        if not override_method:
            self.status = UpdateRequestStatus.ERROR_AUTH
            self.error_messages.append("Invalid authentication: override password invalid or missing")
            logger.debug(f"{id(self)}: Authentication check failed: override did not pass")
            return False
        logger.debug(f"{id(self)}: Authentication check succeeded, override valid")
        return True


def parse_change_requests(
    requests_text: str,
    database_handler: DatabaseHandler,
    auth_validator: AuthValidator,
    reference_validator: ReferenceValidator,
    request_meta: dict[str, Optional[str]],
) -> list[Union[ChangeRequest, SuspensionRequest]]:
    """
    Parse change requests, a text of RPSL objects along with metadata like
    passwords or deletion requests.

    :param requests_text: a string containing all change requests
    :param database_handler: a DatabaseHandler instance
        :param auth_validator: a AuthValidator instance, to resolve authentication requirements
    :param reference_validator: a ReferenceValidator instance
    :return: a list of ChangeRequest instances
    """
    results: list[Union[ChangeRequest, SuspensionRequest]] = []
    passwords = []
    overrides = []
    api_keys = []

    requests_text = requests_text.replace("\r", "")
    for object_text in requests_text.split("\n\n"):
        object_text = object_text.strip()
        if not object_text:
            continue

        rpsl_text = ""
        delete_reason = None
        suspension_state = None

        # The attributes password/override/delete/suspension are meta attributes
        # and need to be extracted before parsing. Delete refers to a specific
        # object, password/override apply to all included objects.
        # Suspension is a special case that does not use the regular ChangeRequest.
        for line in splitline_unicodesafe(object_text):
            if line.startswith("password:"):
                password = line.split(":", maxsplit=1)[1].strip()
                passwords.append(password)
            elif line.startswith("override:"):
                override = line.split(":", maxsplit=1)[1].strip()
                overrides.append(override)
            elif line.startswith("api-key:"):
                api_key = line.split(":", maxsplit=1)[1].strip()
                api_keys.append(api_key)
            elif line.startswith("delete:"):
                delete_reason = line.split(":", maxsplit=1)[1].strip()
            elif line.startswith("suspension:"):
                suspension_state = line.split(":", maxsplit=1)[1].strip()
            else:
                rpsl_text += line + "\n"

        if not rpsl_text:
            continue

        if suspension_state:
            results.append(
                SuspensionRequest(
                    rpsl_text, database_handler, auth_validator, suspension_state=suspension_state
                )
            )
        else:
            results.append(
                ChangeRequest(
                    rpsl_text,
                    database_handler,
                    auth_validator,
                    reference_validator,
                    delete_reason=delete_reason,
                    request_meta=request_meta,
                )
            )

    if auth_validator:
        auth_validator.passwords = passwords
        auth_validator.overrides = overrides
        auth_validator.api_keys = api_keys
    return results
