import logging
from typing import Set, Tuple, List, Optional

from irrd.db.api import DatabaseHandler, RPSLDatabaseQuery
from irrd.rpsl.parser import RPSLObject
from irrd.rpsl.rpsl_objects import RPSLMntner, rpsl_object_from_text

logger = logging.getLogger(__name__)


class ReferenceValidator:
    """
    The ReferenceValidator validates references to other objects, given
    their expected object_class, source and PK.

    Sometimes updates are made to objects, referencing objects newly created
    in the same update message. To handle this, the validator can be preloaded
    with objects that should be considered valid.
    """
    def __init__(self, database_handler: DatabaseHandler):
        self.database_handler = database_handler
        self._cache: Set[Tuple[str, str, str]] = set()
        self._preloaded: Set[Tuple[str, str, str]] = set()

    def check_reference(self, object_classes: List[str], object_pk: str, source: str) -> bool:
        """
        Check whether a reference to a particular object class/source/PK is valid,
        i.e. such an object exists in the database.
        """
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

    def _check_cache(self, object_classes: List[str], object_pk: str, source: str) -> bool:
        for object_class in object_classes:
            if (object_class, object_pk, source) in self._cache:
                return True
            if (object_class, object_pk, source) in self._preloaded:
                return True
        return False

    def preload(self, results) -> None:
        """Preload an iterable of UpdateRequest objects to be considered valid."""
        self._preloaded = set()
        for request in results:
            self._preloaded.add((request.rpsl_obj_new.rpsl_object_class, request.rpsl_obj_new.pk(),
                                 request.rpsl_obj_new.source()))


class AuthValidator:
    passwords: List[str]
    overrides: List[str]
    keycert_obj_pk: Optional[str] = None

    def __init__(self, database_handler: DatabaseHandler):
        self.database_handler = database_handler
        self._passed_cache: Set[str] = set()
        self._pre_approved: Set[str] = set()

    def check_auth(self, rpsl_obj_new: RPSLObject, rpsl_obj_current: Optional[RPSLObject]) -> Optional[str]:
        """Check whether authentication passes for all required objects."""
        source = rpsl_obj_new.source()

        mntners_new = rpsl_obj_new.parsed_data['mnt-by']
        if not self._check_mntners(mntners_new, source):
            return self._generate_failure_message(mntners_new, rpsl_obj_new)

        if rpsl_obj_current:
            mntners_current = rpsl_obj_current.parsed_data['mnt-by']
            if not self._check_mntners(mntners_current, source):
                return self._generate_failure_message(mntners_new, rpsl_obj_new)

        if rpsl_obj_new.rpsl_object_class == 'mntner':
            if not rpsl_obj_new.verify_auth(self.passwords, self.keycert_obj_pk):
                return f'Authorisation failed for the auth methods on this mntner object.'

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
        mntner_objs: List[RPSLMntner] = [rpsl_object_from_text(r['object_text']) for r in results]

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

    def pre_approve(self, results) -> None:
        self._pre_approved = set()
        for request in results:
            if request.is_valid() and request.rpsl_obj_new.rpsl_object_class == 'mntner':
                self._pre_approved.add(request.rpsl_obj_new.pk())
