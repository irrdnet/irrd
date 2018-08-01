# flake8: noqa: W293

import textwrap
from unittest.mock import Mock

import pytest

from irrd.updates.handler import UpdateRequestHandler
from irrd.utils.rpsl_samples import SAMPLE_MNTNER
from irrd.utils.test_utils import flatten_mock_calls


@pytest.fixture()
def prepare_mocks(monkeypatch):
    mock_dh = Mock()
    monkeypatch.setattr('irrd.updates.handler.DatabaseHandler', lambda: mock_dh)
    mock_dq = Mock()
    monkeypatch.setattr('irrd.updates.handler.RPSLDatabaseQuery', lambda: mock_dq)
    monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
    monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)
    yield mock_dq, mock_dh


class TestUpdateRequestHandler:
    # NOTE: the scope of this test also includes UpdateRequest, ReferenceValidator and AuthValidator -
    # this is more of an update handler integration test.

    def test_parse_valid_new_objects(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks
        mock_dh.execute_query = lambda query: []

        rpsl_text = textwrap.dedent("""
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 535 4444
        nic-hdl:        DUMy-RIPE
        mnt-by:         as760-mnt
        e-mail:         bitbucket@ripe.net
        changed:        2009-07-24T17:00:00Z
        source:         RIPE

        mntner:         AS760-MNT
        admin-c:        DUMY-RIPE
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        auth:           MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.  # md5-password
        mnt-by:         AS760-MNT
        changed:        2016-10-05T10:41:15Z
        source:         RIPE
        
        password: md5-password

        inetnum:        80.16.151.184 - 80.016.151.191
        netname:        NETECONOMY-MG41731
        descr:          TELECOM ITALIA LAB SPA
        country:        IT
        admin-c:        DUMY-RIPE
        tech-c:         DUMY-RIPE
        status:         ASSIGNED PA
        notify:         neteconomy.rete@telecomitalia.it
        mnt-by:         AS760-mnt
        changed:        2001-09-21T22:08:01Z
        source:         RIPE
        remarks:        remark
        """)

        handler = UpdateRequestHandler(rpsl_text)
        assert handler.status() == 'SUCCESS'

        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}], ['object_classes', (['person'],), {}], ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pk', ('AS760-MNT',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}],
        ]

        assert mock_dh.mock_calls[0][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[0][1][0].pk() == 'DUMY-RIPE'
        assert mock_dh.mock_calls[1][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[1][1][0].pk() == 'AS760-MNT'
        assert mock_dh.mock_calls[2][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[2][1][0].pk() == '80.16.151.184 - 80.16.151.191'
        assert mock_dh.mock_calls[3][0] == 'commit'

        assert handler.user_report() == textwrap.dedent("""
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
        Create succeeded: [person] DUMY-RIPE
        
        ---
        Create succeeded: [mntner] AS760-MNT
        
        ---
        Create succeeded: [inetnum] 80.16.151.184 - 80.16.151.191
        
        inetnum:        80.16.151.184 - 80.016.151.191
        netname:        NETECONOMY-MG41731
        descr:          TELECOM ITALIA LAB SPA
        country:        IT
        admin-c:        DUMY-RIPE
        tech-c:         DUMY-RIPE
        status:         ASSIGNED PA
        notify:         neteconomy.rete@telecomitalia.it
        mnt-by:         AS760-mnt
        changed:        2001-09-21T22:08:01Z
        source:         RIPE
        remarks:        remark
        
        INFO: Address range 80.16.151.184 - 80.016.151.191 was reformatted as 80.16.151.184 - 80.16.151.191
        
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """)

    def test_parse_valid_new_objects_pgp_key(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        person_text = textwrap.dedent("""
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 535 4444
        nic-hdl:        DUMy-RIPE
        mnt-by:         as760-mnt
        e-mail:         bitbucket@ripe.net
        changed:        2009-07-24T17:00:00Z
        source:         RIPE
        """)

        mntner_text = textwrap.dedent("""
        mntner:         AS760-MNT
        admin-c:        DUMY-RIPE
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        mnt-by:         AS760-MNT
        changed:        2016-10-05T10:41:15Z
        source:         RIPE
        """)
        rpsl_text = person_text + "\n\n" + mntner_text

        query_responses = iter([
            [{'parsed_data': {'fingerpr': '8626 1D8D BEBD A4F5 4692  D64D A838 3BA7 80F2 38C6'}}],
            [],
            [{'object_text': mntner_text}],
            [{'object_text': mntner_text}],
            [],
        ])
        mock_dh.execute_query = lambda query: next(query_responses)

        handler = UpdateRequestHandler(rpsl_text, pgp_fingerprint='8626 1D8DBEBD A4F5 4692  D64D A838 3BA7 80F2 38C6',
                                       request_meta={'Message-ID': 'test', 'From': 'example@example.com'})
        assert handler.status() == 'SUCCESS', handler.user_report()

        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['key-cert'],), {}], ['rpsl_pk', ('PGPKEY-80F238C6',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['person'],), {}], ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pk', ('AS760-MNT',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pks', (['AS760-MNT'],), {}]
        ]

        assert mock_dh.mock_calls[0][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[0][1][0].pk() == 'DUMY-RIPE'
        assert mock_dh.mock_calls[1][0] == 'upsert_rpsl_object'
        assert mock_dh.mock_calls[1][1][0].pk() == 'AS760-MNT'
        assert mock_dh.mock_calls[2][0] == 'commit'

        assert handler.user_report() == textwrap.dedent("""
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
        Create succeeded: [person] DUMY-RIPE

        ---
        Modify succeeded: [mntner] AS760-MNT

        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """)

    def test_parse_invalid_new_objects_pgp_key_does_not_exist(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        person_text = textwrap.dedent("""
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 535 4444
        nic-hdl:        DUMy-RIPE
        mnt-by:         as760-mnt
        e-mail:         bitbucket@ripe.net
        changed:        2009-07-24T17:00:00Z
        source:         RIPE
        """)

        mntner_text = textwrap.dedent("""
        mntner:         AS760-MNT
        admin-c:        DUMY-RIPE
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        mnt-by:         AS760-MNT
        changed:        2016-10-05T10:41:15Z
        source:         RIPE
        """)
        rpsl_text = person_text + "\n\n" + mntner_text

        query_responses = iter([
            [{'parsed_data': {'fingerpr': '8626 1D8D BEBD A4F5 XXXX  D64D A838 3BA7 80F2 38C6'}}],
            [],
            [{'object_text': mntner_text}],
            [{'object_text': mntner_text}],
            [],
        ])
        mock_dh.execute_query = lambda query: next(query_responses)

        handler = UpdateRequestHandler(rpsl_text, pgp_fingerprint='8626 1D8DBEBD A4F5 4692  D64D A838 3BA7 80F2 38C6')
        assert handler.status() == 'FAILED', handler.user_report()

        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['key-cert'],), {}], ['rpsl_pk', ('PGPKEY-80F238C6',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['person'],), {}], ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pk', ('AS760-MNT',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pks', (['AS760-MNT'],), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pks', (['AS760-MNT'],), {}],
        ]

        assert mock_dh.mock_calls[0][0] == 'commit'

    def test_parse_valid_delete(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        rpsl_person = textwrap.dedent("""
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 535 4444
        nic-hdl:        DUMy-RIPE
        mnt-by:         as760-mnt
        e-mail:         bitbucket@ripe.net
        changed:        2009-07-24T17:00:00Z
        source:         RIPE
        """)

        query_responses = iter([
            [{'object_text': rpsl_person}],
            [{'object_text': SAMPLE_MNTNER}],
            [],
        ])
        mock_dh.execute_query = lambda query: next(query_responses)

        handler = UpdateRequestHandler(rpsl_person + 'delete: delete\npassword: crypt-password\n')
        assert handler.status() == 'SUCCESS'

        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}], ['object_classes', (['person'],), {}],
            ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pks', (['AS760-MNT'],), {}],
            ['sources', (['RIPE'],), {}],
            ['lookup_attrs_in', ({'tech-c', 'zone-c', 'admin-c'}, ['DUMY-RIPE']), {}]
        ]
        assert mock_dh.mock_calls[0][0] == 'delete_rpsl_object'
        assert mock_dh.mock_calls[0][1][0].pk() == 'DUMY-RIPE'
        assert mock_dh.mock_calls[1][0] == 'commit'

        assert handler.user_report() == textwrap.dedent("""
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
            Delete succeeded: [person] DUMY-RIPE

            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """)

    def test_parse_invalid_cascading_failure(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks
        mock_dh.execute_query = lambda query: []

        rpsl_text = textwrap.dedent("""
        mntner:         AS760-MNT
        admin-c:        DUMY-RIPE
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        auth:           MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.  # md5-password
        mnt-by:         AS760-MNT
        changed:        2016-10-05T10:41:15Z
        source:         RIPE

        password: md5-password

        inetnum:        80.16.151.184 - 80.016.151.191
        netname:        NETECONOMY-MG41731
        descr:          TELECOM ITALIA LAB SPA
        country:        IT
        admin-c:        DUMY-RIPE
        tech-c:         DUMY-RIPE
        status:         ASSIGNED PA
        notify:         neteconomy.rete@telecomitalia.it
        mnt-by:         AS760-mnt
        changed:        2001-09-21T22:08:01Z
        source:         RIPE
        remarks:        remark
        
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 535 4444
        nic-hdl:        DUMy-RIPE
        mnt-by:         OTHER-MNT
        e-mail:         bitbucket@ripe.net
        changed:        2009-07-24T17:00:00Z
        source:         RIPE
        """)

        handler = UpdateRequestHandler(rpsl_text)
        assert handler.status() == 'FAILED'

        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pk', ('AS760-MNT',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}], ['sources', (['RIPE'],), {}],
            ['object_classes', (['person'],), {}], ['rpsl_pk', ('DUMY-RIPE',), {}], ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}], ['rpsl_pks', (['OTHER-MNT'],), {}], ['sources', (['RIPE'],), {}],
            ['object_classes', (['role', 'person'],), {}], ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['role', 'person'],), {}],
            ['rpsl_pk', ('DUMY-RIPE',), {}], ['sources', (['RIPE'],), {}],
            ['object_classes', (['role', 'person'],), {}], ['rpsl_pk', ('DUMY-RIPE',), {}]
        ]
        assert flatten_mock_calls(mock_dh) == [['commit', (), {}]]

        assert handler.user_report() == textwrap.dedent("""
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
        Create FAILED: [mntner] AS760-MNT
        
        mntner:         AS760-MNT
        admin-c:        DUMY-RIPE
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        auth:           MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.  # md5-password
        mnt-by:         AS760-MNT
        changed:        2016-10-05T10:41:15Z
        source:         RIPE
        
        ERROR: Object DUMY-RIPE referenced in field admin-c not found in database RIPE - must reference one of role, person.
        
        ---
        Create FAILED: [inetnum] 80.16.151.184 - 80.16.151.191
        
        inetnum:        80.16.151.184 - 80.016.151.191
        netname:        NETECONOMY-MG41731
        descr:          TELECOM ITALIA LAB SPA
        country:        IT
        admin-c:        DUMY-RIPE
        tech-c:         DUMY-RIPE
        status:         ASSIGNED PA
        notify:         neteconomy.rete@telecomitalia.it
        mnt-by:         AS760-mnt
        changed:        2001-09-21T22:08:01Z
        source:         RIPE
        remarks:        remark
        
        ERROR: Object DUMY-RIPE referenced in field admin-c not found in database RIPE - must reference one of role, person.
        ERROR: Object DUMY-RIPE referenced in field tech-c not found in database RIPE - must reference one of role, person.
        INFO: Address range 80.16.151.184 - 80.016.151.191 was reformatted as 80.16.151.184 - 80.16.151.191
        
        ---
        Create FAILED: [person] DUMY-RIPE
        
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 535 4444
        nic-hdl:        DUMy-RIPE
        mnt-by:         OTHER-MNT
        e-mail:         bitbucket@ripe.net
        changed:        2009-07-24T17:00:00Z
        source:         RIPE
        
        ERROR: Authorisation for person DUMY-RIPE failed: must by authenticated by one of: OTHER-MNT
        
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """)

    def test_parse_invalid_cascading_failure_invalid_password(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks
        mock_dh.execute_query = lambda query: []

        rpsl_text = textwrap.dedent("""
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 535 4444
        nic-hdl:        DUMy-RIPE
        mnt-by:         as760-mnt
        e-mail:         bitbucket@ripe.net
        changed:        2009-07-24T17:00:00Z
        source:         RIPE

        mntner:         AS760-MNT
        admin-c:        DUMY-RIPE
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        auth:           MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.  # md5-password
        mnt-by:         AS760-MNT
        changed:        2016-10-05T10:41:15Z
        source:         RIPE

        password: wrong-password

        inetnum:        80.16.151.184 - 80.016.151.191
        netname:        NETECONOMY-MG41731
        descr:          TELECOM ITALIA LAB SPA
        country:        IT
        admin-c:        DUMY-RIPE
        tech-c:         DUMY-RIPE
        status:         ASSIGNED PA
        notify:         neteconomy.rete@telecomitalia.it
        mnt-by:         AS760-mnt
        changed:        2001-09-21T22:08:01Z
        source:         RIPE
        remarks:        remark
        """)

        handler = UpdateRequestHandler(rpsl_text)
        assert handler.status() == 'FAILED'

        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}], ['object_classes', (['person'],), {}], ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pk', ('AS760-MNT',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}], ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}], ['rpsl_pks', (['AS760-MNT'],), {}], ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}], ['rpsl_pks', (['AS760-MNT'],), {}]
        ]
        assert flatten_mock_calls(mock_dh) == [['commit', (), {}]]

        assert handler.user_report() == textwrap.dedent("""
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
        Create FAILED: [person] DUMY-RIPE
        
        person:         Placeholder Person Object
        address:        The Netherlands
        phone:          +31 20 535 4444
        nic-hdl:        DUMy-RIPE
        mnt-by:         as760-mnt
        e-mail:         bitbucket@ripe.net
        changed:        2009-07-24T17:00:00Z
        source:         RIPE
        
        ERROR: Authorisation for person DUMY-RIPE failed: must by authenticated by one of: AS760-MNT
        
        ---
        Create FAILED: [mntner] AS760-MNT
        
        mntner:         AS760-MNT
        admin-c:        DUMY-RIPE
        upd-to:         unread@ripe.net
        auth:           PGPKey-80F238C6
        auth:           MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.  # md5-password
        mnt-by:         AS760-MNT
        changed:        2016-10-05T10:41:15Z
        source:         RIPE
        
        ERROR: Authorisation failed for the auth methods on this mntner object.
        
        ---
        Create FAILED: [inetnum] 80.16.151.184 - 80.16.151.191
        
        inetnum:        80.16.151.184 - 80.016.151.191
        netname:        NETECONOMY-MG41731
        descr:          TELECOM ITALIA LAB SPA
        country:        IT
        admin-c:        DUMY-RIPE
        tech-c:         DUMY-RIPE
        status:         ASSIGNED PA
        notify:         neteconomy.rete@telecomitalia.it
        mnt-by:         AS760-mnt
        changed:        2001-09-21T22:08:01Z
        source:         RIPE
        remarks:        remark
        
        ERROR: Authorisation for inetnum 80.16.151.184 - 80.16.151.191 failed: must by authenticated by one of: AS760-MNT
        INFO: Address range 80.16.151.184 - 80.016.151.191 was reformatted as 80.16.151.184 - 80.16.151.191

        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """)

    def test_parse_invalid_object_syntax(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks
        mock_dh.execute_query = lambda query: []

        rpsl_text = textwrap.dedent("""
        person:         Placeholder Person Object
        nic-hdl:        DUMy-RIPE
        changed:        2009-07-24T17:00:00Z
        source:         RIPE
        """)

        handler = UpdateRequestHandler(rpsl_text)
        assert handler.status() == 'FAILED'

        assert flatten_mock_calls(mock_dq) == []
        assert mock_dh.mock_calls[0][0] == 'commit'

        assert handler.user_report() == textwrap.dedent("""
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
        Request FAILED: [person] DUMY-RIPE
        
        person:         Placeholder Person Object
        nic-hdl:        DUMy-RIPE
        changed:        2009-07-24T17:00:00Z
        source:         RIPE
        
        ERROR: Mandatory attribute 'address' on object person is missing
        ERROR: Mandatory attribute 'phone' on object person is missing
        ERROR: Mandatory attribute 'e-mail' on object person is missing
        ERROR: Mandatory attribute 'mnt-by' on object person is missing
        
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """)
