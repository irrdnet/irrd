# flake8: noqa: W293
import datetime
import textwrap
from unittest.mock import Mock

import pytest

from irrd.utils.rpsl_samples import SAMPLE_MNTNER
from irrd.utils.test_utils import flatten_mock_calls
from ..handler import ChangeSubmissionHandler


@pytest.fixture()
def prepare_mocks(monkeypatch, config_override):
    monkeypatch.setenv('IRRD_SOURCES_TEST_AUTHORITATIVE', '1')
    mock_dh = Mock()
    monkeypatch.setattr('irrd.updates.handler.DatabaseHandler', lambda: mock_dh)
    mock_dq = Mock()
    monkeypatch.setattr('irrd.updates.handler.RPSLDatabaseQuery', lambda: mock_dq)
    monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
    monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)
    mock_email = Mock()
    monkeypatch.setattr('irrd.utils.email.send_email', mock_email)
    config_override({'auth': {'override_password': '$1$J6KycItM$MbPaBU6iFSGFV299Rk7Di0'}})
    yield mock_dq, mock_dh, mock_email


class TestChangeSubmissionHandler:
    # NOTE: the scope of this test also includes ChangeRequest, ReferenceValidator and AuthValidator -
    # this is more of an update handler integration test.
    expected_changed_date = datetime.datetime.now().strftime('%Y%m%d')

    def test_parse_valid_new_objects_with_override(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks
        mock_dh.execute_query = lambda query: []

        rpsl_text = textwrap.dedent("""
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
        """)

        handler = ChangeSubmissionHandler(rpsl_text)
        assert handler.status() == 'SUCCESS'

        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['TEST'],), {}], ['object_classes', (['person'],), {}], ['rpsl_pk', ('PERSON-TEST',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pk', ('TEST-MNT',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}],
        ]

        assert mock_dh.mock_calls[0][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[0][1][0].pk() == 'PERSON-TEST'
        assert mock_dh.mock_calls[1][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[1][1][0].pk() == 'TEST-MNT'
        assert mock_dh.mock_calls[2][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[2][1][0].pk() == '80.16.151.184 - 80.16.151.191'
        assert mock_dh.mock_calls[3][0] == 'commit'
        assert mock_dh.mock_calls[4][0] == 'close'

        assert handler.submitter_report() == textwrap.dedent("""
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
        """)

    def test_parse_valid_new_person_existing_mntner_pgp_key(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks

        person_text = textwrap.dedent("""
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 000 0000
        nic-hdl:        PERSON-TEST
        mnt-by:         TEST-MNT
        e-mail:         email@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """)

        mntner_text = textwrap.dedent("""
        mntner:         TEST-MNT
        admin-c:        PERSON-TEST
        upd-to:         upd-to@example.com
        mnt-nfy:        mnt-nfy@example.com
        auth:           PGPKey-80F238C6
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """)
        rpsl_text = person_text + '\n\n' + mntner_text

        query_responses = iter([
            [{'parsed_data': {'fingerpr': '8626 1D8D BEBD A4F5 4692  D64D A838 3BA7 80F2 38C6'}}],
            [],
            [{'object_text': mntner_text}],
            [{'object_text': mntner_text}],
            [],
        ])
        mock_dh.execute_query = lambda query: next(query_responses)

        handler = ChangeSubmissionHandler(rpsl_text, pgp_fingerprint='8626 1D8DBEBD A4F5 4692  D64D A838 3BA7 80F2 38C6',
                                          request_meta={'Message-ID': 'test', 'From': 'example@example.com'})
        assert handler.status() == 'SUCCESS', handler.submitter_report()

        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['key-cert'],), {}], ['rpsl_pk', ('PGPKEY-80F238C6',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['person'],), {}], ['rpsl_pk', ('PERSON-TEST',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pk', ('TEST-MNT',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pks', ({'TEST-MNT'},), {}],
        ]

        assert mock_dh.mock_calls[0][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[0][1][0].pk() == 'PERSON-TEST'
        assert mock_dh.mock_calls[1][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[1][1][0].pk() == 'TEST-MNT'
        assert mock_dh.mock_calls[2][0] == 'commit'
        assert mock_dh.mock_calls[3][0] == 'close'

        assert handler.submitter_report() == textwrap.dedent(f"""
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
        
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 000 0000
        nic-hdl:        PERSON-TEST
        mnt-by:         TEST-MNT
        e-mail:         email@example.com
        changed:        changed@example.com {self.expected_changed_date} # comment
        source:         TEST
        
        INFO: Set date in changed line "changed@example.com 20190701 # comment" to today.
        
        ---
        Modify succeeded: [mntner] TEST-MNT

        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """)

        expected_notification = textwrap.dedent(f"""
            This is to notify you of changes in the TEST database
            or object authorisation failures.
            
            You may receive this message because you are listed in
            the notify attribute on the changed object(s), or because
            you are listed in the mnt-nfy or upd-to attribute on a maintainer
            of the object(s).
            
            This message is auto-generated.
            The request was made by email, with the following details:
            
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
            changed:        changed@example.com {self.expected_changed_date} # comment
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

        """).lstrip()
        handler.send_notification_target_reports()
        assert flatten_mock_calls(mock_email) == [
            ['', ('mnt-nfy@example.com', 'Notification of TEST database changes', expected_notification), {}]
        ]

    def test_parse_invalid_new_objects_pgp_key_does_not_exist(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks

        person_text = textwrap.dedent("""
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 000 0000
        nic-hdl:        PERSON-TEST
        mnt-by:         TEST-MNT
        e-mail:         email@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """)

        mntner_text = textwrap.dedent("""
        mntner:         TEST-MNT
        admin-c:        PERSON-TEST
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """)
        rpsl_text = person_text + '\n\n' + mntner_text

        query_responses = iter([
            [{'parsed_data': {'fingerpr': '8626 1D8D BEBD A4F5 XXXX  D64D A838 3BA7 80F2 38C6'}}],
            [],
            [{'object_text': mntner_text}],
            [{'object_text': mntner_text}],
            [],
            [],
        ])
        mock_dh.execute_query = lambda query: next(query_responses)

        handler = ChangeSubmissionHandler(rpsl_text, pgp_fingerprint='8626 1D8DBEBD A4F5 4692  D64D A838 3BA7 80F2 38C6')
        assert handler.status() == 'FAILED', handler.submitter_report()

        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['key-cert'],), {}], ['rpsl_pk', ('PGPKEY-80F238C6',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['person'],), {}], ['rpsl_pk', ('PERSON-TEST',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pk', ('TEST-MNT',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pks', ({'TEST-MNT'},), {}],
        ]

        assert mock_dh.mock_calls[0][0] == 'commit'
        assert mock_dh.mock_calls[1][0] == 'close'

    def test_parse_valid_delete(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks

        rpsl_person = textwrap.dedent("""
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 00000000
        nic-hdl:        PERSON-TEST
        mnt-by:         TEST-MNT
        e-mail:         email@example.com
        notify:         notify@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """)

        query_responses = iter([
            [{'object_text': rpsl_person}],
            [{'object_text': SAMPLE_MNTNER}],
            [],
        ])
        mock_dh.execute_query = lambda query: next(query_responses)

        handler = ChangeSubmissionHandler(rpsl_person + 'delete: delete\npassword: crypt-password\n')
        assert handler.status() == 'SUCCESS'

        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['TEST'],), {}], ['object_classes', (['person'],), {}],
            ['rpsl_pk', ('PERSON-TEST',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pks', ({'TEST-MNT'},), {}],
            ['sources', (['TEST'],), {}],
            ['lookup_attrs_in', ({'tech-c', 'zone-c', 'admin-c'}, ['PERSON-TEST']), {}]
        ]
        assert mock_dh.mock_calls[0][0] == 'delete_rpsl_object'
        assert mock_dh.mock_calls[0][1][0].pk() == 'PERSON-TEST'
        assert mock_dh.mock_calls[1][0] == 'commit'
        assert mock_dh.mock_calls[2][0] == 'close'

        assert handler.submitter_report() == textwrap.dedent("""
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
        """)

        expected_notification = textwrap.dedent("""
            This is to notify you of changes in the TEST database
            or object authorisation failures.
            
            You may receive this message because you are listed in
            the notify attribute on the changed object(s), or because
            you are listed in the mnt-nfy or upd-to attribute on a maintainer
            of the object(s).
            
            This message is auto-generated.
            The request was made by email, with the following details:
            
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

        """).lstrip()
        handler.send_notification_target_reports()

        # Notification recipients are kept in unordered data types at times, so call order may vary.
        sorted_mock_calls = sorted(flatten_mock_calls(mock_email), key=lambda x: x[1][0])
        assert sorted_mock_calls == [
            ['', ('mnt-nfy2@example.net', 'Notification of TEST database changes', expected_notification), {}],
            ['', ('mnt-nfy@example.net', 'Notification of TEST database changes', expected_notification), {}],
            ['', ('notify@example.com', 'Notification of TEST database changes', expected_notification), {}],
        ]

    def test_parse_invalid_cascading_failure(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks
        mock_dh.execute_query = lambda query: []

        rpsl_text = textwrap.dedent("""
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
        """)

        handler = ChangeSubmissionHandler(rpsl_text)
        assert handler.status() == 'FAILED'

        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['TEST'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pk', ('TEST-MNT',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['person'],), {}], ['rpsl_pk', ('PERSON-TEST',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pk', ('OTHER-MNT',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['role', 'person'],), {}], ['rpsl_pk', ('PERSON-TEST',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['role', 'person'],), {}], ['rpsl_pk', ('PERSON-TEST',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['role', 'person'],), {}], ['rpsl_pk', ('PERSON-TEST',), {}],
        ]
        assert flatten_mock_calls(mock_dh) == [
            ['commit', (), {}],
            ['close', (), {}],
        ]

        assert handler.submitter_report() == textwrap.dedent("""
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
        auth:           MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.  # md5-password
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
        """)

    def test_parse_invalid_single_failure_invalid_password(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks
        query_results = iter([
            [],
            [{'object_text': SAMPLE_MNTNER}],
        ])
        mock_dh.execute_query = lambda query: next(query_results)

        rpsl_text = textwrap.dedent("""
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 000 0000
        nic-hdl:        PERSON-TEST
        mnt-by:         TEST-MNT
        e-mail:         email@example.com
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """)

        handler = ChangeSubmissionHandler(rpsl_text)
        assert handler.status() == 'FAILED'

        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['TEST'],), {}], ['object_classes', (['person'],), {}], ['rpsl_pk', ('PERSON-TEST',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pks', ({'TEST-MNT'},), {}]
        ]
        assert flatten_mock_calls(mock_dh) == [
            ['commit', (), {}],
            ['close', (), {}],
        ]

        assert handler.submitter_report() == textwrap.dedent("""
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
            
            ERROR: Authorisation for person PERSON-TEST failed: must by authenticated by one of: TEST-MNT
            
            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """)

        expected_notification = textwrap.dedent("""
            This is to notify you of changes in the TEST database
            or object authorisation failures.
            
            You may receive this message because you are listed in
            the notify attribute on the changed object(s), or because
            you are listed in the mnt-nfy or upd-to attribute on a maintainer
            of the object(s).
            
            This message is auto-generated.
            The request was made by email, with the following details:
            
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

        """).lstrip()
        handler.send_notification_target_reports()
        assert flatten_mock_calls(mock_email) == [
            ['', ('upd-to@example.net', 'Notification of TEST database changes', expected_notification), {}],
        ]

    def test_parse_invalid_cascading_failure_invalid_password(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks

        query_results = iter([
            [],
            [{'object_text': SAMPLE_MNTNER}],
            [],
            [{'object_text': SAMPLE_MNTNER}],
            [{'object_text': SAMPLE_MNTNER}],
            [{'object_text': SAMPLE_MNTNER}],
            [{'object_text': SAMPLE_MNTNER}],
        ])
        mock_dh.execute_query = lambda query: next(query_results)

        rpsl_text = textwrap.dedent("""
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
        """)

        handler = ChangeSubmissionHandler(rpsl_text)
        assert handler.status() == 'FAILED'

        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['TEST'],), {}], ['object_classes', (['person'],), {}], ['rpsl_pk', ('PERSON-TEST',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pk', ('TEST-MNT',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pks', ({'TEST-MNT'},), {}],
            ['sources', (['TEST'],), {}], ['object_classes', (['mntner'],), {}],
            ['rpsl_pks', ({'OTHER1-MNT', 'OTHER2-MNT'},), {}],
        ]
        assert flatten_mock_calls(mock_dh) == [
            ['commit', (), {}],
            ['close', (), {}],
        ]

        assert handler.submitter_report() == textwrap.dedent("""
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
        
        ERROR: Authorisation for person PERSON-TEST failed: must by authenticated by one of: TEST-MNT
        
        ---
        Modify FAILED: [mntner] TEST-MNT
        
        mntner:         TEST-MNT
        admin-c:        PERSON-TEST
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        auth:           MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.  # md5-password
        mnt-by:         TEST-MNT
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        
        ERROR: Authorisation for mntner TEST-MNT failed: must by authenticated by one of: TEST-MNT
        ERROR: Authorisation for mntner TEST-MNT failed: must by authenticated by one of: TEST-MNT, OTHER1-MNT, OTHER2-MNT
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
        
        ERROR: Authorisation for inetnum 80.16.151.184 - 80.16.151.191 failed: must by authenticated by one of: TEST-MNT
        INFO: Address range 80.16.151.184 - 80.016.151.191 was reformatted as 80.16.151.184 - 80.16.151.191

        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """)

    def test_parse_invalid_object_syntax(self, prepare_mocks):
        mock_dq, mock_dh, mock_email = prepare_mocks
        mock_dh.execute_query = lambda query: []

        rpsl_text = textwrap.dedent("""
        person:         Placeholder Person Object
        nic-hdl:        PERSON-TEST
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        """)

        handler = ChangeSubmissionHandler(rpsl_text)
        assert handler.status() == 'FAILED'

        assert flatten_mock_calls(mock_dq) == []
        assert mock_dh.mock_calls[0][0] == 'commit'
        assert mock_dh.mock_calls[1][0] == 'close'

        assert handler.submitter_report() == textwrap.dedent("""
        SUMMARY OF UPDATE:
        
        Number of objects found:                    1
        Number of objects processed successfully:   0
            Create:        0
            Modify:        0
            Delete:        0
        Number of objects processed with errors:    1
            Create:        0
            Modify:        0
            Delete:        0
        
        DETAILED EXPLANATION:
        
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ---
        Request FAILED: [person] PERSON-TEST
        
        person:         Placeholder Person Object
        nic-hdl:        PERSON-TEST
        changed:        changed@example.com 20190701 # comment
        source:         TEST
        
        ERROR: Mandatory attribute "address" on object person is missing
        ERROR: Mandatory attribute "phone" on object person is missing
        ERROR: Mandatory attribute "e-mail" on object person is missing
        ERROR: Mandatory attribute "mnt-by" on object person is missing
        
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """)
