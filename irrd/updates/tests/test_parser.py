import itertools
from unittest.mock import Mock

from pytest import raises

from irrd.utils.rpsl_samples import SAMPLE_INETNUM, SAMPLE_AS_SET, SAMPLE_PERSON, SAMPLE_MNTNER
from irrd.utils.test_utils import flatten_mock_calls
from ..parser import parse_update_requests, UpdateRequestType, UpdateRequestStatus
from ..validators import ReferenceValidator, AuthValidator


class TestSingleUpdateRequestHandling:
    # NOTE: the scope of this test includes UpdateRequest, ReferenceValidator and Authvalidator

    def test_parse_valid(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)

        query_results = iter([
            [{'object_text': SAMPLE_INETNUM}],
            [{'object_text': SAMPLE_AS_SET}],
        ])
        mock_dh.execute_query = lambda query: next(query_results)

        result_inetnum, result_as_set, result_unknown, result_invalid = parse_update_requests(
            self._request_text(), mock_dh, AuthValidator(mock_dh), None)

        assert result_inetnum.status == UpdateRequestStatus.PROCESSING, result_inetnum.error_messages
        assert result_inetnum.is_valid()
        assert result_inetnum.rpsl_text.startswith('inetnum:')
        assert result_inetnum.rpsl_obj_new.rpsl_object_class == 'inetnum'
        assert result_inetnum.passwords == ['pw1', 'pw2', 'pw3']
        assert result_inetnum.overrides == ['override-pw']
        assert result_inetnum.request_type == UpdateRequestType.DELETE
        assert len(result_inetnum.info_messages) == 1
        assert 'reformatted as' in result_inetnum.info_messages[0]
        assert not result_inetnum.error_messages

        assert result_as_set.status == UpdateRequestStatus.PROCESSING, result_inetnum.error_messages
        assert result_as_set.is_valid()
        assert result_as_set.rpsl_text.startswith('as-set:')
        assert result_as_set.rpsl_obj_new.rpsl_object_class == 'as-set'
        assert result_as_set.passwords == ['pw1', 'pw2', 'pw3']
        assert result_inetnum.overrides == ['override-pw']
        assert result_as_set.request_type == UpdateRequestType.MODIFY
        assert not result_as_set.info_messages
        assert not result_as_set.error_messages

        assert result_unknown.status == UpdateRequestStatus.ERROR_UNKNOWN_CLASS
        assert not result_unknown.is_valid()
        assert result_unknown.rpsl_text.startswith('unknown-object:')
        assert not result_unknown.rpsl_obj_new
        assert result_unknown.passwords == ['pw1', 'pw2', 'pw3']
        assert result_unknown.overrides == ['override-pw']
        assert result_unknown.request_type == UpdateRequestType.NO_OP
        assert not result_unknown.info_messages
        assert len(result_unknown.error_messages) == 1
        assert 'unknown object class' in result_unknown.error_messages[0]

        assert result_invalid.status == UpdateRequestStatus.ERROR_PARSING
        assert not result_invalid.is_valid()
        assert result_invalid.rpsl_text.startswith('aut-num:')
        assert result_invalid.rpsl_obj_new.rpsl_object_class == 'aut-num'
        assert result_invalid.passwords == ['pw1', 'pw2', 'pw3']
        assert result_invalid.overrides == ['override-pw']
        assert result_invalid.request_type == UpdateRequestType.NO_OP
        assert not result_invalid.info_messages
        assert len(result_invalid.error_messages) == 6
        assert 'Mandatory attribute' in result_invalid.error_messages[0]

        mock_dh.reset_mock()
        result_inetnum.save(mock_dh)
        result_as_set.save(mock_dh)

        with raises(ValueError):
            result_unknown.save(mock_dh)
        with raises(ValueError):
            result_invalid.save(mock_dh)
        assert flatten_mock_calls(mock_dh) == [
            ['delete_rpsl_object', (result_inetnum.rpsl_obj_current,), {}],
            ['upsert_rpsl_object', (result_as_set.rpsl_obj_new,), {}],
        ]

    def test_delete_nonexistent_object(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)
        mock_dh.execute_query = lambda query: []

        result_inetnum = parse_update_requests(self._request_text(), mock_dh, AuthValidator(mock_dh), None)[0]

        assert result_inetnum.status == UpdateRequestStatus.ERROR_PARSING
        assert not result_inetnum.is_valid()
        assert result_inetnum.rpsl_text.startswith('inetnum:')
        assert result_inetnum.request_type == UpdateRequestType.DELETE
        assert len(result_inetnum.error_messages) == 1
        assert 'Can not delete object: no object found for this key in this database' in result_inetnum.error_messages[0]

    def test_check_references_valid(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)

        query_result_existing_obj = {
            'object_text': SAMPLE_INETNUM,
        }
        query_result_dumy_person = {
            'rpsl_pk': 'DUMY-RIPE',
            'object_class': 'person',
        }
        query_result_interdb_mntner = {
            'rpsl_pk': 'INTERDB-MNT',
            'object_class': 'mntner',
            'parsed_data': {'mntner': 'INTERDB-MNT'},
        }
        query_results = iter([query_result_existing_obj, query_result_dumy_person, query_result_interdb_mntner])
        mock_dh.execute_query = lambda query: [next(query_results)]

        validator = ReferenceValidator(mock_dh)

        result_inetnum = parse_update_requests(SAMPLE_INETNUM, mock_dh, AuthValidator(mock_dh), validator)[0]
        assert result_inetnum._check_references()
        assert result_inetnum.is_valid()
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['role', 'person'],), {}],
            ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pk', ('INTERB-MNT',), {}],
        ]

    def test_check_references_invalid(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)

        query_result_existing_obj = {
            'object_text': SAMPLE_INETNUM,
        }
        query_results = iter([[query_result_existing_obj], [], [], []])
        mock_dh.execute_query = lambda query: next(query_results)
        validator = ReferenceValidator(mock_dh)

        result_inetnum = parse_update_requests(SAMPLE_INETNUM, mock_dh, AuthValidator(mock_dh), validator)[0]
        assert not result_inetnum._check_references()
        assert not result_inetnum.is_valid()
        assert result_inetnum.error_messages == [
            'Object DUMY-RIPE referenced in field admin-c not found in database RIPE - must reference one of role, person object',
            'Object DUMY-RIPE referenced in field tech-c not found in database RIPE - must reference one of role, person object',
            'Object INTERB-MNT referenced in field mnt-by not found in database RIPE - must reference mntner object'
        ]
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['role', 'person'],), {}],
            ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['role', 'person'],), {}],
            ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pk', ('INTERB-MNT',), {}],
        ]

    def test_check_references_preload(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)

        mock_dh.execute_query = lambda query: next(iter([[{'object_text': SAMPLE_PERSON}], [{'object_text': SAMPLE_MNTNER}]]))
        validator = ReferenceValidator(mock_dh)

        preload = parse_update_requests(SAMPLE_PERSON + '\n' + SAMPLE_MNTNER.replace('AS760-MNt', 'INTERB-mnt'),
                                        mock_dh, AuthValidator(mock_dh), validator)
        mock_dq.reset_mock()
        validator.preload(preload)

        result_inetnum = parse_update_requests(SAMPLE_INETNUM, mock_dh, AuthValidator(mock_dh), validator)[0]
        assert result_inetnum._check_references()
        assert result_inetnum.is_valid()
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}]
        ]

    def test_check_references_deletion(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)

        validator = ReferenceValidator(mock_dh)
        mock_dh.execute_query = lambda query: [{'object_text': SAMPLE_INETNUM}]

        result_inetnum = parse_update_requests(SAMPLE_INETNUM + "delete: delete",
                                               mock_dh, AuthValidator(mock_dh), validator)[0]
        assert result_inetnum._check_references()
        assert result_inetnum.is_valid()
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}]
        ]

    def test_user_report(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)

        query_results = iter([
            [{'object_text': SAMPLE_INETNUM}],
            [],
        ])
        mock_dh.execute_query = lambda query: next(query_results)

        result_inetnum, result_as_set, result_unknown, result_invalid = parse_update_requests(
            self._request_text(), mock_dh, AuthValidator(mock_dh), None)
        report_inetnum = result_inetnum.user_report()
        report_as_set = result_as_set.user_report()
        report_unknown = result_unknown.user_report()
        report_invalid = result_invalid.user_report()

        assert 'Delete succeeded' in report_inetnum
        assert 'remarks: ' in report_inetnum  # full RPSL object should be included
        assert 'INFO: Address range 80' in report_inetnum

        assert report_as_set == 'Create succeeded: [as-set] AS-RESTENA\n'

        assert 'FAILED' in report_unknown
        assert 'ERROR: unknown object class' in report_unknown

        assert 'FAILED' in report_invalid
        assert 'aut-num: pw1'  # full RPSL object should be included
        assert 'ERROR: Mandatory attribute' in report_invalid
        assert 'ERROR: Invalid AS number PW1' in report_invalid

    def test_check_auth_success(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)

        query_result1 = {'object_text': SAMPLE_INETNUM}
        query_result2 = {'object_text': SAMPLE_MNTNER.replace('AS760-MNt', 'INTERB-mnt')}
        query_results = itertools.cycle([[query_result1], [query_result2]])
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_inetnum = parse_update_requests(SAMPLE_INETNUM + 'password: crypt-password',
                                               mock_dh, auth_validator, reference_validator)[0]
        assert result_inetnum._check_auth()
        assert not result_inetnum.error_messages
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pks', (['INTERB-MNT'],), {}]
        ]

        auth_validator = AuthValidator(mock_dh)
        result_inetnum = parse_update_requests(SAMPLE_INETNUM + 'password: md5-password',
                                               mock_dh, auth_validator, reference_validator)[0]
        assert result_inetnum._check_auth()
        assert not result_inetnum.error_messages

        auth_validator = AuthValidator(mock_dh)
        result_inetnum = parse_update_requests(SAMPLE_INETNUM, mock_dh,
                                               auth_validator, reference_validator, 'PGPKEY-80F238C6')[0]
        assert result_inetnum._check_auth()
        assert not result_inetnum.error_messages

    def test_check_auth_self_reference(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)

        mock_dh.execute_query = lambda query: [{'object_text': SAMPLE_MNTNER}]

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_mntner = parse_update_requests(SAMPLE_MNTNER + 'password: crypt-password',
                                               mock_dh, auth_validator, reference_validator)[0]
        auth_validator.pre_approve([result_mntner])

        assert result_mntner._check_auth()
        assert not result_mntner.error_messages
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pk', ('AS760-MNT',), {}]
        ]

        auth_validator = AuthValidator(mock_dh)
        result_mntner = parse_update_requests(SAMPLE_MNTNER + 'password: wrong-pw',
                                               mock_dh, auth_validator, reference_validator)[0]
        auth_validator.pre_approve([result_mntner])
        assert not result_mntner._check_auth()

    def test_check_auth_fail(self, monkeypatch):
        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
        monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)

        query_results = iter([[{'object_text': SAMPLE_INETNUM}], [{'object_text': SAMPLE_MNTNER}]])
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_inetnum = parse_update_requests(SAMPLE_INETNUM + 'password: wrong-pw',
                                               mock_dh, auth_validator, reference_validator)[0]
        assert not result_inetnum._check_auth()
        assert 'Authorisation for inetnum 80.16.151.184 - 80.16.151.191 failed' in result_inetnum.error_messages[0]
        assert 'one of: INTERB-MNT' in result_inetnum.error_messages[0]
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pks', (['INTERB-MNT'],), {}]
        ]

    def _request_text(self):
        unknown_class = 'unknown-object: foo\n'
        invalid_object = 'aut-num: pw1\n'

        request_text = 'password: pw1\n' + SAMPLE_INETNUM + 'delete: delete\n\r\n\r\n\r\n'
        request_text += SAMPLE_AS_SET + 'password: pw2\n\n'
        request_text += 'password: pw3\n' + unknown_class + '\r\n'
        request_text += invalid_object + '\noverride: override-pw'
        return request_text
