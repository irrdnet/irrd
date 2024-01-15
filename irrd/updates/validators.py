import functools
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple, Union

import sqlalchemy.orm as saorm
from IPy import IP
from ordered_set import OrderedSet
from passlib.hash import bcrypt, md5_crypt

from irrd.conf import RPSL_MNTNER_AUTH_INTERNAL, get_setting
from irrd.rpsl.parser import RPSLObject
from irrd.rpsl.rpsl_objects import (
    PROTECTED_NAME_OBJECT_CLASSES,
    RPSLMntner,
    RPSLSet,
    rpsl_object_from_text,
)
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import (
    AuthApiToken,
    AuthMntner,
    AuthoritativeChangeOrigin,
    AuthUser,
    ChangeLog,
)
from irrd.storage.queries import (
    ProtectedRPSLNameQuery,
    RPSLDatabaseQuery,
    RPSLDatabaseSuspendedQuery,
)

from .parser_state import AuthMethod, RPSLSetAutnumAuthenticationMode, UpdateRequestType

if TYPE_CHECKING:  # pragma: no cover
    # http://mypy.readthedocs.io/en/latest/common_issues.html#import-cycles
    from .parser import ChangeRequest, SuspensionRequest  # noqa: F401

logger = logging.getLogger(__name__)


@dataclass
class ValidatorResult:
    # OrderedSet has some obscure issues with mypy
    error_messages: Set[str] = field(default_factory=OrderedSet)  # type: ignore
    info_messages: Set[str] = field(default_factory=OrderedSet)  # type: ignore
    # mntners that may need to be notified
    mntners_notify: List[RPSLMntner] = field(default_factory=list)
    # Details of how authentication was provided
    auth_method: AuthMethod = AuthMethod.NONE
    auth_through_mntner: Optional[str] = None
    auth_through_internal_mntner: Optional[AuthMntner] = None
    auth_through_api_key: Optional[AuthApiToken] = None
    auth_through_internal_user: Optional[AuthUser] = None

    def is_valid(self):
        return len(self.error_messages) == 0

    def to_change_log(self) -> ChangeLog:
        kwargs: Dict[str, Union[str, bool, None]] = {
            "auth_through_rpsl_mntner_pk": self.auth_through_mntner,
            "auth_by_rpsl_mntner_password": self.auth_method == AuthMethod.MNTNER_PASSWORD,
            "auth_by_rpsl_mntner_pgp_key": self.auth_method == AuthMethod.MNTNER_PGP_KEY,
            "auth_by_override": self.auth_method in [
                AuthMethod.OVERRIDE_PASSWORD,
                AuthMethod.OVERRIDE_INTERNAL_AUTH,
            ],
        }
        if self.auth_through_internal_user:
            kwargs["auth_by_user_id"] = str(self.auth_through_internal_user.pk)
            kwargs["auth_by_user_email"] = self.auth_through_internal_user.email
        if self.auth_through_api_key:
            kwargs["auth_by_api_key_id"] = str(self.auth_through_api_key.pk)
            kwargs["auth_by_api_key_id_fixed"] = str(self.auth_through_api_key.pk)
        if self.auth_through_internal_mntner:
            kwargs["auth_through_mntner_id"] = str(self.auth_through_internal_mntner.pk)
        return ChangeLog(**kwargs)


@dataclass
class MntnerCheckResult:
    valid: bool
    associated_mntners: List[RPSLMntner] = field(default_factory=list)
    auth_method: AuthMethod = AuthMethod.NONE
    mntner_pk: Optional[str] = None
    auth_mntner: Optional[AuthMntner] = None
    api_key: Optional[AuthApiToken] = None


class ReferenceValidator:
    """
    The ReferenceValidator validates references to other objects, given
    their expected object_class, source and PK.

    Sometimes updates are made to objects, referencing objects newly created
    in the same update message. To handle this, the validator can be preloaded
    with objects that should be considered valid.
    """

    def __init__(self, database_handler: DatabaseHandler) -> None:
        self.database_handler = database_handler
        self._cache: Set[Tuple[str, str, str]] = set()
        self._preloaded_new: Set[Tuple[str, str, str]] = set()
        self._preloaded_deleted: Set[Tuple[str, str, str]] = set()

    def preload(self, results: List[Union["ChangeRequest", "SuspensionRequest"]]) -> None:
        """Preload an iterable of ChangeRequest objects to be considered valid, or to be considered deleted."""
        self._preloaded_new = set()
        self._preloaded_deleted = set()
        for request in results:
            assert request.rpsl_obj_new
            if request.request_type == UpdateRequestType.DELETE:
                self._preloaded_deleted.add(
                    (
                        request.rpsl_obj_new.rpsl_object_class,
                        request.rpsl_obj_new.pk(),
                        request.rpsl_obj_new.source(),
                    )
                )
            elif request.request_type in [UpdateRequestType.CREATE, UpdateRequestType.MODIFY]:
                self._preloaded_new.add(
                    (
                        request.rpsl_obj_new.rpsl_object_class,
                        request.rpsl_obj_new.pk(),
                        request.rpsl_obj_new.source(),
                    )
                )

    def check_references_to_others(self, rpsl_obj: RPSLObject) -> ValidatorResult:
        """
        Check the validity of references of a particular object, i.e. whether
        all references to other objects actually exist in the database.
        """
        result = ValidatorResult()
        references = rpsl_obj.referred_strong_objects()
        source = rpsl_obj.source()

        for field_name, objects_referred, object_pks in references:
            for object_pk in object_pks:
                if not self._check_reference_to_others(objects_referred, object_pk, source):
                    if len(objects_referred) > 1:
                        objects_referred_str = "one of " + ", ".join(objects_referred)
                    else:
                        objects_referred_str = objects_referred[0]
                    result.error_messages.add(
                        f"Object {object_pk} referenced in field {field_name} not found in "
                        f"database {source} - must reference {objects_referred_str}."
                    )
        return result

    def _check_reference_to_others(self, object_classes: List[str], object_pk: str, source: str) -> bool:
        """
        Check whether one reference to a particular object class/source/PK is valid,
        i.e. such an object exists in the database.

        Object classes is a list of classes to which the reference may point, e.g.
        person/role for admin-c, route for route-set members, or route/route6 for mp-members.
        """
        for object_class in object_classes:
            if (object_class, object_pk, source) in self._cache:
                return True
            if (object_class, object_pk, source) in self._preloaded_new:
                return True
            if (object_class, object_pk, source) in self._preloaded_deleted:
                return False

        query = RPSLDatabaseQuery().sources([source]).object_classes(object_classes).rpsl_pk(object_pk)
        results = list(self.database_handler.execute_query(query))
        for result in results:
            self._cache.add((result["object_class"], object_pk, source))
        if len(results):
            return True

        return False

    def check_references_from_others_for_deletion(
        self, rpsl_obj: RPSLObject, used_override=False
    ) -> ValidatorResult:
        """
        Check for any references to this object in the DB.
        Used for validating deletions.
        When using override and removing a protected object,
        the check may be bypassed.
        """
        result = ValidatorResult()
        if used_override and rpsl_obj.rpsl_object_class in PROTECTED_NAME_OBJECT_CLASSES:
            message_target = result.info_messages
            message_format = (
                "NOTE: object {rpsl_pk} still referenced by {referring_object_class} {referring_rpsl_pk}."
                " Delete permitted due to override. This creates a broken reference."
            )
        else:
            message_target = result.error_messages
            message_format = (
                "Object {rpsl_pk} to be deleted, but still referenced by"
                " {referring_object_class} {referring_rpsl_pk}"
            )
        self._check_references_from_others(
            rpsl_obj=rpsl_obj,
            message_target=message_target,
            message_format=message_format,
        )
        return result

    def check_protected_name(self, rpsl_obj: RPSLObject, used_override=False) -> ValidatorResult:
        """
        Check whether the object violates protected name rules (#616)

        Checks for existing (currently broken) references to the object,
        and whether the name is in the protected name table.
        If used_override is set, violations are permitted and this generates
        an info message instead of an error.
        """
        result = ValidatorResult()
        if used_override:
            message_target = result.info_messages
            message_format = (
                "NOTE: existing references to {rpsl_pk} exist"
                " from {referring_object_class} {referring_rpsl_pk}, permitted due to override"
            )
        else:
            message_target = result.error_messages
            message_format = (
                "Object {rpsl_pk} to be created, but existing references exist"
                " from {referring_object_class} {referring_rpsl_pk}"
            )

        self._check_references_from_others(
            rpsl_obj=rpsl_obj,
            message_target=message_target,
            message_format=message_format,
        )
        query = (
            ProtectedRPSLNameQuery()
            .protected_name(rpsl_obj.pk())
            .object_classes([rpsl_obj.rpsl_object_class])
            .source(rpsl_obj.source())
        )
        is_protected = bool(list(self.database_handler.execute_query(query)))
        if is_protected:
            if used_override:
                result.info_messages.add(
                    f"NOTE: object {rpsl_obj.pk()} has a protected name, creation permitted due to override."
                )
            else:
                result.error_messages.add(
                    f"Object {rpsl_obj.pk()} has a protected name that can not be reused."
                    " Create the object under a different name."
                )
        return result

    def _check_references_from_others(
        self, rpsl_obj: RPSLObject, message_target: Set[str], message_format: str
    ) -> ValidatorResult:
        """
        Check for any references to this object in the DB.
        Used for validating deletions and protected names.

        Checks self._preloaded_deleted, because a reference from an object
        that is also about to be deleted, is acceptable.
        """
        result = ValidatorResult()
        if not rpsl_obj.references_strong_inbound():
            return result

        query = RPSLDatabaseQuery().sources([rpsl_obj.source()])
        query = query.lookup_attrs_in(rpsl_obj.references_strong_inbound(), [rpsl_obj.pk()])
        query_results = self.database_handler.execute_query(query)
        for query_result in query_results:
            reference_to_be_deleted = (
                query_result["object_class"],
                query_result["rpsl_pk"],
                query_result["source"],
            ) in self._preloaded_deleted
            if not reference_to_be_deleted:
                message_target.add(
                    message_format.format(
                        rpsl_pk=rpsl_obj.pk(),
                        referring_object_class=query_result["object_class"],
                        referring_rpsl_pk=query_result["rpsl_pk"],
                    )
                )
        return result


class AuthValidator:
    """
    The AuthValidator validates authentication. It looks for relevant mntner
    objects and checks whether any of their auth methods pass.

    When adding a mntner in an update, a check for that mntner in the DB will
    fail, as it does not exist yet. To prevent this failure, call pre_approve()
    with a list of UpdateRequests.
    """

    passwords: List[str]
    overrides: List[str]
    api_keys: List[str]
    keycert_obj_pk: Optional[str] = None

    def __init__(
        self,
        database_handler: DatabaseHandler,
        origin: AuthoritativeChangeOrigin = AuthoritativeChangeOrigin.other,
        keycert_obj_pk=None,
        internal_authenticated_user: Optional[AuthUser] = None,
        remote_ip: Optional[IP] = None,
    ) -> None:
        self.database_handler = database_handler
        self.passwords = []
        self.overrides = []
        self.api_keys = []
        self.origin = origin
        self.remote_ip = remote_ip
        self._mntner_db_cache: Set[RPSLMntner] = set()
        self._pre_approved: Set[str] = set()
        self.keycert_obj_pk = keycert_obj_pk
        self._internal_authenticated_user = internal_authenticated_user

    def pre_approve(self, presumed_valid_new_mntners: List[RPSLMntner]) -> None:
        """
        Pre-approve certain maintainers that are part of this batch of updates.
        This is required for creating new maintainers along with other objects.

        All new maintainer PKs are added to self._pre_approved. When they are
        encountered as mnt-by, the authentication is immediately approved,
        as a check in the database would fail.
        When the new mntner object's mnt-by is checked, there is an additional
        check to verify that it passes the newly submitted authentication.
        """
        self._pre_approved = {obj.pk() for obj in presumed_valid_new_mntners}

    def process_auth(
        self, rpsl_obj_new: RPSLObject, rpsl_obj_current: Optional[RPSLObject]
    ) -> ValidatorResult:
        """
        Check whether authentication passes for all required objects.
        Returns a ValidatorResult object with error/info messages, and fills
        result.mntners_notify with the RPSLMntner objects that may have
        to be notified.

        If a valid override password is provided, changes are immediately approved.
        On the result object, method is set to override, but associated_mntners is
        not filled, as mntner resolving does not take place.
        """
        source = rpsl_obj_new.source()
        result = ValidatorResult()

        override_method = self.check_override()
        if override_method:
            result.auth_method = override_method
            if override_method == AuthMethod.OVERRIDE_INTERNAL_AUTH:
                result.auth_through_internal_user = self._internal_authenticated_user
            logger.info("Found valid override password.")
            return result

        mntners_new = rpsl_obj_new.parsed_data["mnt-by"]
        logger.debug(f"Checking auth for new object {rpsl_obj_new}, mntners in new object: {mntners_new}")
        new_mntners_result = self._check_mntners(rpsl_obj_new, mntners_new, source)
        if not new_mntners_result.valid:
            self._generate_failure_message(result, mntners_new, rpsl_obj_new)

        current_mntners_result = None
        related_mntners_result = None
        if rpsl_obj_current:
            mntners_current = rpsl_obj_current.parsed_data["mnt-by"]
            logger.debug(
                f"Checking auth for current object {rpsl_obj_current}, "
                f"mntners in current object: {mntners_current}"
            )
            current_mntners_result = self._check_mntners(rpsl_obj_new, mntners_current, source)
            if not current_mntners_result.valid:
                self._generate_failure_message(result, mntners_current, rpsl_obj_new)

            result.mntners_notify = current_mntners_result.associated_mntners
        else:
            result.mntners_notify = new_mntners_result.associated_mntners
            mntners_related = self._find_related_mntners(rpsl_obj_new, result)
            if mntners_related:
                related_object_class, related_pk, related_mntner_list = mntners_related
                logger.debug(
                    f"Checking auth for related object {related_object_class} / "
                    f"{related_pk} with mntners {related_mntner_list}"
                )
                related_mntners_result = self._check_mntners(rpsl_obj_new, related_mntner_list, source)
                if not related_mntners_result.valid:
                    self._generate_failure_message(
                        result, related_mntner_list, rpsl_obj_new, related_object_class, related_pk
                    )
                    result.mntners_notify = related_mntners_result.associated_mntners

        if isinstance(rpsl_obj_new, RPSLMntner):
            if not rpsl_obj_current:
                result.error_messages.add("New mntner objects must be added by an administrator.")
                return result
            # Dummy auth values are only permitted in existing objects
            if rpsl_obj_new.has_dummy_auth_value():
                if len(self.passwords) == 1:
                    logger.debug(
                        f"Object {rpsl_obj_new} submitted with dummy hash values and single password, "
                        "replacing all hashes with currently supplied password."
                    )
                    rpsl_obj_new.force_single_new_password(self.passwords[0])
                    result.info_messages.add(
                        "As you submitted dummy hash values, all password hashes on this object "
                        "were replaced with a new BCRYPT-PW hash of the password you provided for "
                        "authentication."
                    )
                else:
                    result.error_messages.add(
                        "Object submitted with dummy hash values, but multiple or no passwords "
                        "submitted. Either submit only full hashes, or a single password."
                    )
            elif not any(
                [
                    rpsl_obj_new.verify_auth(self.passwords, self.keycert_obj_pk),
                    self._mntner_matches_internal_auth(rpsl_obj_new, rpsl_obj_new.pk(), source),
                    # API keys are not checked here, as they can never be used on RPSLMntner
                ]
            ):
                result.error_messages.add("Authorisation failed for the auth methods on this mntner object.")

        mntner_result_for_change_log = current_mntners_result or related_mntners_result or new_mntners_result
        if mntner_result_for_change_log:
            result.auth_method = mntner_result_for_change_log.auth_method
            result.auth_through_mntner = mntner_result_for_change_log.mntner_pk
            result.auth_through_api_key = mntner_result_for_change_log.api_key
            result.auth_through_internal_mntner = mntner_result_for_change_log.auth_mntner
            if result.auth_method == AuthMethod.MNTNER_INTERNAL_AUTH:
                result.auth_through_internal_user = self._internal_authenticated_user

        return result

    def check_override(self) -> Optional[AuthMethod]:
        if self._internal_authenticated_user and self._internal_authenticated_user.override:
            logger.info(
                "Authenticated by valid override from internally authenticated "
                f"user {self._internal_authenticated_user}"
            )
            return AuthMethod.OVERRIDE_INTERNAL_AUTH

        override_hash = get_setting("auth.override_password")
        if override_hash:
            for override in self.overrides:
                try:
                    if bcrypt.verify(override, override_hash):
                        return AuthMethod.OVERRIDE_PASSWORD
                    else:
                        logger.info("Found invalid override password, ignoring.")
                except ValueError:
                    try:
                        if md5_crypt.verify(override, override_hash):
                            return AuthMethod.OVERRIDE_PASSWORD
                        else:
                            logger.info("Found invalid override password, ignoring.")
                    except ValueError:
                        logger.error(
                            "Exception occurred while checking override password as both bcrypt and salted"
                            " MD5 (possible misconfigured hash?)"
                        )
        elif self.overrides:
            logger.info("Ignoring override password, auth.override_password not set.")
        return AuthMethod.NONE

    def _check_mntners(
        self, rpsl_obj_new: RPSLObject, mntner_pk_list: List[str], source: str
    ) -> MntnerCheckResult:
        """
        Check whether authentication passes for a list of maintainers.

        Checks if at least one of the mntners in mntner_list
        passes authentication, given self.passwords and
        self.keycert_obj_pk. Updates and checks self._mntner_db_cache
        to prevent double retrieval of maintainers.
        """
        mntner_pk_set = set(mntner_pk_list)
        mntner_objs: List[RPSLMntner] = [
            m for m in self._mntner_db_cache if m.pk() in mntner_pk_set and m.source() == source
        ]
        mntner_pks_to_resolve: Set[str] = mntner_pk_set - {m.pk() for m in mntner_objs}

        if mntner_pks_to_resolve:
            query = RPSLDatabaseQuery().sources([source])
            query = query.object_classes(["mntner"]).rpsl_pks(mntner_pks_to_resolve)
            results = self.database_handler.execute_query(query)

            retrieved_mntner_objs: List[RPSLMntner] = [rpsl_object_from_text(r["object_text"], strict_validation=False) for r in results]  # type: ignore
            self._mntner_db_cache.update(retrieved_mntner_objs)
            mntner_objs += retrieved_mntner_objs

        for mntner_name in mntner_pk_list:
            if mntner_name in self._pre_approved:
                return MntnerCheckResult(
                    valid=True,
                    associated_mntners=mntner_objs,
                    auth_method=AuthMethod.MNTNER_IN_SAME_REQUEST,
                    mntner_pk=mntner_name,
                )
            internal_auth_match = self._mntner_matches_internal_auth(rpsl_obj_new, mntner_name, source)
            if internal_auth_match:
                return MntnerCheckResult(
                    valid=True,
                    associated_mntners=mntner_objs,
                    auth_method=AuthMethod.MNTNER_INTERNAL_AUTH,
                    auth_mntner=internal_auth_match,
                    mntner_pk=mntner_name,
                )
            api_key = self._api_key_match_for_mntner(rpsl_obj_new, mntner_name, source)
            if api_key:
                return MntnerCheckResult(
                    valid=True,
                    associated_mntners=mntner_objs,
                    auth_method=AuthMethod.MNTNER_API_KEY,
                    auth_mntner=api_key.mntner,
                    mntner_pk=mntner_name,
                    api_key=api_key.pk,
                )

        for mntner_obj in mntner_objs:
            valid_scheme = mntner_obj.verify_auth(self.passwords, self.keycert_obj_pk)
            if valid_scheme:
                auth_method = (
                    AuthMethod.MNTNER_PGP_KEY if "PGPKEY" in valid_scheme else AuthMethod.MNTNER_PASSWORD
                )
                return MntnerCheckResult(
                    valid=True,
                    associated_mntners=mntner_objs,
                    auth_method=auth_method,
                    mntner_pk=mntner_obj.pk(),
                )

        return MntnerCheckResult(valid=False, associated_mntners=mntner_objs)

    def _mntner_matches_internal_auth(
        self, rpsl_obj_new: RPSLObject, rpsl_pk: str, source: str
    ) -> Optional[AuthMntner]:
        if not self._internal_authenticated_user:
            return None
        if rpsl_obj_new.pk() == rpsl_pk and rpsl_obj_new.source() == source:
            user_mntner_set = self._internal_authenticated_user.mntners_user_management
        else:
            user_mntner_set = self._internal_authenticated_user.mntners
        for mntner in user_mntner_set:
            if rpsl_pk == mntner.rpsl_mntner_pk and source == mntner.rpsl_mntner_source:
                logger.info(
                    f"Authenticated through internally authenticated user {self._internal_authenticated_user}"
                )
                return mntner
        return None

    def _api_key_match_for_mntner(
        self, rpsl_obj_new: RPSLObject, rpsl_pk: str, source: str
    ) -> Optional[AuthApiToken]:
        if not self.api_keys or isinstance(rpsl_obj_new, RPSLMntner):
            return None

        session = saorm.Session(bind=self.database_handler._connection)
        query = (
            session.query(AuthApiToken)
            .join(AuthMntner)
            .filter(
                AuthMntner.rpsl_mntner_pk == rpsl_pk,
                AuthMntner.rpsl_mntner_source == source,
                AuthApiToken.token.in_(self.api_keys),
            )
        )
        for api_token in query.all():
            if api_token.valid_for(self.origin, self.remote_ip):
                logger.info(f"Authenticated through API token {api_token.pk} on mntner {rpsl_pk}")
                return api_token

        return None

    def _generate_failure_message(
        self,
        result: ValidatorResult,
        failed_mntner_list: List[str],
        rpsl_obj,
        related_object_class: Optional[str] = None,
        related_pk: Optional[str] = None,
    ) -> None:
        mntner_str = ", ".join(failed_mntner_list)
        msg = f"Authorisation for {rpsl_obj.rpsl_object_class} {rpsl_obj.pk()} failed: "
        msg += f"must be authenticated by one of: {mntner_str}"
        if related_object_class and related_pk:
            msg += f" - from parent {related_object_class} {related_pk}"
        result.error_messages.add(msg)

    def _find_related_mntners(
        self, rpsl_obj_new: RPSLObject, result: ValidatorResult
    ) -> Optional[Tuple[str, str, List[str]]]:
        """
        Find the maintainers of the related object to rpsl_obj_new, if any.
        This is used to authorise creating objects - authentication may be
        required to pass for the related object as well.

        Returns a tuple of:
        - object class of the related object
        - PK of the related object
        - List of maintainers for the related object (at least one must pass)
        Returns None if no related objects were found that should be authenticated.

        Custom error messages may be added directly to the passed ValidatorResult.
        """
        related_object = None
        if rpsl_obj_new.rpsl_object_class in ["route", "route6"]:
            related_object = self._find_related_object_route(rpsl_obj_new)
        if issubclass(rpsl_obj_new.__class__, RPSLSet):
            related_object = self._find_related_object_set(rpsl_obj_new, result)

        if related_object:
            mntners = related_object.get("parsed_data", {}).get("mnt-by", [])
            return related_object["object_class"], related_object["rpsl_pk"], mntners

        return None

    @functools.lru_cache(maxsize=50)
    def _find_related_object_route(self, rpsl_obj_new: RPSLObject):
        """
        Find the related inetnum/route object to rpsl_obj_new, which must be a route(6).
        Returns a dict as returned by the database handler.
        """
        if not get_setting("auth.authenticate_parents_route_creation"):
            return None

        inetnum_class = {
            "route": "inetnum",
            "route6": "inet6num",
        }

        object_class = inetnum_class[rpsl_obj_new.rpsl_object_class]
        query = _init_related_object_query(object_class, rpsl_obj_new).ip_exact(rpsl_obj_new.prefix)
        inetnums = list(self.database_handler.execute_query(query))

        if not inetnums:
            query = _init_related_object_query(object_class, rpsl_obj_new).ip_less_specific_one_level(
                rpsl_obj_new.prefix
            )
            inetnums = list(self.database_handler.execute_query(query))

        if inetnums:
            return inetnums[0]

        object_class = rpsl_obj_new.rpsl_object_class
        query = _init_related_object_query(object_class, rpsl_obj_new).ip_less_specific_one_level(
            rpsl_obj_new.prefix
        )
        routes = list(self.database_handler.execute_query(query))
        if routes:
            return routes[0]

        return None

    def _find_related_object_set(self, rpsl_obj_new: RPSLObject, result: ValidatorResult):
        """
        Find the related aut-num object to rpsl_obj_new, which must be a set object,
        depending on settings.
        Returns a dict as returned by the database handler.
        """

        @functools.lru_cache(maxsize=50)
        def _find_in_db():
            query = _init_related_object_query("aut-num", rpsl_obj_new).rpsl_pk(rpsl_obj_new.pk_asn_segment)
            aut_nums = list(self.database_handler.execute_query(query))
            if aut_nums:
                return aut_nums[0]

        if not rpsl_obj_new.pk_asn_segment:
            return None

        mode = RPSLSetAutnumAuthenticationMode.for_set_name(rpsl_obj_new.rpsl_object_class)
        if mode == RPSLSetAutnumAuthenticationMode.DISABLED:
            return None

        aut_num = _find_in_db()
        if aut_num:
            return aut_num
        elif mode == RPSLSetAutnumAuthenticationMode.REQUIRED:
            result.error_messages.add(
                f"Creating this object requires an aut-num for {rpsl_obj_new.pk_asn_segment} to exist."
            )
        return None


def _init_related_object_query(rpsl_object_class: str, rpsl_obj_new: RPSLObject) -> RPSLDatabaseQuery:
    query = RPSLDatabaseQuery().sources([rpsl_obj_new.source()])
    query = query.object_classes([rpsl_object_class])
    return query.first_only()


class RulesValidator:
    """
    The RulesValidator validates any other rules for RPSL object changes.
    This means: anything that is not authentication, references, RPKI or scope filter.
    """

    def __init__(self, database_handler: DatabaseHandler) -> None:
        self.database_handler = database_handler

    def validate(self, rpsl_obj: RPSLObject, request_type: UpdateRequestType) -> ValidatorResult:
        result = ValidatorResult()

        if (
            request_type == UpdateRequestType.CREATE
            and rpsl_obj.rpsl_object_class == "mntner"
            and self._check_suspended_mntner_with_same_pk(rpsl_obj.pk(), rpsl_obj.source())
        ):
            result.error_messages.add(
                f"A suspended mntner with primary key {rpsl_obj.pk()} already exists for {rpsl_obj.source()}"
            )

        if isinstance(rpsl_obj, RPSLMntner):
            is_migrated = self._check_mntner_migrated(rpsl_obj.pk(), rpsl_obj.source())
            has_internal_auth = rpsl_obj.has_internal_auth()
            if is_migrated and not has_internal_auth:
                result.error_messages.add(
                    f"This maintainer is migrated and must include the {RPSL_MNTNER_AUTH_INTERNAL} method."
                )
            elif not is_migrated and has_internal_auth:
                result.error_messages.add(
                    "This maintainer is not migrated, and therefore can not use the"
                    f" {RPSL_MNTNER_AUTH_INTERNAL} method."
                )

        return result

    @functools.lru_cache(maxsize=50)
    def _check_suspended_mntner_with_same_pk(self, pk: str, source: str) -> bool:
        q = RPSLDatabaseSuspendedQuery().object_classes(["mntner"]).rpsl_pk(pk).sources([source]).first_only()
        return bool(list(self.database_handler.execute_query(q)))

    @functools.lru_cache(maxsize=50)
    def _check_mntner_migrated(self, pk: str, source: str) -> bool:
        session = saorm.Session(bind=self.database_handler._connection)
        query = session.query(AuthMntner).filter(
            AuthMntner.rpsl_mntner_pk == pk,
            AuthMntner.rpsl_mntner_source == source,
        )
        return bool(query.count())
