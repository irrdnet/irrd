from unittest.mock import Mock

from pytest import raises

from irrd.utils.rpsl_samples import SAMPLE_INETNUM, SAMPLE_AS_SET, SAMPLE_PERSON, SAMPLE_MNTNER
from irrd.utils.test_utils import flatten_mock_calls
from ..parser import parse_update_request, UpdateRequestStatus, UpdateRequestType, ReferenceChecker


class TestUpdateRequest:

    def test_parse_valid(self):
        result_inetnum, result_as_set, result_unknown, result_invalid = parse_update_request(self._request_text())

        assert result_inetnum.status == UpdateRequestStatus.PROCESSING
        assert result_inetnum.is_valid()
        assert result_inetnum.rpsl_text.startswith('inetnum:')
        assert result_inetnum.rpsl_obj.rpsl_object_class == 'inetnum'
        assert result_inetnum.passwords == ['pw1', 'pw2', 'pw3']
        assert result_inetnum.overrides == ['override-pw']
        assert result_inetnum.request_type == UpdateRequestType.DELETE
        assert len(result_inetnum.info_messages) == 1
        assert 'reformatted as' in result_inetnum.info_messages[0]
        assert not result_inetnum.error_messages

        assert result_as_set.status == UpdateRequestStatus.PROCESSING
        assert result_as_set.is_valid()
        assert result_as_set.rpsl_text.startswith('as-set:')
        assert result_as_set.rpsl_obj.rpsl_object_class == 'as-set'
        assert result_as_set.passwords == ['pw1', 'pw2', 'pw3']
        assert result_inetnum.overrides == ['override-pw']
        assert result_as_set.request_type == UpdateRequestType.NO_OP
        assert not result_as_set.info_messages
        assert not result_as_set.error_messages

        assert result_unknown.status == UpdateRequestStatus.ERROR_UNKNOWN_CLASS
        assert not result_unknown.is_valid()
        assert result_unknown.rpsl_text.startswith('unknown-object:')
        assert not result_unknown.rpsl_obj
        assert result_unknown.passwords == ['pw1', 'pw2', 'pw3']
        assert result_unknown.overrides == ['override-pw']
        assert result_unknown.request_type == UpdateRequestType.NO_OP
        assert not result_unknown.info_messages
        assert len(result_unknown.error_messages) == 1
        assert 'unknown object class' in result_unknown.error_messages[0]

        assert result_invalid.status == UpdateRequestStatus.ERROR_PARSING
        assert not result_invalid.is_valid()
        assert result_invalid.rpsl_text.startswith('aut-num:')
        assert result_invalid.rpsl_obj.rpsl_object_class == 'aut-num'
        assert result_invalid.passwords == ['pw1', 'pw2', 'pw3']
        assert result_invalid.overrides == ['override-pw']
        assert result_invalid.request_type == UpdateRequestType.NO_OP
        assert not result_invalid.info_messages
        assert len(result_invalid.error_messages) == 6
        assert 'Mandatory attribute' in result_invalid.error_messages[0]

        mock_dh = Mock()
        result_inetnum.save(mock_dh)
        result_as_set.save(mock_dh)

        with raises(ValueError):
            result_unknown.save(mock_dh)
        with raises(ValueError):
            result_invalid.save(mock_dh)

        assert flatten_mock_calls(mock_dh) == [
            ['delete_rpsl_object', (result_inetnum.rpsl_obj,), {}],
            ['upsert_rpsl_object', (result_as_set.rpsl_obj,), {}],
        ]

    def test_check_references_valid(self, monkeypatch):
        result_inetnum = parse_update_request(SAMPLE_INETNUM)[0]

        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)

        query_result_dumy_person = {
            'rpsl_pk': 'DUMY-RIPE',
            'object_class': 'person',
        }
        query_result_interdb_mntner = {
            'rpsl_pk': 'INTERDB-MNT',
            'object_class': 'mntner',
            'parsed_data': {'mntner': 'INTERDB-MNT'},
        }
        mock_dh.execute_query = lambda query: [next(iter([query_result_dumy_person, query_result_interdb_mntner]))]

        checker = ReferenceChecker(mock_dh)
        assert result_inetnum.check_references(checker)
        assert result_inetnum.is_valid()
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['role', 'person'],), {}],
            ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pk', ('INTERB-MNT',), {}],
        ]

    def test_check_references_invalid(self, monkeypatch):
        result_inetnum = parse_update_request(SAMPLE_INETNUM)[0]

        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)

        query_result_interdb_mntner = {
            'rpsl_pk': 'INTERDB-MNT',
            'object_class': 'mntner',
            'parsed_data': {'mntner': 'INTERDB-MNT'},
        }
        mock_dh.execute_query = lambda query: next(iter([[], [], [query_result_interdb_mntner]]))

        checker = ReferenceChecker(mock_dh)
        assert not result_inetnum.check_references(checker)
        assert not result_inetnum.is_valid()
        assert result_inetnum.error_messages == [
            'Object DUMY-RIPE referenced in field admin-c not found in database RIPE - must reference one of role, person object',
            'Object DUMY-RIPE referenced in field tech-c not found in database RIPE - must reference one of role, person object',
            'Object INTERB-MNT referenced in field mnt-by not found in database RIPE - must reference mntner object'
        ]
        assert flatten_mock_calls(mock_dq) == [
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
        result_inetnum = parse_update_request(SAMPLE_INETNUM)[0]

        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
        mock_dh.execute_query = lambda query: []

        preload = parse_update_request(SAMPLE_PERSON + '\n' + SAMPLE_MNTNER.replace('AS760-MNt', 'INTERB-mnt'))

        checker = ReferenceChecker(mock_dh)
        checker.preload(preload)

        assert result_inetnum.check_references(checker)
        assert result_inetnum.is_valid()
        assert flatten_mock_calls(mock_dq) == []

    def test_check_references_deletion(self, monkeypatch):
        result_inetnum = parse_update_request(SAMPLE_INETNUM + "delete: delete")[0]

        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)

        checker = ReferenceChecker(mock_dh)
        assert result_inetnum.check_references(checker)
        assert result_inetnum.is_valid()
        assert flatten_mock_calls(mock_dq) == []

    def test_user_report(self):
        result_inetnum, result_as_set, result_unknown, result_invalid = parse_update_request(self._request_text())

        report_inetnum = result_inetnum.user_report()
        report_as_set = result_as_set.user_report()
        report_unknown = result_unknown.user_report()
        report_invalid = result_invalid.user_report()

        assert 'Delete succeeded' in report_inetnum
        assert 'remarks: ' in report_inetnum  # full RPSL object should be included
        assert 'INFO: Address range 80' in report_inetnum

        assert report_as_set == 'No Operation succeeded: [as-set] AS-RESTENA\n'

        assert 'FAILED' in report_unknown
        assert 'ERROR: unknown object class' in report_unknown

        assert 'FAILED' in report_invalid
        assert 'aut-num: pw1'  # full RPSL object should be included
        assert 'ERROR: Mandatory attribute' in report_invalid
        assert 'ERROR: Invalid AS number PW1' in report_invalid

    def _request_text(self):
        unknown_class = 'unknown-object: foo\n'
        invalid_object = 'aut-num: pw1\n'

        request_text = 'password: pw1\n' + SAMPLE_INETNUM + 'delete: delete\n\r\n\r\n\r\n'
        request_text += SAMPLE_AS_SET + 'password: pw2\n\n'
        request_text += 'password: pw3\n' + unknown_class + '\r\n'
        request_text += invalid_object + '\noverride: override-pw'
        return request_text
