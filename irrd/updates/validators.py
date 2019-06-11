import logging
from passlib.hash import md5_crypt
from typing import Set, Tuple, List, Optional, TYPE_CHECKING

from dataclasses import dataclass, field
from ordered_set import OrderedSet

from irrd.conf import get_setting
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery
from irrd.rpsl.parser import RPSLObject
from irrd.rpsl.rpsl_objects import RPSLMntner, rpsl_object_from_text
from .parser_state import UpdateRequestType

if TYPE_CHECKING:  # pragma: no cover
    # http://mypy.readthedocs.io/en/latest/common_issues.html#import-cycles
    import parser  # noqa: F401

logger = logging.getLogger(__name__)


@dataclass
class ValidatorResult:
    error_messages: Set[str] = field(default_factory=OrderedSet)
    info_messages: Set[str] = field(default_factory=OrderedSet)
    # mntners that may need to be notified
    mntners_notify: List[RPSLMntner] = field(default_factory=list)
    # whether the authentication succeeded due to use of an override password
    used_override: bool = field(default=False)

    def is_valid(self):
        return len(self.error_messages) == 0


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

    def preload(self, results: List['parser.ChangeRequest']) -> None:
        """Preload an iterable of ChangeRequest objects to be considered valid, or to be considered deleted."""
        self._preloaded_new = set()
        self._preloaded_deleted = set()
        for request in results:
            if request.request_type == UpdateRequestType.DELETE:
                self._preloaded_deleted.add((request.rpsl_obj_new.rpsl_object_class, request.rpsl_obj_new.pk(),
                                             request.rpsl_obj_new.source()))
            else:
                self._preloaded_new.add((request.rpsl_obj_new.rpsl_object_class, request.rpsl_obj_new.pk(),
                                         request.rpsl_obj_new.source()))

    def check_references_to_others(self, rpsl_obj: RPSLObject) -> ValidatorResult:
        """
        Check the validity of references of a particular object, i.e. whether
        all references to other objects actually exist in the database.
        """
        result = ValidatorResult()
        references = rpsl_obj.referred_objects()
        source = rpsl_obj.source()

        for field_name, objects_referred, object_pks in references:
            for object_pk in object_pks:
                if not self._check_reference_to_others(objects_referred, object_pk, source):
                    if len(objects_referred) > 1:
                        objects_referred_str = 'one of ' + ', '.join(objects_referred)
                    else:
                        objects_referred_str = objects_referred[0]
                    result.error_messages.add(f'Object {object_pk} referenced in field {field_name} not found in '
                                              f'database {source} - must reference {objects_referred_str}.')
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
            self._cache.add((result['object_class'], object_pk, source))
        if len(results):
            return True

        return False

    def check_references_from_others(self, rpsl_obj: RPSLObject) -> ValidatorResult:
        """
        Check for any references to this object in the DB.
        Used for validating deletions.

        Checks self._preload_deleted, because a reference from an object
        that is also about to be deleted, is acceptable.
        """
        result = ValidatorResult()
        if not rpsl_obj.references_inbound():
            return result

        query = RPSLDatabaseQuery().sources([rpsl_obj.source()])
        query = query.lookup_attrs_in(rpsl_obj.references_inbound(), [rpsl_obj.pk()])
        query_results = self.database_handler.execute_query(query)
        for query_result in query_results:
            reference_to_be_deleted = (query_result['object_class'], query_result['rpsl_pk'],
                                       query_result['source']) in self._preloaded_deleted
            if not reference_to_be_deleted:
                result.error_messages.add(f'Object {rpsl_obj.pk()} to be deleted, but still referenced '
                                          f'by {query_result["object_class"]} {query_result["rpsl_pk"]}')
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
    keycert_obj_pk: Optional[str] = None

    def __init__(self, database_handler: DatabaseHandler, keycert_obj_pk=None) -> None:
        self.database_handler = database_handler
        self._mntner_db_cache: Set[RPSLMntner] = set()
        self._pre_approved: Set[str] = set()
        self.keycert_obj_pk = keycert_obj_pk

    def pre_approve(self, results: List['parser.ChangeRequest']) -> None:
        """
        Pre-approve certain maintainers that are part of this batch of updates.
        This is required for creating new maintainers along with other objects.

        All new maintainer PKs are added to self._pre_approved. When they are
        encountered as mnt-by, the authentication is immediately approved,
        as a check in the database would fail.
        When the new mntner object's mnt-by is checked, there is an additional
        check to verify that it passes the newly submitted authentication.
        """
        self._pre_approved = set()
        for request in results:
            if request.is_valid() and request.request_type == UpdateRequestType.CREATE and isinstance(request.rpsl_obj_new, RPSLMntner):
                self._pre_approved.add(request.rpsl_obj_new.pk())

    def process_auth(self, rpsl_obj_new: RPSLObject, rpsl_obj_current: Optional[RPSLObject]) -> ValidatorResult:
        """
        Check whether authentication passes for all required objects.
        Returns a ValidatorResult object with error/info messages, and fills
        result.mntners_notify with the RPSLMntner objects that may have
        to be notified.

        If a valid override password is provided, changes are immediately approved.
        On the result object, used_override is set to True, but mntners_notify is
        not filled, as mntner resolving does not take place.
        """
        source = rpsl_obj_new.source()
        result = ValidatorResult()

        override_hash = get_setting('auth.override_password')
        if override_hash:
            for override in self.overrides:
                try:
                    if md5_crypt.verify(override, override_hash):
                        result.used_override = True
                        logger.debug(f'Found valid override password.')
                        return result
                    else:
                        logger.info(f'Found invalid override password, ignoring.')
                except ValueError as ve:
                    logger.error(f'Exception occurred while checking override password: {ve} (possible misconfigured hash?)')
        elif self.overrides:
            logger.info(f'Ignoring override password, auth.override_password not set.')

        mntners_new = rpsl_obj_new.parsed_data['mnt-by']
        logger.debug(f'Checking auth for new object {rpsl_obj_new}, mntners in new object: {mntners_new}')
        valid, mntner_objs_new = self._check_mntners(mntners_new, source)
        if not valid:
            self._generate_failure_message(result, mntners_new, rpsl_obj_new)

        if rpsl_obj_current:
            mntners_current = rpsl_obj_current.parsed_data['mnt-by']
            logger.debug(f'Checking auth for current object {rpsl_obj_current}, '
                         f'mntners in new object: {mntners_current}')
            valid, mntner_objs_current = self._check_mntners(mntners_current, source)
            if not valid:
                self._generate_failure_message(result, mntners_current, rpsl_obj_new)

            result.mntners_notify = mntner_objs_current
        else:
            result.mntners_notify = mntner_objs_new

        if isinstance(rpsl_obj_new, RPSLMntner):
            if not rpsl_obj_current:
                result.error_messages.add('New mntner objects must be added by an administrator.')
                return result
            # Dummy auth values are only permitted in existing objects
            if rpsl_obj_new.has_dummy_auth_value():
                if len(self.passwords) == 1:
                    logger.debug(f'Object {rpsl_obj_new} submitted with dummy hash values and single password, '
                                 f'replacing all hashes with currently supplied password.')
                    rpsl_obj_new.force_single_new_password(self.passwords[0])
                    result.info_messages.add('As you submitted dummy hash values, all password hashes on this object '
                                             'were replaced with a new MD5-PW hash of the password you provided for '
                                             'authentication.')
                else:
                    result.error_messages.add(f'Object submitted with dummy hash values, but multiple or no passwords '
                                              f'submitted. Either submit only full hashes, or a single password.')
            elif not rpsl_obj_new.verify_auth(self.passwords, self.keycert_obj_pk):
                result.error_messages.add(f'Authorisation failed for the auth methods on this mntner object.')

        return result

    def _check_mntners(self, mntner_pk_list: List[str], source: str) -> Tuple[bool, List[RPSLMntner]]:
        """
        Check whether authentication passes for a list of maintainers.

        Returns True if at least one of the mntners in mntner_list
        passes authentication, given self.passwords and
        self.keycert_obj_pk. Updates and checks self.passed_mntner_cache
        to prevent double checking of maintainers.
        """
        mntner_pk_set = set(mntner_pk_list)
        mntner_objs: List[RPSLMntner] = [m for m in self._mntner_db_cache if m.pk() in mntner_pk_set and m.source() == source]
        mntner_pks_to_resolve: Set[str] = mntner_pk_set - {m.pk() for m in mntner_objs}

        if mntner_pks_to_resolve:
            query = RPSLDatabaseQuery().sources([source])
            query = query.object_classes(['mntner']).rpsl_pks(mntner_pks_to_resolve)
            results = list(self.database_handler.execute_query(query))

            retrieved_mntner_objs: List[RPSLMntner] = [rpsl_object_from_text(r['object_text']) for r in results]   # type: ignore
            self._mntner_db_cache.update(retrieved_mntner_objs)
            mntner_objs += retrieved_mntner_objs

        for mntner_name in mntner_pk_list:
            if mntner_name in self._pre_approved:
                return True, mntner_objs

        for mntner_obj in mntner_objs:
            if mntner_obj.verify_auth(self.passwords, self.keycert_obj_pk):
                return True, mntner_objs

        return False, mntner_objs

    def _generate_failure_message(self, result: ValidatorResult, failed_mntner_list: List[str], rpsl_obj) -> None:
        mntner_str = ', '.join(failed_mntner_list)
        msg = f'Authorisation for {rpsl_obj.rpsl_object_class} {rpsl_obj.pk()} failed: '
        msg += f'must by authenticated by one of: {mntner_str}'
        result.error_messages.add(msg)
