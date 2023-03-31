# flake8: noqa: W293
import textwrap
from unittest.mock import Mock

import pytest

from irrd.scopefilter.status import ScopeFilterStatus
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.models import JournalEntryOrigin
from irrd.updates.parser import parse_change_requests
from irrd.utils.rpsl_samples import SAMPLE_MNTNER
from irrd.utils.test_utils import flatten_mock_calls

from ...utils.validators import RPSLChangeSubmission, RPSLSuspensionSubmission
from ..handler import ChangeSubmissionHandler
from ..parser_state import SuspensionRequestType


@pytest.fixture()
def prepare_mocks(monkeypatch, config_override):
    monkeypatch.setenv("IRRD_SOURCES_TEST_AUTHORITATIVE", "1")
    mock_dh = Mock()
    monkeypatch.setattr("irrd.updates.handler.DatabaseHandler", lambda: mock_dh)
    mock_dq = Mock()
    monkeypatch.setattr("irrd.updates.handler.RPSLDatabaseQuery", lambda: mock_dq)
    monkeypatch.setattr("irrd.updates.parser.RPSLDatabaseQuery", lambda: mock_dq)
    monkeypatch.setattr("irrd.updates.validators.RPSLDatabaseQuery", lambda: mock_dq)
    mock_email = Mock()
    monkeypatch.setattr("irrd.utils.email.send_email", mock_email)
    config_override(
        {
            "auth": {
                "override_password": "$1$J6KycItM$MbPaBU6iFSGFV299Rk7Di0",
                "password_hashers": {"crypt-pw": "enabled"},
            },
        }
    )

    mock_scopefilter = Mock(spec=ScopeFilterValidator)
    monkeypatch.setattr("irrd.updates.parser.ScopeFilterValidator", lambda: mock_scopefilter)
    mock_scopefilter.validate_rpsl_object = lambda obj: (ScopeFilterStatus.in_scope, "")
    yield mock_dq, mock_dh, mock_email


class TestChangeSubmissionHandler:
    # NOTE: the scope of this test also includes ChangeRequest, ReferenceValidator and AuthValidator -
    # this is more of an update handler integration test.

    def test_parse_valid_new_objects_with_override(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks
        mock_dh.execute_query = lambda query: []

        rpsl_text = textwrap.dedent(
            """
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 000 0000
        nic-hdl:        PERSON-TEST
        mnt-by:         TEST-MNT
        e-mail:         email@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST

        mntner:         TEST-MNT
        admin-c:        PERSON-TEST
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        auth:           MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.  # md5-password
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        
        override: override-password

        inetnum:        80.16.151.184 - 80.016.151.191
        netname:        NETECONOMY-MG41731
        descr:          TELECOM ITALIA LAB SPA
        country:        IT
        admin-c:        PERSON-TEST
        tech-c:         PERSON-TEST
        status:         ASSIGNED PA
        notify:         neteconomy.rete@telecomitalia.it
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        remarks:        remark
        """
        )

        handler = ChangeSubmissionHandler().load_text_blob(rpsl_text)
        assert handler.status() == "SUCCESS"

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["rpsl_pk", ("80.16.151.184 - 80.16.151.191",), {}],
        ]

        assert mock_dh.mock_calls[0][0] == "upsert_rpsl_object"
        assert mock_dh.mock_calls[0][1][0].pk() == "PERSON-TEST"
        assert mock_dh.mock_calls[1][0] == "upsert_rpsl_object"
        assert mock_dh.mock_calls[1][1][0].pk() == "TEST-MNT"
        assert mock_dh.mock_calls[2][0] == "upsert_rpsl_object"
        assert mock_dh.mock_calls[2][1][0].pk() == "80.16.151.184 - 80.16.151.191"
        assert mock_dh.mock_calls[3][0] == "commit"
        assert mock_dh.mock_calls[4][0] == "close"

        assert handler.submitter_report_human() == textwrap.dedent(
            """
        SUMMARY OF UPDATE:

        Number of objects found:                    3
        Number of objects processed successfully:   3
            Create:        3
            Modify:        0
            Delete:        0
        Number of objects processed with errors:    0
            Create:        0
            Modify:        0
            Delete:        0
        
        DETAILED EXPLANATION:

        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ---
        Create succeeded: [person] PERSON-TEST
        
        ---
        Create succeeded: [mntner] TEST-MNT
        
        ---
        Create succeeded: [inetnum] 80.16.151.184 - 80.16.151.191
        
        inetnum:        80.16.151.184 - 80.16.151.191
        netname:        NETECONOMY-MG41731
        descr:          TELECOM ITALIA LAB SPA
        country:        IT
        admin-c:        PERSON-TEST
        tech-c:         PERSON-TEST
        status:         ASSIGNED PA
        notify:         neteconomy.rete@telecomitalia.it
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        remarks:        remark
        
        INFO: Address range 80.16.151.184 - 80.016.151.191 was reformatted as 80.16.151.184 - 80.16.151.191
        
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        )

    def test_parse_valid_new_person_existing_mntner_pgp_key(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks

        person_text = textwrap.dedent(
            """
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 000 0000
        nic-hdl:        PERSON-TEST
        mnt-by:         TEST-MNT
        e-mail:         email@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """
        )

        mntner_text = textwrap.dedent(
            """
        mntner:         TEST-MNT
        admin-c:        PERSON-TEST
        upd-to:         upd-to@example.com
        mnt-nfy:        mnt-nfy@example.com
        auth:           PGPKey-80F238C6
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """
        )
        rpsl_text = person_text + "\n\n" + mntner_text

        query_responses = iter(
            [
                [{"parsed_data": {"fingerpr": "8626 1D8D BEBD A4F5 4692  D64D A838 3BA7 80F2 38C6"}}],
                [],
                [{"object_text": mntner_text}],
                [{"object_text": mntner_text}],
                [],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_responses)

        handler = ChangeSubmissionHandler().load_text_blob(
            rpsl_text,
            pgp_fingerprint="8626 1D8DBEBD A4F5 4692  D64D A838 3BA7 80F2 38C6",
            request_meta={"Message-ID": "test", "From": "example@example.com"},
        )
        assert handler.status() == "SUCCESS", handler.submitter_report_human()

        assert flatten_mock_calls(mock_dq) == [
            ["object_classes", (["key-cert"],), {}],
            ["rpsl_pk", ("PGPKEY-80F238C6",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
        ]

        assert mock_dh.mock_calls[0][0] == "upsert_rpsl_object"
        assert mock_dh.mock_calls[0][1][0].pk() == "PERSON-TEST"
        assert mock_dh.mock_calls[1][0] == "upsert_rpsl_object"
        assert mock_dh.mock_calls[1][1][0].pk() == "TEST-MNT"
        assert mock_dh.mock_calls[2][0] == "commit"
        assert mock_dh.mock_calls[3][0] == "close"

        assert handler.submitter_report_human() == textwrap.dedent(
            f"""
        > Message-ID: test
        > From: example@example.com
        
        
        SUMMARY OF UPDATE:

        Number of objects found:                    2
        Number of objects processed successfully:   2
            Create:        1
            Modify:        1
            Delete:        0
        Number of objects processed with errors:    0
            Create:        0
            Modify:        0
            Delete:        0

        DETAILED EXPLANATION:
        
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ---
        Create succeeded: [person] PERSON-TEST
                
        ---
        Modify succeeded: [mntner] TEST-MNT

        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        )

        expected_notification = textwrap.dedent(
            f"""
            This is to notify you of changes in the TEST database
            or object authorisation failures.
            
            You may receive this message because you are listed in
            the notify attribute on the changed object(s), because
            you are listed in the mnt-nfy or upd-to attribute on a maintainer
            of the object(s), or the upd-to attribute on the maintainer of a
            parent of newly created object(s).
            
            This message is auto-generated.
            The request was made with the following details:
            
            > Message-ID: test
            > From: example@example.com
            
            
            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            Some objects in which you are referenced have been created,
            deleted or changed.
            
            ---
            Create succeeded for object below: [person] PERSON-TEST:
            
            person:         Placeholder Person Object
            address:        The Netherlands
            phone:          +31 20 000 0000
            nic-hdl:        PERSON-TEST
            mnt-by:         TEST-MNT
            e-mail:         email@example.com
            changed:        changed@example.com 20190701 # comment
            source:         TEST
            
            ---
            Modify succeeded for object below: [mntner] TEST-MNT:
            
            
            
            New version of this object:
            
            mntner:         TEST-MNT
            admin-c:        PERSON-TEST
            upd-to:         upd-to@example.com
            mnt-nfy:        mnt-nfy@example.com
            auth:           PGPKey-80F238C6
            mnt-by:         TEST-MNT
            changed:        changed@example.com 20190701 # comment
            source:         TEST
            
            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        """
        ).lstrip()
        handler.send_notification_target_reports()
        assert flatten_mock_calls(mock_email) == [
            ["", ("mnt-nfy@example.com", "Notification of TEST database changes", expected_notification), {}]
        ]

    def test_parse_invalid_new_objects_pgp_key_does_not_exist(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks

        person_text = textwrap.dedent(
            """
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 000 0000
        nic-hdl:        PERSON-TEST
        mnt-by:         TEST-MNT
        e-mail:         email@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """
        )

        mntner_text = textwrap.dedent(
            """
        mntner:         TEST-MNT
        admin-c:        PERSON-TEST
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """
        )
        rpsl_text = person_text + "\n\n" + mntner_text

        query_responses = iter(
            [
                [{"parsed_data": {"fingerpr": "8626 1D8D BEBD A4F5 XXXX  D64D A838 3BA7 80F2 38C6"}}],
                [],
                [{"object_text": mntner_text}],
                [{"object_text": mntner_text}],
                [],
                [],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_responses)

        handler = ChangeSubmissionHandler().load_text_blob(
            rpsl_text, pgp_fingerprint="8626 1D8DBEBD A4F5 4692  D64D A838 3BA7 80F2 38C6"
        )
        assert handler.status() == "FAILED", handler.submitter_report_human()

        assert flatten_mock_calls(mock_dq) == [
            ["object_classes", (["key-cert"],), {}],
            ["rpsl_pk", ("PGPKEY-80F238C6",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
        ]

        assert mock_dh.mock_calls[0][0] == "commit"
        assert mock_dh.mock_calls[1][0] == "close"

    def test_parse_valid_delete(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks

        rpsl_person = textwrap.dedent(
            """
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 00000000
        nic-hdl:        PERSON-TEST
        mnt-by:         TEST-MNT
        e-mail:         email@example.com
        notify:         notify@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """
        )

        query_responses = iter(
            [
                [{"object_text": rpsl_person}],
                [{"object_text": SAMPLE_MNTNER}],
                [],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_responses)

        handler = ChangeSubmissionHandler().load_text_blob(
            rpsl_person + "delete: delete\npassword: crypt-password\n"
        )
        assert handler.status() == "SUCCESS"

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["lookup_attrs_in", ({"tech-c", "zone-c", "admin-c"}, ["PERSON-TEST"]), {}],
        ]
        assert mock_dh.mock_calls[0][0] == "delete_rpsl_object"
        assert mock_dh.mock_calls[0][2]["rpsl_object"].pk() == "PERSON-TEST"
        assert mock_dh.mock_calls[0][2]["origin"] == JournalEntryOrigin.auth_change
        assert mock_dh.mock_calls[1][0] == "commit"
        assert mock_dh.mock_calls[2][0] == "close"

        assert handler.submitter_report_human() == textwrap.dedent(
            """
            SUMMARY OF UPDATE:

            Number of objects found:                    1
            Number of objects processed successfully:   1
                Create:        0
                Modify:        0
                Delete:        1
            Number of objects processed with errors:    0
                Create:        0
                Modify:        0
                Delete:        0

            DETAILED EXPLANATION:

            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            ---
            Delete succeeded: [person] PERSON-TEST

            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        )

        assert handler.submitter_report_json() == {
            "request_meta": {},
            "summary": {
                "failed": 0,
                "failed_create": 0,
                "failed_delete": 0,
                "failed_modify": 0,
                "objects_found": 1,
                "successful": 1,
                "successful_create": 0,
                "successful_delete": 1,
                "successful_modify": 0,
            },
            "objects": [
                {
                    "successful": True,
                    "type": "delete",
                    "error_messages": [],
                    "object_class": "person",
                    "rpsl_pk": "PERSON-TEST",
                    "info_messages": [],
                    "new_object_text": (
                        "person:         Placeholder Person Object\n"
                        "address:        The Netherlands\n"
                        "phone:          +31 20 00000000\n"
                        "nic-hdl:        PERSON-TEST\n"
                        "mnt-by:         TEST-MNT\n"
                        "e-mail:         email@example.com\n"
                        "notify:         notify@example.com\n"
                        "changed:        changed@example.com 20190701 "
                        "# comment\n"
                        "source:         TEST\n"
                    ),
                    "submitted_object_text": (
                        "person:         Placeholder Person "
                        "Object\n"
                        "address:        The Netherlands\n"
                        "phone:          +31 20 00000000\n"
                        "nic-hdl:        PERSON-TEST\n"
                        "mnt-by:         TEST-MNT\n"
                        "e-mail:         email@example.com\n"
                        "notify:         notify@example.com\n"
                        "changed:        changed@example.com "
                        "20190701 # comment\n"
                        "source:         TEST\n"
                    ),
                }
            ],
        }

        expected_notification = textwrap.dedent(
            """
            This is to notify you of changes in the TEST database
            or object authorisation failures.
            
            You may receive this message because you are listed in
            the notify attribute on the changed object(s), because
            you are listed in the mnt-nfy or upd-to attribute on a maintainer
            of the object(s), or the upd-to attribute on the maintainer of a
            parent of newly created object(s).
            
            This message is auto-generated.
            The request was made with the following details:
            
            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            Some objects in which you are referenced have been created,
            deleted or changed.
            
            ---
            Delete succeeded for object below: [person] PERSON-TEST:
            
            person:         Placeholder Person Object
            address:        The Netherlands
            phone:          +31 20 00000000
            nic-hdl:        PERSON-TEST
            mnt-by:         TEST-MNT
            e-mail:         email@example.com
            notify:         notify@example.com
            changed:        changed@example.com 20190701 # comment
            source:         TEST
            
            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        """
        ).lstrip()
        handler.send_notification_target_reports()

        # Notification recipients are kept in unordered data types at times, so call order may vary.
        sorted_mock_calls = sorted(flatten_mock_calls(mock_email), key=lambda x: x[1][0])
        assert sorted_mock_calls == [
            [
                "",
                ("mnt-nfy2@example.net", "Notification of TEST database changes", expected_notification),
                {},
            ],
            ["", ("mnt-nfy@example.net", "Notification of TEST database changes", expected_notification), {}],
            ["", ("notify@example.com", "Notification of TEST database changes", expected_notification), {}],
        ]

    def test_parse_invalid_cascading_failure(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks
        mock_dh.execute_query = lambda query: []

        rpsl_text = textwrap.dedent(
            """
        mntner:         TEST-MNT
        admin-c:        PERSON-TEST
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        auth:           MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.  # md5-password
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST

        override: override-password

        inetnum:        80.16.151.184 - 80.016.151.191
        netname:        NETECONOMY-MG41731
        descr:          TELECOM ITALIA LAB SPA
        country:        IT
        admin-c:        PERSON-TEST
        tech-c:         PERSON-TEST
        status:         ASSIGNED PA
        notify:         neteconomy.rete@telecomitalia.it
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        remarks:        remark
        
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 000 0000
        nic-hdl:        PERSON-TEST
        mnt-by:         OTHER-MNT
        e-mail:         email@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """
        )

        handler = ChangeSubmissionHandler().load_text_blob(rpsl_text)
        assert handler.status() == "FAILED"

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["rpsl_pk", ("80.16.151.184 - 80.16.151.191",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("OTHER-MNT",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["role", "person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["role", "person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["role", "person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
        ]
        assert flatten_mock_calls(mock_dh) == [
            ["commit", (), {}],
            ["close", (), {}],
        ]

        assert handler.submitter_report_human() == textwrap.dedent(
            """
        SUMMARY OF UPDATE:
        
        Number of objects found:                    3
        Number of objects processed successfully:   0
            Create:        0
            Modify:        0
            Delete:        0
        Number of objects processed with errors:    3
            Create:        3
            Modify:        0
            Delete:        0
        
        DETAILED EXPLANATION:
        
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ---
        Create FAILED: [mntner] TEST-MNT
        
        mntner:         TEST-MNT
        admin-c:        PERSON-TEST
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        auth:           MD5-pw DummyValue  # Filtered for security
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        
        ERROR: Object PERSON-TEST referenced in field admin-c not found in database TEST - must reference one of role, person.
        
        ---
        Create FAILED: [inetnum] 80.16.151.184 - 80.16.151.191
        
        inetnum:        80.16.151.184 - 80.016.151.191
        netname:        NETECONOMY-MG41731
        descr:          TELECOM ITALIA LAB SPA
        country:        IT
        admin-c:        PERSON-TEST
        tech-c:         PERSON-TEST
        status:         ASSIGNED PA
        notify:         neteconomy.rete@telecomitalia.it
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        remarks:        remark
        
        ERROR: Object PERSON-TEST referenced in field admin-c not found in database TEST - must reference one of role, person.
        ERROR: Object PERSON-TEST referenced in field tech-c not found in database TEST - must reference one of role, person.
        INFO: Address range 80.16.151.184 - 80.016.151.191 was reformatted as 80.16.151.184 - 80.16.151.191
        
        ---
        Create FAILED: [person] PERSON-TEST
        
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 000 0000
        nic-hdl:        PERSON-TEST
        mnt-by:         OTHER-MNT
        e-mail:         email@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        
        ERROR: Object OTHER-MNT referenced in field mnt-by not found in database TEST - must reference mntner.
        
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        )

        assert handler.submitter_report_json() == {
            "request_meta": {},
            "summary": {
                "failed": 3,
                "failed_create": 3,
                "failed_delete": 0,
                "failed_modify": 0,
                "objects_found": 3,
                "successful": 0,
                "successful_create": 0,
                "successful_delete": 0,
                "successful_modify": 0,
            },
            "objects": [
                {
                    "successful": False,
                    "type": "create",
                    "object_class": "mntner",
                    "rpsl_pk": "TEST-MNT",
                    "error_messages": [
                        "Object PERSON-TEST referenced in field "
                        "admin-c not found in database TEST - must "
                        "reference one of role, person."
                    ],
                    "info_messages": [],
                    "new_object_text": None,
                    "submitted_object_text": (
                        "mntner:         TEST-MNT\n"
                        "admin-c:        PERSON-TEST\n"
                        "upd-to:         unread@ripe.net\n"
                        "auth:           PGPKey-80F238C6\n"
                        "auth:           MD5-pw "
                        "DummyValue  # Filtered for security\n"
                        "mnt-by:         TEST-MNT\n"
                        "changed:        changed@example.com "
                        "20190701 # comment\n"
                        "source:         TEST\n"
                    ),
                },
                {
                    "successful": False,
                    "type": "create",
                    "object_class": "inetnum",
                    "rpsl_pk": "80.16.151.184 - 80.16.151.191",
                    "error_messages": [
                        (
                            "Object PERSON-TEST referenced in field "
                            "admin-c not found in database TEST - must "
                            "reference one of role, person."
                        ),
                        (
                            "Object PERSON-TEST referenced in field "
                            "tech-c not found in database TEST - must "
                            "reference one of role, person."
                        ),
                    ],
                    "info_messages": [
                        "Address range 80.16.151.184 - 80.016.151.191 "
                        "was reformatted as 80.16.151.184 - "
                        "80.16.151.191"
                    ],
                    "new_object_text": None,
                    "submitted_object_text": (
                        "inetnum:        80.16.151.184 - "
                        "80.016.151.191\n"
                        "netname:        NETECONOMY-MG41731\n"
                        "descr:          TELECOM ITALIA LAB "
                        "SPA\n"
                        "country:        IT\n"
                        "admin-c:        PERSON-TEST\n"
                        "tech-c:         PERSON-TEST\n"
                        "status:         ASSIGNED PA\n"
                        "notify:         "
                        "neteconomy.rete@telecomitalia.it\n"
                        "mnt-by:         TEST-MNT\n"
                        "changed:        changed@example.com "
                        "20190701 # comment\n"
                        "source:         TEST\n"
                        "remarks:        remark\n"
                    ),
                },
                {
                    "successful": False,
                    "type": "create",
                    "object_class": "person",
                    "rpsl_pk": "PERSON-TEST",
                    "error_messages": [
                        "Object OTHER-MNT referenced in field mnt-by "
                        "not found in database TEST - must reference "
                        "mntner."
                    ],
                    "info_messages": [],
                    "new_object_text": None,
                    "submitted_object_text": (
                        "person:         Placeholder Person "
                        "Object\n"
                        "address:        The Netherlands\n"
                        "phone:          +31 20 000 0000\n"
                        "nic-hdl:        PERSON-TEST\n"
                        "mnt-by:         OTHER-MNT\n"
                        "e-mail:         email@example.com\n"
                        "changed:        changed@example.com "
                        "20190701 # comment\n"
                        "source:         TEST\n"
                    ),
                },
            ],
        }

    def test_parse_invalid_single_failure_invalid_password(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks
        query_results = iter(
            [
                [],
                [{"object_text": SAMPLE_MNTNER}],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_results)

        rpsl_text = (
            textwrap.dedent(
                """
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 000 0000
        nic-hdl:        PERSON-TEST
        mnt-by:         TEST-MNT
        e-mail:         email@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """
            ).strip()
            + "\n"
        )

        submission_object = RPSLChangeSubmission.parse_obj(
            {
                "objects": [
                    {"object_text": rpsl_text},
                ],
                "passwords": ["invalid1", "invalid2"],
            }
        )

        handler = ChangeSubmissionHandler().load_change_submission(submission_object)
        assert handler.status() == "FAILED"

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
        ]
        assert flatten_mock_calls(mock_dh) == [
            ["commit", (), {}],
            ["close", (), {}],
        ]

        assert handler.submitter_report_human() == textwrap.dedent(
            """
            SUMMARY OF UPDATE:
            
            Number of objects found:                    1
            Number of objects processed successfully:   0
                Create:        0
                Modify:        0
                Delete:        0
            Number of objects processed with errors:    1
                Create:        1
                Modify:        0
                Delete:        0
            
            DETAILED EXPLANATION:
            
            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            ---
            Create FAILED: [person] PERSON-TEST
            
            person:         Placeholder Person Object
            address:        The Netherlands
            phone:          +31 20 000 0000
            nic-hdl:        PERSON-TEST
            mnt-by:         TEST-MNT
            e-mail:         email@example.com
            changed:        changed@example.com 20190701 # comment
            source:         TEST
            
            ERROR: Authorisation for person PERSON-TEST failed: must be authenticated by one of: TEST-MNT
            
            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        )

        expected_notification = textwrap.dedent(
            """
            This is to notify you of changes in the TEST database
            or object authorisation failures.
            
            You may receive this message because you are listed in
            the notify attribute on the changed object(s), because
            you are listed in the mnt-nfy or upd-to attribute on a maintainer
            of the object(s), or the upd-to attribute on the maintainer of a
            parent of newly created object(s).
            
            This message is auto-generated.
            The request was made with the following details:
            
            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            Some objects in which you are referenced were requested
            to be created, deleted or changed, but *failed* the 
            proper authorisation for any of the referenced maintainers.
            
            ---
            Create FAILED AUTHORISATION for object below: [person] PERSON-TEST:
            
            person:         Placeholder Person Object
            address:        The Netherlands
            phone:          +31 20 000 0000
            nic-hdl:        PERSON-TEST
            mnt-by:         TEST-MNT
            e-mail:         email@example.com
            changed:        changed@example.com 20190701 # comment
            source:         TEST
            
            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        """
        ).lstrip()
        handler.send_notification_target_reports()
        assert flatten_mock_calls(mock_email) == [
            ["", ("upd-to@example.net", "Notification of TEST database changes", expected_notification), {}],
        ]

    def test_parse_invalid_cascading_failure_invalid_password(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks

        query_results = iter(
            [
                [],
                [{"object_text": SAMPLE_MNTNER}],
                [],
                [{"object_text": SAMPLE_MNTNER}],
                [{"object_text": SAMPLE_MNTNER}],
                [{"object_text": SAMPLE_MNTNER}],
                [{"object_text": SAMPLE_MNTNER}],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_results)

        rpsl_text = textwrap.dedent(
            """
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 000 0000
        nic-hdl:        PERSON-TEST
        mnt-by:         TEST-MNT
        e-mail:         email@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST

        mntner:         TEST-MNT
        admin-c:        PERSON-TEST
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        auth:           MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.  # md5-password
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST

        password: wrong-password

        inetnum:        80.16.151.184 - 80.016.151.191
        netname:        NETECONOMY-MG41731
        descr:          TELECOM ITALIA LAB SPA
        country:        IT
        admin-c:        PERSON-TEST
        tech-c:         PERSON-TEST
        status:         ASSIGNED PA
        notify:         neteconomy.rete@telecomitalia.it
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        remarks:        remark
        """
        )

        handler = ChangeSubmissionHandler().load_text_blob(rpsl_text)
        assert handler.status() == "FAILED"

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["rpsl_pk", ("80.16.151.184 - 80.16.151.191",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"OTHER1-MNT", "OTHER2-MNT"},), {}],
        ]
        assert flatten_mock_calls(mock_dh) == [
            ["commit", (), {}],
            ["close", (), {}],
        ]

        assert handler.submitter_report_human() == textwrap.dedent(
            """
        SUMMARY OF UPDATE:

        Number of objects found:                    3
        Number of objects processed successfully:   0
            Create:        0
            Modify:        0
            Delete:        0
        Number of objects processed with errors:    3
            Create:        2
            Modify:        1
            Delete:        0

        DETAILED EXPLANATION:

        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ---
        Create FAILED: [person] PERSON-TEST
        
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 000 0000
        nic-hdl:        PERSON-TEST
        mnt-by:         TEST-MNT
        e-mail:         email@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        
        ERROR: Authorisation for person PERSON-TEST failed: must be authenticated by one of: TEST-MNT
        
        ---
        Modify FAILED: [mntner] TEST-MNT
        
        mntner:         TEST-MNT
        admin-c:        PERSON-TEST
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        auth:           MD5-pw DummyValue  # Filtered for security
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        
        ERROR: Authorisation for mntner TEST-MNT failed: must be authenticated by one of: TEST-MNT
        ERROR: Authorisation for mntner TEST-MNT failed: must be authenticated by one of: TEST-MNT, OTHER1-MNT, OTHER2-MNT
        ERROR: Authorisation failed for the auth methods on this mntner object.
        
        ---
        Create FAILED: [inetnum] 80.16.151.184 - 80.16.151.191
        
        inetnum:        80.16.151.184 - 80.016.151.191
        netname:        NETECONOMY-MG41731
        descr:          TELECOM ITALIA LAB SPA
        country:        IT
        admin-c:        PERSON-TEST
        tech-c:         PERSON-TEST
        status:         ASSIGNED PA
        notify:         neteconomy.rete@telecomitalia.it
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        remarks:        remark
        
        ERROR: Authorisation for inetnum 80.16.151.184 - 80.16.151.191 failed: must be authenticated by one of: TEST-MNT
        INFO: Address range 80.16.151.184 - 80.016.151.191 was reformatted as 80.16.151.184 - 80.16.151.191

        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        )

    def test_parse_invalid_object_delete_syntax(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks
        mock_dh.execute_query = lambda query: []

        submission_object = RPSLChangeSubmission.parse_obj(
            {
                "objects": [
                    {
                        "attributes": [
                            {"name": "person", "value": "Placeholder Person Object"},
                            {"name": "nic-hdl", "value": "PERSON-TEST"},
                            {"name": "changed", "value": "changed@example.com 20190701 # comment"},
                            {"name": "source", "value": "TEST"},
                        ]
                    },
                ],
                "passwords": ["invalid1", "invalid2"],
            }
        )

        handler = ChangeSubmissionHandler().load_change_submission(submission_object, delete=True)
        assert handler.status() == "FAILED"

        assert flatten_mock_calls(mock_dq) == []
        assert mock_dh.mock_calls[0][0] == "commit"
        assert mock_dh.mock_calls[1][0] == "close"

        assert handler.submitter_report_human() == textwrap.dedent(
            """
        SUMMARY OF UPDATE:
        
        Number of objects found:                    1
        Number of objects processed successfully:   0
            Create:        0
            Modify:        0
            Delete:        0
        Number of objects processed with errors:    1
            Create:        0
            Modify:        0
            Delete:        1
        
        DETAILED EXPLANATION:
        
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ---
        Delete FAILED: [person] PERSON-TEST
        
        person: Placeholder Person Object
        nic-hdl: PERSON-TEST
        changed: changed@example.com 20190701 # comment
        source: TEST
        
        ERROR: Mandatory attribute "address" on object person is missing
        ERROR: Mandatory attribute "phone" on object person is missing
        ERROR: Mandatory attribute "e-mail" on object person is missing
        ERROR: Mandatory attribute "mnt-by" on object person is missing
        ERROR: Can not delete object: no object found for this key in this database.
 
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        )

    def test_load_suspension_submission(self, prepare_mocks, monkeypatch):
        mock_dq, mock_dh, mock_email = prepare_mocks
        mock_handle_change_requests = Mock(ChangeSubmissionHandler._handle_change_requests)
        monkeypatch.setattr(
            "irrd.updates.handler.ChangeSubmissionHandler._handle_change_requests",
            mock_handle_change_requests,
        )

        data = {
            "objects": [{"mntner": "DASHCARE-MNT", "source": "DASHCARE", "request_type": "reactivate"}],
            "override": "override-pw",
        }
        submission_object = RPSLSuspensionSubmission.parse_obj(data)

        ChangeSubmissionHandler().load_suspension_submission(submission_object)
        assert mock_handle_change_requests.assert_called_once
        (requests, reference_validator, auth_validator) = mock_handle_change_requests.call_args[0]
        assert len(requests) == 1
        assert "DASHCARE-MNT" in requests[0].rpsl_text_submitted
        assert requests[0].request_type == SuspensionRequestType.REACTIVATE
        assert auth_validator.overrides == ["override-pw"]
