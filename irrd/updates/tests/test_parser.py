import itertools
from unittest.mock import Mock

import pytest
from passlib.handlers.md5_crypt import md5_crypt
from pytest import raises

from irrd.conf import PASSWORD_HASH_DUMMY_VALUE
from irrd.utils.text import splitline_unicodesafe
from irrd.utils.rpsl_samples import SAMPLE_INETNUM, SAMPLE_AS_SET, SAMPLE_PERSON, SAMPLE_MNTNER
from irrd.utils.test_utils import flatten_mock_calls
from ..parser import parse_update_requests
from ..parser_state import UpdateRequestType, UpdateRequestStatus
from ..validators import ReferenceValidator, AuthValidator


@pytest.fixture()
def prepare_mocks(monkeypatch):
    mock_dh = Mock()
    mock_dq = Mock()
    monkeypatch.setattr('irrd.updates.parser.RPSLDatabaseQuery', lambda: mock_dq)
    monkeypatch.setattr('irrd.updates.validators.RPSLDatabaseQuery', lambda: mock_dq)
    yield mock_dq, mock_dh


class TestSingleUpdateRequestHandling:
    # NOTE: the scope of this test includes UpdateRequest, ReferenceValidator and AuthValidator

    def test_parse_valid(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_results = iter([
            [{'object_text': SAMPLE_INETNUM}],
            [{'object_text': SAMPLE_AS_SET}],
        ])
        mock_dh.execute_query = lambda query: next(query_results)

        auth_validator = AuthValidator(mock_dh)
        result_inetnum, result_as_set, result_unknown, result_invalid = parse_update_requests(
            self._request_text(), mock_dh, auth_validator, None)

        assert result_inetnum.status == UpdateRequestStatus.PROCESSING, result_inetnum.error_messages
        assert result_inetnum.is_valid()
        assert result_inetnum.rpsl_text_submitted.startswith('inetnum:')
        assert result_inetnum.rpsl_obj_new.rpsl_object_class == 'inetnum'
        assert result_inetnum.request_type == UpdateRequestType.DELETE
        assert len(result_inetnum.info_messages) == 1
        assert 'reformatted as' in result_inetnum.info_messages[0]
        assert not result_inetnum.error_messages

        assert result_as_set.status == UpdateRequestStatus.PROCESSING, result_inetnum.error_messages
        assert result_as_set.is_valid()
        assert result_as_set.rpsl_text_submitted.startswith('as-set:')
        assert result_as_set.rpsl_obj_new.rpsl_object_class == 'as-set'
        assert result_as_set.request_type == UpdateRequestType.MODIFY
        assert not result_as_set.info_messages
        assert not result_as_set.error_messages

        assert result_unknown.status == UpdateRequestStatus.ERROR_UNKNOWN_CLASS
        assert not result_unknown.is_valid()
        assert result_unknown.rpsl_text_submitted.startswith('unknown-object:')
        assert not result_unknown.rpsl_obj_new
        assert not result_unknown.request_type
        assert not result_unknown.info_messages
        assert len(result_unknown.error_messages) == 1
        assert 'unknown object class' in result_unknown.error_messages[0]

        assert result_invalid.status == UpdateRequestStatus.ERROR_PARSING
        assert not result_invalid.is_valid()
        assert result_invalid.rpsl_text_submitted.startswith('aut-num:')
        assert result_invalid.rpsl_obj_new.rpsl_object_class == 'aut-num'
        assert not result_invalid.info_messages
        assert len(result_invalid.error_messages) == 6
        assert 'Mandatory attribute' in result_invalid.error_messages[0]

        assert auth_validator.passwords == ['pw1', 'pw2', 'pw3']
        assert auth_validator.overrides == ['override-pw']

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

    def test_save_nonexistent_object(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks
        mock_dh.execute_query = lambda query: []

        result_inetnum = parse_update_requests(self._request_text(), mock_dh, AuthValidator(mock_dh), None)[0]

        assert result_inetnum.status == UpdateRequestStatus.ERROR_PARSING
        assert not result_inetnum.is_valid()
        assert result_inetnum.rpsl_text_submitted.startswith('inetnum:')
        assert result_inetnum.request_type == UpdateRequestType.DELETE
        assert len(result_inetnum.error_messages) == 1
        assert 'Can not delete object: no object found for this key in this database' in result_inetnum.error_messages[0]

    def test_check_references_valid(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

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

    def test_check_references_invalid_referred_objects_dont_exist(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

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
            'Object DUMY-RIPE referenced in field admin-c not found in database RIPE - must reference one of role, person.',
            'Object DUMY-RIPE referenced in field tech-c not found in database RIPE - must reference one of role, person.',
            'Object INTERB-MNT referenced in field mnt-by not found in database RIPE - must reference mntner.'
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

    def test_check_references_valid_preload_references(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

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

    def test_check_references_invalid_deleting_object_with_refs_in_db(self, prepare_mocks):
        # Delete an object which is still referred by other objects in the DB.
        mock_dq, mock_dh = prepare_mocks

        validator = ReferenceValidator(mock_dh)
        query_results = iter([
            [{'object_text': SAMPLE_PERSON}],
            [{'object_text': SAMPLE_INETNUM, 'object_class': 'inetnum',
              'rpsl_pk': '80.16.151.184 - 80.16.151.191', 'source': 'RIPE'}],
        ])
        mock_dh.execute_query = lambda query: next(query_results)

        result = parse_update_requests(SAMPLE_PERSON + "delete: delete",
                                       mock_dh, AuthValidator(mock_dh), validator)[0]
        result._check_references()
        assert not result.is_valid()
        assert result.error_messages == [
            'Object DUMY-RIPE to be deleted, but still referenced by inetnum 80.16.151.184 - 80.16.151.191',
        ]

        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['person'],), {}],
            ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}],
            ['lookup_attrs_in', ({'tech-c', 'zone-c', 'admin-c'}, ['DUMY-RIPE']), {}],
        ]

    def test_check_references_invalid_deleting_object_with_refs_in_update_message(self, prepare_mocks):
        # Delete an object that is referred by a new object in the same update.
        mock_dq, mock_dh = prepare_mocks

        validator = ReferenceValidator(mock_dh)
        query_results = iter([
            [{'object_text': SAMPLE_PERSON}],
            [{'object_text': SAMPLE_INETNUM}],
            [],
            [{'object_text': SAMPLE_PERSON, 'object_class': 'person',
              'rpsl_pk': 'DUMY-RIPE', 'source': 'RIPE'}],
        ])
        mock_dh.execute_query = lambda query: next(query_results)

        results = parse_update_requests(SAMPLE_PERSON + "delete: delete" + "\n\n" + SAMPLE_INETNUM,
                                        mock_dh, AuthValidator(mock_dh), validator)
        validator.preload(results)
        result_inetnum = results[1]
        result_inetnum._check_references()
        assert not result_inetnum.is_valid()
        assert result_inetnum.error_messages == [
            'Object DUMY-RIPE referenced in field admin-c not found in database RIPE - must reference one of role, person.',
            'Object DUMY-RIPE referenced in field tech-c not found in database RIPE - must reference one of role, person.',
            'Object INTERB-MNT referenced in field mnt-by not found in database RIPE - must reference mntner.',
        ]

        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['person'],), {}],
            ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pk', ('INTERB-MNT',), {}],
        ]

    def test_check_references_valid_deleting_object_referencing_to_be_deleted_object(self, prepare_mocks):
        # Delete an object that refers another object in the DB,
        # but the object referred to is also being deleted,
        # therefore the deletion is valid.
        mock_dq, mock_dh = prepare_mocks

        validator = ReferenceValidator(mock_dh)
        mock_dh.execute_query = lambda query: []
        result_inetnum = parse_update_requests(SAMPLE_INETNUM + "delete: delete",
                                               mock_dh, AuthValidator(mock_dh), validator)
        validator.preload(result_inetnum)
        mock_dq.reset_mock()

        query_results = iter([
            [{'object_text': SAMPLE_PERSON}],
            [{'object_text': SAMPLE_INETNUM, 'object_class': 'inetnum',
              'rpsl_pk': '80.16.151.184 - 80.16.151.191', 'source': 'RIPE'}],
        ])
        mock_dh.execute_query = lambda query: next(query_results)

        result = parse_update_requests(SAMPLE_PERSON + "delete: delete" + "\n",
                                       mock_dh, AuthValidator(mock_dh), validator)[0]
        result._check_references()
        assert result.is_valid(), result.error_messages
        assert not result.error_messages
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['person'],), {}],
            ['rpsl_pk', ('DUMY-RIPE',), {}],
            ['sources', (['RIPE'],), {}],
            ['lookup_attrs_in', ({'tech-c', 'zone-c', 'admin-c'}, ['DUMY-RIPE']), {}],
        ]

    def test_check_auth_valid_update_mntner(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

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

        auth_validator = AuthValidator(mock_dh, 'PGPKEY-80F238C6')
        result_inetnum = parse_update_requests(SAMPLE_INETNUM, mock_dh, auth_validator, reference_validator)[0]
        assert result_inetnum._check_auth()
        assert not result_inetnum.error_messages

    def test_check_auth_valid_create_mntner_referencing_self(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: []

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_mntner = parse_update_requests(SAMPLE_MNTNER + 'password: md5-password',
                                              mock_dh, auth_validator, reference_validator)[0]
        auth_validator.pre_approve([result_mntner])

        assert result_mntner._check_auth()
        assert not result_mntner.error_messages
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pk', ('AS760-MNT',), {}],
        ]

    def test_check_auth_invalid_create_mntner_referencing_self_wrong_password(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: []

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_mntner = parse_update_requests(SAMPLE_MNTNER + 'password: invalid-password',
                                              mock_dh, auth_validator, reference_validator)[0]
        auth_validator.pre_approve([result_mntner])

        assert not result_mntner._check_auth()
        assert result_mntner.error_messages == ['Authorisation failed for the auth methods on this mntner object.']
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pk', ('AS760-MNT',), {}],
        ]

    def test_check_auth_invalid_create_mntner_referencing_self_with_dummy_passwords(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: []

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        # Submit the mntner with dummy password values as would be returned by queries.
        # This should not be allowed in new objects.
        data = SAMPLE_MNTNER.replace('LEuuhsBJNFV0Q', PASSWORD_HASH_DUMMY_VALUE)
        data = data.replace('$1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.', PASSWORD_HASH_DUMMY_VALUE)
        result_mntner = parse_update_requests(data + 'password: crypt-password',
                                              mock_dh, auth_validator, reference_validator)[0]
        auth_validator.pre_approve([result_mntner])

        assert not result_mntner._check_auth()
        assert result_mntner.error_messages == ['Authorisation failed for the auth methods on this mntner object.']
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pk', ('AS760-MNT',), {}],
        ]

    def test_check_auth_valid_update_mntner_submits_new_object_with_all_dummy_hash_values(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: [{'object_text': SAMPLE_MNTNER}]

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        # Submit the mntner with dummy password values as would be returned by queries,
        # but a password attribute that is valid for the current DB object.
        data = SAMPLE_MNTNER.replace('LEuuhsBJNFV0Q', PASSWORD_HASH_DUMMY_VALUE)
        data = data.replace('$1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.', PASSWORD_HASH_DUMMY_VALUE)
        result_mntner = parse_update_requests(data + 'password: crypt-password',
                                              mock_dh, auth_validator, reference_validator)[0]
        auth_validator.pre_approve([result_mntner])
        assert result_mntner._check_auth()
        assert not result_mntner.error_messages
        auth_pgp, auth_hash = splitline_unicodesafe(result_mntner.rpsl_obj_new.parsed_data['auth'])
        assert auth_pgp == 'PGPKey-80F238C6'
        assert auth_hash.startswith('MD5-PW ')
        assert md5_crypt.verify('crypt-password', auth_hash[7:])
        assert auth_hash in result_mntner.rpsl_obj_new.render_rpsl_text()

        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pk', ('AS760-MNT',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pks', (['AS760-MNT', 'ACONET-LIR-MNT', 'ACONET2-LIR-MNT'],), {}],
        ]

    def test_check_auth_invalid_update_mntner_submits_new_object_with_mixed_dummy_hash_real_hash(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: [{'object_text': SAMPLE_MNTNER}]

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        # Submit the mntner with dummy password values as would be returned by queries,
        # but a password attribute that is valid for the current DB object.
        data = SAMPLE_MNTNER.replace('LEuuhsBJNFV0Q', PASSWORD_HASH_DUMMY_VALUE)
        result_mntner = parse_update_requests(data + 'password: md5-password',
                                              mock_dh, auth_validator, reference_validator)[0]
        auth_validator.pre_approve([result_mntner])
        result_mntner._check_auth()
        assert not result_mntner.is_valid()
        assert result_mntner.error_messages == [
            'Either all password auth hashes in a submitted mntner must be dummy objects, or none.',
        ]

    def test_check_auth_invalid_update_mntner_submits_new_object_with_dummy_hash_multiple_passwords(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: [{'object_text': SAMPLE_MNTNER}]

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        # Submit the mntner with dummy password values as would be returned by queries,
        # but multiple password attributes, which means we wouldn't know which password to set.
        data = SAMPLE_MNTNER.replace('LEuuhsBJNFV0Q', PASSWORD_HASH_DUMMY_VALUE)
        data = data.replace('$1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.', PASSWORD_HASH_DUMMY_VALUE)
        result_mntner = parse_update_requests(data + 'password: md5-password\npassword: other-password',
                                              mock_dh, auth_validator, reference_validator)[0]
        auth_validator.pre_approve([result_mntner])
        result_mntner._check_auth()
        assert not result_mntner.is_valid()
        assert result_mntner.error_messages == [
            'Object submitted with dummy hash values, but multiple passwords submitted. '
            'Either submit all full hashes, or a single password.'
        ]

    def test_check_auth_invalid_update_mntner_wrong_password_current_db_object(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        # Make the crypt password invalid in the version from the mock database
        mock_dh.execute_query = lambda query: [{'object_text': SAMPLE_MNTNER.replace('CRYPT-PW', 'FAILED')}]

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        # This password is valid for the new object, but invalid for the current version in the DB
        result_mntner = parse_update_requests(SAMPLE_MNTNER + 'password: crypt-password',
                                              mock_dh, auth_validator, reference_validator)[0]
        auth_validator.pre_approve([result_mntner])
        assert not result_mntner._check_auth()
        assert result_mntner.error_messages == [
            'Authorisation for mntner AS760-MNT failed: must by authenticated by one of: AS760-MNT, '
            'ACONET-LIR-MNT, ACONET2-LIR-MNT'
        ]
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}], ['object_classes', (['mntner'],), {}], ['rpsl_pk', ('AS760-MNT',), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['mntner'],), {}],
            ['rpsl_pks', (['AS760-MNT', 'ACONET-LIR-MNT', 'ACONET2-LIR-MNT'],), {}],
            ['sources', (['RIPE'],), {}], ['object_classes', (['mntner'],), {}],
            ['rpsl_pks', (['AS760-MNT', 'ACONET-LIR-MNT', 'ACONET2-LIR-MNT'],), {}]
        ]

    def test_check_auth_invalid_create_with_incorrect_password_referenced_mntner(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_results = iter([[{'object_text': SAMPLE_INETNUM}], [{'object_text': SAMPLE_MNTNER}], []])
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_inetnum = parse_update_requests(SAMPLE_INETNUM + 'password: wrong-pw',
                                               mock_dh, auth_validator, reference_validator)[0]
        assert not result_inetnum._check_auth()
        assert 'Authorisation for inetnum 80.16.151.184 - 80.16.151.191 failed' in result_inetnum.error_messages[0]
        assert 'one of: INTERB-MNT' in result_inetnum.error_messages[0]
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}], ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}], ['rpsl_pks', (['INTERB-MNT'],), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}], ['rpsl_pks', (['INTERB-MNT'],), {}]
        ]

    def test_check_auth_invalid_update_with_incorrect_password_referenced_mntner(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_results = iter([
            [{'object_text': SAMPLE_INETNUM.replace('INTERB-MNT', 'FAIL-MNT')}],
            [{'object_text': SAMPLE_MNTNER}],
            []
        ])
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_inetnum = parse_update_requests(SAMPLE_INETNUM + 'password: md5-password',
                                               mock_dh, auth_validator, reference_validator)[0]
        assert not result_inetnum._check_auth()
        assert 'Authorisation for inetnum 80.16.151.184 - 80.16.151.191 failed' in result_inetnum.error_messages[0]
        assert 'one of: FAIL-MNT' in result_inetnum.error_messages[0]
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['inetnum'],), {}],
            ['rpsl_pk', ('80.16.151.184 - 80.16.151.191',), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pks', (['INTERB-MNT'],), {}],
            ['sources', (['RIPE'],), {}],
            ['object_classes', (['mntner'],), {}],
            ['rpsl_pks', (['FAIL-MNT'],), {}],
        ]

    def test_user_report(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

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

    def _request_text(self):
        unknown_class = 'unknown-object: foo\n'
        invalid_object = 'aut-num: pw1\n'

        request_text = 'password: pw1\n' + SAMPLE_INETNUM + 'delete: delete\n\r\n\r\n\r\n'
        request_text += SAMPLE_AS_SET + 'password: pw2\n\n'
        request_text += 'password: pw3\n' + unknown_class + '\r\n'
        request_text += invalid_object + '\noverride: override-pw'
        return request_text
