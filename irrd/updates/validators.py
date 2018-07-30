import logging
from typing import Set, Tuple, List, Optional, TYPE_CHECKING

from irrd.db.api import DatabaseHandler, RPSLDatabaseQuery
from irrd.rpsl.parser import RPSLObject
from irrd.rpsl.rpsl_objects import RPSLMntner, rpsl_object_from_text
from .parser_state import UpdateRequestType

if TYPE_CHECKING:  # pragma: no cover
    # http://mypy.readthedocs.io/en/latest/common_issues.html#import-cycles
    import parser  # noqa: F401

logger = logging.getLogger(__name__)


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

    def preload(self, results: List['parser.UpdateRequest']) -> None:
        """Preload an iterable of UpdateRequest objects to be considered valid, or to be considered deleted."""
        self._preloaded_new = set()
        self._preloaded_deleted = set()
        for request in results:
            if request.request_type == UpdateRequestType.DELETE:
                self._preloaded_deleted.add((request.rpsl_obj_new.rpsl_object_class, request.rpsl_obj_new.pk(),
                                             request.rpsl_obj_new.source()))
            else:
                self._preloaded_new.add((request.rpsl_obj_new.rpsl_object_class, request.rpsl_obj_new.pk(),
                                         request.rpsl_obj_new.source()))

    def check_reference_to_others(self, object_classes: List[str], object_pk: str, source: str) -> bool:
        """
        Check whether a reference to a particular object class/source/PK is valid,
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

        # TODO: this still fails for route objects, where the PK includes the AS, but the reference does not
        query = RPSLDatabaseQuery().sources([source]).object_classes(object_classes).rpsl_pk(object_pk)
        results = list(self.database_handler.execute_query(query))
        for result in results:
            self._cache.add((result['object_class'], object_pk, source))
        if results:
            return True

        return False

    def check_references_from_others(self, rpsl_obj: RPSLObject) -> List[Tuple[str, str, str]]:
        """
        Check for any references to this object in the DB.
        Used for validation deletions.
        """
        query = RPSLDatabaseQuery().sources([rpsl_obj.source()])
        # TODO: fails to detect route objects
        query = query.lookup_attrs_in(rpsl_obj.references_inbound(), [rpsl_obj.pk()])
        query_results = self.database_handler.execute_query(query)
        results = [(r['object_class'], r['rpsl_pk'], r['source']) for r in query_results]
        return [r for r in results if r not in self._preloaded_deleted]


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

    def __init__(self, database_handler: DatabaseHandler) -> None:
        self.database_handler = database_handler
        self._passed_cache: Set[str] = set()
        self._pre_approved: Set[str] = set()

    def pre_approve(self, results: List['parser.UpdateRequest']) -> None:
        """
        Pre-approve certain maintainers that are part of this batch of updates.

        When these maintainers are encountered in another object, e.g. the mnt-by
        of a person, their authentication is considered passed.
        When the mntner object itself is encountered, it's auth attributes are
        always validated against available authentication metadata.
        """
        # TODO: only allow pre-approving newly created maintainers - otherwise
        # follow the regular process to ensure the old mntner is validates

        self._pre_approved = set()
        for request in results:
            if request.is_valid() and request.request_type != UpdateRequestType.DELETE and isinstance(request.rpsl_obj_new, RPSLMntner):
                self._pre_approved.add(request.rpsl_obj_new.pk())

    def check_auth(self, rpsl_obj_new: RPSLObject, rpsl_obj_current: Optional[RPSLObject]) -> Optional[str]:
        """
        Check whether authentication passes for all required objects.

        Returns a string with an error message for failures, None when successful
        """
        source = rpsl_obj_new.source()

        mntners_new = rpsl_obj_new.parsed_data['mnt-by']
        if not self._check_mntners(mntners_new, source):
            return self._generate_failure_message(mntners_new, rpsl_obj_new)

        if rpsl_obj_current:
            mntners_current = rpsl_obj_current.parsed_data['mnt-by']
            if not self._check_mntners(mntners_current, source):
                return self._generate_failure_message(mntners_current, rpsl_obj_new)

        if isinstance(rpsl_obj_new, RPSLMntner):
            if not rpsl_obj_new.verify_auth(self.passwords, self.keycert_obj_pk):
                return f'Authorisation failed for the auth methods on this mntner object.'

        return None
        # TODO: further sets pending https://github.com/irrdnet/irrd4/issues/21#issuecomment-407105924

    def _check_mntners(self, mntner_list: List[str], source: str) -> bool:
        """
        Check whether authentication passes for a list of maintainers.

        Returns True if at least one of the mntners in mntner_list
        passes authentication, given self.passwords and
        self.keycert_obj_pk. Updates and checks self.passed_mntner_cache
        to prevent double checking of maintainers.
        """
        for mntner_name in mntner_list:
            if mntner_name in self._passed_cache or mntner_name in self._pre_approved:
                return True

        query = RPSLDatabaseQuery().sources([source])
        query = query.object_classes(['mntner']).rpsl_pks(mntner_list)
        results = list(self.database_handler.execute_query(query))
        mntner_objs: List[RPSLMntner] = [rpsl_object_from_text(r['object_text']) for r in results]  # type: ignore

        for mntner_obj in mntner_objs:
            if mntner_obj.verify_auth(self.passwords, self.keycert_obj_pk):
                self._passed_cache.add(mntner_obj.pk())

                return True

        return False

    def _generate_failure_message(self, failed_mntner_list: List[str], rpsl_obj) -> str:
        mntner_str = ', '.join(failed_mntner_list)
        msg = f'Authorisation for {rpsl_obj.rpsl_object_class} {rpsl_obj.pk()} failed: '
        msg += f'must by authenticated by one of: {mntner_str}'
        return msg
