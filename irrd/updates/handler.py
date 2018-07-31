from typing import List

from irrd.db.api import DatabaseHandler
from .parser import parse_update_requests, UpdateRequest
from .parser_state import UpdateRequestType
from .validators import ReferenceValidator, AuthValidator


class UpdateRequestHandler:

    def __init__(self):
        self.database_handler = DatabaseHandler()

    def handle_object_texts(self, object_texts: str):
        reference_validator = ReferenceValidator(self.database_handler)
        auth_validator = AuthValidator(self.database_handler)
        results = parse_update_requests(object_texts, self.database_handler, auth_validator, reference_validator)

        # When an object references another object, e.g. tech-c referring a person or mntner,
        # an add/update is only valid if those referred objects exist. To complicate matters,
        # the object referred to may be part of this very same update. For this reason, the
        # reference validator can be provided with all new objects to be added in this update.
        # However, a possible scenario is that A, B and C are submitted. Object A refers to B,
        # B refers to C, C refers to D and D does not exist - or C fails authentication.
        # At a first scan, A is valid because B exists, B is valid because C exists. C
        # becomes invalid on the first scan, which is why another scan is performed, which
        # will mark B invalid due to the reference to an invalid C, etc. This continues until
        # all references are resolved and repeated scans lead to the same conclusions.
        valid_updates = [r for r in results if r.is_valid()]
        previous_valid_updates: List[UpdateRequest] = []
        while valid_updates != previous_valid_updates:  # TODO: protect against infinite loops
            previous_valid_updates = valid_updates
            reference_validator.preload(valid_updates)
            auth_validator.pre_approve(valid_updates)

            for result in valid_updates:
                result.validate()
            valid_updates = [r for r in results if r.is_valid()]

        for result in results:
            if result.is_valid():
                result.save(self.database_handler)

        self.database_handler.rollback()
        return self.user_report(results)

    def user_report(self, results):
        user_report = 'DETAILED EXPLANATION:\n'
        user_report += '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n'
        for result in results:
            user_report += "---\n"
            user_report += result.user_report()
            user_report += "\n"
        user_report += '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n'
        return user_report
