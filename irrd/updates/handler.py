from irrd.db.api import DatabaseHandler
from irrd.updates.parser import parse_update_request, UpdateRequestStatus, ReferenceChecker, UpdateRequestType


class UpdateRequestHandler:

    def __init__(self):
        self.database_handler = DatabaseHandler()

    def handle_object_texts(self, object_texts: str):
        results = parse_update_request(object_texts)
        # TODO: pks should be immutable

        reference_checker = ReferenceChecker(self.database_handler)

        # When an object references another object, e.g. tech-c referring a person or mntner,
        # an add/update is only valid if those referred objects exist. To complicate matters,
        # the object referred to may be part of this very same update. For this reason, the
        # reference checker can be provided with all new objects to be added in this update.
        # However, a possible scenario is that A, B and C are submitted. Object A refers to B,
        # B refers to C, C refers to D and D does not exist. At a first scan, A is valid because
        # B exists, B is valid because C exists. C becomes invalid on the first scan, which is
        # why another scan is performed, which will mark B invalid due to the reference to an
        # invalid C, etc. This continues until all references are resolved and repeated scans
        # lead to the same conclusions.
        valid_updates = [r for r in results if r.is_valid() and r.request_type != UpdateRequestType.DELETE]
        previous_valid_updates = []
        while valid_updates != previous_valid_updates:
            previous_valid_updates = valid_updates
            reference_checker.preload(valid_updates)

            for result in valid_updates:
                result.check_references(reference_checker)
                valid_updates = [r for r in results if r.is_valid()]

        # auth checks

        for result in results:
            if result.is_valid():
                result.save(self.database_handler)

        self.database_handler.rollback()
        return self.user_report(results)

        # Must match authoritive source
        # current object one mnt-by must be matched
        # route must match one mnt-by from aut-num
        # aut-num must match mnt-by of smallest surrounding as-block
        # inetnum must match mnt-by of smallest surrounding inetnum
        # for sets containing object names, must pass mnt-by for any objects mentioned

        # For change, email all relevant maintainers on mnt-nfy if auth succeeded,
        # upd-to if auth failed. If the failure was otherwise, e.g. syntax, do not mail
        # maintainers.
        # On succesful change, mail the notify attribute of this object.

    def user_report(self, results):
        user_report = 'DETAILED EXPLANATION:\n'
        user_report += '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n'
        for result in results:
            user_report += "---\n"
            user_report += result.user_report()
            user_report += "\n"
        user_report += '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n'
        return user_report
