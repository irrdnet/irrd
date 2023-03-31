# flake8: noqa: W293
import itertools
import textwrap
from unittest.mock import Mock

import passlib.hash
import pytest
from passlib.hash import bcrypt
from pytest import raises

from irrd.conf import PASSWORD_HASH_DUMMY_VALUE
from irrd.rpki.status import RPKIStatus
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.models import JournalEntryOrigin
from irrd.updates.suspension import reactivate_for_mntner, suspend_for_mntner
from irrd.utils.rpsl_samples import (
    SAMPLE_AS_SET,
    SAMPLE_INETNUM,
    SAMPLE_MNTNER,
    SAMPLE_PERSON,
    SAMPLE_ROUTE,
    SAMPLE_ROUTE6,
)
from irrd.utils.test_utils import flatten_mock_calls
from irrd.utils.text import splitline_unicodesafe

from ..parser import parse_change_requests
from ..parser_state import SuspensionRequestType, UpdateRequestStatus, UpdateRequestType
from ..validators import (
    AuthValidator,
    ReferenceValidator,
    RulesValidator,
    ValidatorResult,
)


@pytest.fixture()
def prepare_mocks(monkeypatch, config_override):
    monkeypatch.setenv("IRRD_SOURCES_TEST_AUTHORITATIVE", "1")
    monkeypatch.setenv("IRRD_AUTH_OVERRIDE_PASSWORD", "$1$J6KycItM$MbPaBU6iFSGFV299Rk7Di0")
    mock_dh = Mock()
    mock_dq = Mock()
    monkeypatch.setattr("irrd.updates.parser.RPSLDatabaseQuery", lambda: mock_dq)
    monkeypatch.setattr("irrd.updates.validators.RPSLDatabaseQuery", lambda: mock_dq)

    mock_scopefilter = Mock(spec=ScopeFilterValidator)
    monkeypatch.setattr("irrd.updates.parser.ScopeFilterValidator", lambda: mock_scopefilter)
    mock_scopefilter.validate_rpsl_object = lambda obj: (ScopeFilterStatus.in_scope, "")
    mock_rules_validator = Mock(spec=RulesValidator)
    monkeypatch.setattr("irrd.updates.parser.RulesValidator", lambda dh: mock_rules_validator)
    mock_rules_validator.validate.return_value = ValidatorResult()

    config_override(
        {
            "auth": {
                "password_hashers": {"crypt-pw": "enabled"},
            },
        }
    )
    yield mock_dq, mock_dh


class TestSingleChangeRequestHandling:
    # NOTE: the scope of this test includes ChangeRequest,
    # ReferenceValidator and AuthValidator. See #412.

    def test_parse(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_results = iter(
            [
                [{"object_text": SAMPLE_INETNUM}],
                [{"object_text": SAMPLE_AS_SET}],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_results)

        auth_validator = AuthValidator(mock_dh)
        result_inetnum, result_as_set, result_unknown, result_invalid = parse_change_requests(
            self._request_text(), mock_dh, auth_validator, None
        )

        assert result_inetnum.status == UpdateRequestStatus.PROCESSING, result_inetnum.error_messages
        assert result_inetnum.is_valid()
        assert result_inetnum.rpsl_text_submitted.startswith("inetnum:")
        assert result_inetnum.rpsl_obj_new.rpsl_object_class == "inetnum"
        assert result_inetnum.request_type == UpdateRequestType.DELETE
        assert len(result_inetnum.info_messages) == 1
        assert "reformatted as" in result_inetnum.info_messages[0]
        assert not result_inetnum.error_messages

        assert result_as_set.status == UpdateRequestStatus.PROCESSING, result_inetnum.error_messages
        assert result_as_set.is_valid()
        assert result_as_set.rpsl_text_submitted.startswith("as-set:")
        assert result_as_set.rpsl_obj_new.rpsl_object_class == "as-set"
        assert result_as_set.request_type == UpdateRequestType.MODIFY
        assert not result_as_set.info_messages
        assert not result_as_set.error_messages

        assert result_unknown.status == UpdateRequestStatus.ERROR_UNKNOWN_CLASS
        assert not result_unknown.is_valid()
        assert result_unknown.rpsl_text_submitted.startswith("unknown-object:")
        assert not result_unknown.rpsl_obj_new
        assert not result_unknown.request_type
        assert not result_unknown.info_messages
        assert len(result_unknown.error_messages) == 1
        assert "unknown object class" in result_unknown.error_messages[0]

        assert result_invalid.status == UpdateRequestStatus.ERROR_PARSING
        assert not result_invalid.is_valid()
        assert result_invalid.rpsl_text_submitted.startswith("aut-num:")
        assert result_invalid.rpsl_obj_new.rpsl_object_class == "aut-num"
        assert not result_invalid.info_messages
        assert len(result_invalid.error_messages) == 5
        assert "Mandatory attribute" in result_invalid.error_messages[0]

        assert auth_validator.passwords == ["pw1", "pw2", "pw3"]
        assert auth_validator.overrides == ["override-pw"]

        mock_dh.reset_mock()
        result_inetnum.save()
        result_as_set.save()

        with raises(ValueError):
            result_unknown.save()
        with raises(ValueError):
            result_invalid.save()
        assert flatten_mock_calls(mock_dh) == [
            [
                "delete_rpsl_object",
                (),
                {"rpsl_object": result_inetnum.rpsl_obj_current, "origin": JournalEntryOrigin.auth_change},
            ],
            ["upsert_rpsl_object", (result_as_set.rpsl_obj_new, JournalEntryOrigin.auth_change), {}],
        ]

    def test_non_authorative_source(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: []

        auth_validator = AuthValidator(mock_dh)
        result = parse_change_requests(SAMPLE_MNTNER.replace("TEST", "TEST2"), mock_dh, auth_validator, None)[
            0
        ]

        assert result.status == UpdateRequestStatus.ERROR_NON_AUTHORITIVE
        assert not result.is_valid()
        assert result.error_messages == ["This instance is not authoritative for source TEST2"]

    def test_validates_for_create(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: []

        auth_validator = Mock()
        invalid_auth_result = ValidatorResult()
        invalid_auth_result.error_messages.add("error catch")
        auth_validator.process_auth = lambda new, cur: invalid_auth_result

        invalid_create_text = SAMPLE_AS_SET.replace("AS65537:AS-SETTEST", "AS-SETTEST")
        result = parse_change_requests(invalid_create_text, mock_dh, auth_validator, None)[0]

        assert not result.validate()
        assert result.status == UpdateRequestStatus.ERROR_PARSING
        assert len(result.error_messages) == 1
        assert "as-set names must be hierarchical and the first" in result.error_messages[0]

        # Test again with an UPDATE (which then fails on auth to stop)
        mock_dh.execute_query = lambda query: [{"object_text": SAMPLE_AS_SET}]
        result = parse_change_requests(invalid_create_text, mock_dh, auth_validator, None)[0]
        assert not result.validate()
        assert result.error_messages == ["error catch"]

    def test_calls_rules_validator(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: []

        auth_validator = Mock()
        invalid_auth_result = ValidatorResult()
        invalid_auth_result.error_messages.add("error catch")
        auth_validator.process_auth = lambda new, cur: invalid_auth_result

        result = parse_change_requests(SAMPLE_AS_SET, mock_dh, auth_validator, None)[0]
        invalid_rules_result = ValidatorResult()
        invalid_rules_result.error_messages.add("rules fault")
        result.rules_validator.validate.return_value = invalid_rules_result

        assert not result.validate()
        assert result.status == UpdateRequestStatus.ERROR_RULES
        assert len(result.error_messages) == 1
        assert "rules fault" in result.error_messages[0]

    def test_save_nonexistent_object(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks
        mock_dh.execute_query = lambda query: []

        result_inetnum = parse_change_requests(self._request_text(), mock_dh, AuthValidator(mock_dh), None)[0]

        assert result_inetnum.status == UpdateRequestStatus.ERROR_PARSING
        assert not result_inetnum.is_valid()
        assert result_inetnum.rpsl_text_submitted.startswith("inetnum:")
        assert result_inetnum.request_type == UpdateRequestType.DELETE
        assert len(result_inetnum.error_messages) == 1
        assert (
            "Can not delete object: no object found for this key in this database"
            in result_inetnum.error_messages[0]
        )

    def test_check_references_valid(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_result_existing_obj = {
            "object_text": SAMPLE_INETNUM,
        }
        query_result_dumy_person = {
            "rpsl_pk": "PERSON-TEST",
            "object_class": "person",
        }
        query_result_interdb_mntner = {
            "rpsl_pk": "INTERDB-MNT",
            "object_class": "mntner",
            "parsed_data": {"mntner": "INTERDB-MNT"},
        }
        query_results = iter(
            [query_result_existing_obj, query_result_dumy_person, query_result_interdb_mntner]
        )
        mock_dh.execute_query = lambda query: [next(query_results)]

        validator = ReferenceValidator(mock_dh)

        result_inetnum = parse_change_requests(SAMPLE_INETNUM, mock_dh, AuthValidator(mock_dh), validator)[0]
        assert result_inetnum._check_references()
        assert result_inetnum.is_valid()
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["rpsl_pk", ("192.0.2.0 - 192.0.2.255",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["role", "person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
        ]

    def test_check_references_invalid_referred_objects_dont_exist(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_result_existing_obj = {
            "object_text": SAMPLE_INETNUM,
        }
        query_results = iter([[query_result_existing_obj], iter([]), iter([]), iter([])])
        mock_dh.execute_query = lambda query: next(query_results)
        validator = ReferenceValidator(mock_dh)

        result_inetnum = parse_change_requests(SAMPLE_INETNUM, mock_dh, AuthValidator(mock_dh), validator)[0]
        assert not result_inetnum._check_references()
        assert not result_inetnum.is_valid()
        assert not result_inetnum.notification_targets()
        assert result_inetnum.error_messages == [
            (
                "Object PERSON-TEST referenced in field admin-c not found in database TEST - must reference"
                " one of role, person."
            ),
            (
                "Object PERSON-TEST referenced in field tech-c not found in database TEST - must reference"
                " one of role, person."
            ),
            "Object TEST-MNT referenced in field mnt-by not found in database TEST - must reference mntner.",
        ]
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["rpsl_pk", ("192.0.2.0 - 192.0.2.255",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["role", "person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["role", "person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
        ]

    def test_check_references_valid_preload_references(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: next(
            iter([[{"object_text": SAMPLE_PERSON}], [{"object_text": SAMPLE_MNTNER}]])
        )
        validator = ReferenceValidator(mock_dh)

        preload = parse_change_requests(
            SAMPLE_PERSON + "\n" + SAMPLE_MNTNER, mock_dh, AuthValidator(mock_dh), validator
        )
        mock_dq.reset_mock()
        validator.preload(preload)

        result_inetnum = parse_change_requests(SAMPLE_INETNUM, mock_dh, AuthValidator(mock_dh), validator)[0]
        assert result_inetnum._check_references()
        assert result_inetnum.is_valid()
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["rpsl_pk", ("192.0.2.0 - 192.0.2.255",), {}],
        ]

    def test_check_references_valid_deleting_object_with_no_inbound_refs(self, prepare_mocks):
        # Delete an object which has no inbound references (fixes #228)
        mock_dq, mock_dh = prepare_mocks

        validator = ReferenceValidator(mock_dh)
        query_results = iter(
            [
                [
                    {
                        "object_text": SAMPLE_ROUTE,
                        "object_class": "route",
                        "rpsl_pk": "192.0.2.0/24",
                        "source": "TEST",
                    }
                ],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_results)

        result = parse_change_requests(
            SAMPLE_ROUTE + "delete: delete", mock_dh, AuthValidator(mock_dh), validator
        )[0]
        result._check_references()
        assert result.is_valid(), result.error_messages
        assert not result.error_messages

        # No lookup for references should be done as part of reference checks,
        # as this particular route object has no inbound references
        # (admin-c/tech-c is optional for route)
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["route"],), {}],
            ["rpsl_pk", ("192.0.2.0/24AS65537",), {}],
        ]

    def test_check_references_invalid_deleting_object_with_refs_in_db(self, prepare_mocks):
        # Delete an object which is still referred by other objects in the DB.
        mock_dq, mock_dh = prepare_mocks

        validator = ReferenceValidator(mock_dh)
        query_results = iter(
            [
                [{"object_text": SAMPLE_PERSON}],
                [
                    {
                        "object_text": SAMPLE_INETNUM,
                        "object_class": "inetnum",
                        "rpsl_pk": "192.0.2.0 - 192.0.2.255",
                        "source": "TEST",
                    }
                ],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_results)

        result = parse_change_requests(
            SAMPLE_PERSON + "delete: delete", mock_dh, AuthValidator(mock_dh), validator
        )[0]
        result._check_references()
        assert not result.is_valid()
        assert result.error_messages == [
            "Object PERSON-TEST to be deleted, but still referenced by inetnum 192.0.2.0 - 192.0.2.255",
        ]

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["lookup_attrs_in", ({"tech-c", "zone-c", "admin-c"}, ["PERSON-TEST"]), {}],
        ]

    def test_check_references_invalid_deleting_object_with_refs_in_update_message(self, prepare_mocks):
        # Delete an object that is referred by a new object in the same update.
        mock_dq, mock_dh = prepare_mocks

        validator = ReferenceValidator(mock_dh)
        query_results = iter(
            [
                [{"object_text": SAMPLE_PERSON}],
                [{"object_text": SAMPLE_INETNUM}],
                [],
                [
                    {
                        "object_text": SAMPLE_PERSON,
                        "object_class": "person",
                        "rpsl_pk": "PERSON-TEST",
                        "source": "TEST",
                    }
                ],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_results)

        results = parse_change_requests(
            SAMPLE_PERSON + "delete: delete" + "\n\n" + SAMPLE_INETNUM,
            mock_dh,
            AuthValidator(mock_dh),
            validator,
        )
        validator.preload(results)
        result_inetnum = results[1]
        result_inetnum._check_references()
        assert not result_inetnum.is_valid()
        assert result_inetnum.error_messages == [
            (
                "Object PERSON-TEST referenced in field admin-c not found in database TEST - must reference"
                " one of role, person."
            ),
            (
                "Object PERSON-TEST referenced in field tech-c not found in database TEST - must reference"
                " one of role, person."
            ),
            "Object TEST-MNT referenced in field mnt-by not found in database TEST - must reference mntner.",
        ]

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["rpsl_pk", ("192.0.2.0 - 192.0.2.255",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
        ]

    def test_check_references_valid_deleting_object_referencing_to_be_deleted_object(self, prepare_mocks):
        # Delete an object that refers another object in the DB,
        # but the object referred to is also being deleted,
        # therefore the deletion is valid.
        mock_dq, mock_dh = prepare_mocks

        validator = ReferenceValidator(mock_dh)
        mock_dh.execute_query = lambda query: []
        result_inetnum = parse_change_requests(
            SAMPLE_INETNUM + "delete: delete", mock_dh, AuthValidator(mock_dh), validator
        )
        validator.preload(result_inetnum)
        mock_dq.reset_mock()

        query_results = iter(
            [
                [{"object_text": SAMPLE_PERSON}],
                [
                    {
                        "object_text": SAMPLE_INETNUM,
                        "object_class": "inetnum",
                        "rpsl_pk": "192.0.2.0 - 192.0.2.255",
                        "source": "TEST",
                    }
                ],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_results)

        result = parse_change_requests(
            SAMPLE_PERSON + "delete: delete" + "\n", mock_dh, AuthValidator(mock_dh), validator
        )[0]
        result._check_references()
        assert result.is_valid(), result.error_messages
        assert not result.error_messages
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["person"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["sources", (["TEST"],), {}],
            ["lookup_attrs_in", ({"tech-c", "zone-c", "admin-c"}, ["PERSON-TEST"]), {}],
        ]

    def test_check_auth_valid_update_mntner(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_result1 = {"object_text": SAMPLE_INETNUM}
        query_result2 = {"object_text": SAMPLE_MNTNER}
        query_results = itertools.cycle([[query_result1], [query_result2]])
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_inetnum = parse_change_requests(
            SAMPLE_INETNUM + "password: crypt-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert result_inetnum._check_auth()
        assert not result_inetnum.error_messages

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["rpsl_pk", ("192.0.2.0 - 192.0.2.255",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
        ]

        auth_validator = AuthValidator(mock_dh)
        result_inetnum = parse_change_requests(
            SAMPLE_INETNUM + "password: md5-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert result_inetnum._check_auth()
        assert not result_inetnum.error_messages
        assert result_inetnum.notification_targets() == {
            "mnt-nfy@example.net",
            "mnt-nfy2@example.net",
            "notify@example.com",
        }

        auth_validator = AuthValidator(mock_dh, "PGPKEY-80F238C6")
        result_inetnum = parse_change_requests(SAMPLE_INETNUM, mock_dh, auth_validator, reference_validator)[
            0
        ]
        assert result_inetnum._check_auth()
        assert not result_inetnum.error_messages

    def test_check_auth_valid_create_mntner_referencing_self(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: []

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_mntner = parse_change_requests(
            SAMPLE_MNTNER + "override: override-password", mock_dh, auth_validator, reference_validator
        )[0]
        auth_validator.pre_approve([result_mntner.rpsl_obj_new])

        assert result_mntner._check_auth()
        assert not result_mntner.error_messages

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
        ]

    def test_check_auth_invalid_create_mntner_referencing_self_wrong_override_password(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: []

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_mntner = parse_change_requests(
            SAMPLE_MNTNER + "override: invalid-password", mock_dh, auth_validator, reference_validator
        )[0]
        auth_validator.pre_approve([result_mntner.rpsl_obj_new])

        assert not result_mntner._check_auth()
        assert result_mntner.error_messages == [
            "New mntner objects must be added by an administrator.",
        ]

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"OTHER1-MNT", "OTHER2-MNT", "TEST-MNT"},), {}],
        ]

    def test_check_auth_valid_update_mntner_submits_new_object_with_all_dummy_hash_values(
        self, prepare_mocks
    ):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: [{"object_text": SAMPLE_MNTNER}]

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        # Submit the mntner with dummy password values as would be returned by queries,
        # but a password attribute that is valid for the current DB object.
        data = SAMPLE_MNTNER.replace("LEuuhsBJNFV0Q", PASSWORD_HASH_DUMMY_VALUE)
        data = data.replace("$1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.", PASSWORD_HASH_DUMMY_VALUE)
        data = data.replace(
            "$2b$12$RMrlONJ0tasnpo.zHDF.yuYm/Gb1ARmIjP097ZoIWBn9YLIM2ao5W", PASSWORD_HASH_DUMMY_VALUE
        )
        result_mntner = parse_change_requests(
            data + "password: crypt-password", mock_dh, auth_validator, reference_validator
        )[0]
        auth_validator.pre_approve([result_mntner.rpsl_obj_new])
        assert result_mntner._check_auth()
        assert not result_mntner.error_messages
        assert result_mntner.info_messages == [
            "As you submitted dummy hash values, all password hashes on this object "
            "were replaced with a new BCRYPT-PW hash of the password you provided for "
            "authentication."
        ]

        auth_pgp, auth_hash = splitline_unicodesafe(result_mntner.rpsl_obj_new.parsed_data["auth"])
        assert auth_pgp == "PGPKey-80F238C6"
        assert auth_hash.startswith("BCRYPT-PW ")
        assert bcrypt.verify("crypt-password", auth_hash[10:])
        assert auth_hash in result_mntner.rpsl_obj_new.render_rpsl_text()
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"OTHER1-MNT", "OTHER2-MNT", "TEST-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"OTHER1-MNT", "OTHER2-MNT"},), {}],
        ]

    def test_check_auth_invalid_update_mntner_submits_new_object_with_mixed_dummy_hash_real_hash(
        self, prepare_mocks
    ):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: [{"object_text": SAMPLE_MNTNER}]

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        # Submit the mntner with dummy password values as would be returned by queries,
        # but a password attribute that is valid for the current DB object.
        data = SAMPLE_MNTNER.replace("LEuuhsBJNFV0Q", PASSWORD_HASH_DUMMY_VALUE)
        result_mntner = parse_change_requests(
            data + "password: md5-password", mock_dh, auth_validator, reference_validator
        )[0]
        auth_validator.pre_approve([result_mntner.rpsl_obj_new])
        assert not result_mntner.is_valid()
        assert result_mntner.error_messages == [
            "Either all password auth hashes in a submitted mntner must be dummy objects, or none.",
        ]

    def test_check_auth_invalid_update_mntner_submits_new_object_with_dummy_hash_multiple_passwords(
        self, prepare_mocks
    ):
        mock_dq, mock_dh = prepare_mocks

        mock_dh.execute_query = lambda query: [{"object_text": SAMPLE_MNTNER}]

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        # Submit the mntner with dummy password values as would be returned by queries,
        # but multiple password attributes, which means we wouldn't know which password to set.
        data = SAMPLE_MNTNER.replace("LEuuhsBJNFV0Q", PASSWORD_HASH_DUMMY_VALUE)
        data = data.replace(
            "$2b$12$RMrlONJ0tasnpo.zHDF.yuYm/Gb1ARmIjP097ZoIWBn9YLIM2ao5W", PASSWORD_HASH_DUMMY_VALUE
        )
        data = data.replace("$1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.", PASSWORD_HASH_DUMMY_VALUE)
        result_mntner = parse_change_requests(
            data + "password: md5-password\npassword: other-password",
            mock_dh,
            auth_validator,
            reference_validator,
        )[0]
        auth_validator.pre_approve([result_mntner.rpsl_obj_new])
        result_mntner._check_auth()
        assert not result_mntner.is_valid()
        assert result_mntner.error_messages == [
            "Object submitted with dummy hash values, but multiple or no passwords submitted. "
            "Either submit only full hashes, or a single password."
        ]

    def test_check_auth_invalid_update_mntner_wrong_password_current_db_object(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        # Make the crypt password invalid in the version from the mock database
        mock_dh.execute_query = lambda query: [{"object_text": SAMPLE_MNTNER.replace("CRYPT-Pw", "FAILED")}]

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        # This password is valid for the new object, but invalid for the current version in the DB
        result_mntner = parse_change_requests(
            SAMPLE_MNTNER + "password: crypt-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert not result_mntner._check_auth()
        assert result_mntner.error_messages == [
            "Authorisation for mntner TEST-MNT failed: must be authenticated by one of: TEST-MNT, "
            "OTHER1-MNT, OTHER2-MNT"
        ]
        assert result_mntner.notification_targets() == {"notify@example.net", "upd-to@example.net"}

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT", "OTHER1-MNT", "OTHER2-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"OTHER1-MNT", "OTHER2-MNT"},), {}],
        ]

    def test_check_auth_invalid_create_with_incorrect_password_referenced_mntner(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_results = iter([[{"object_text": SAMPLE_INETNUM}], [{"object_text": SAMPLE_MNTNER}], []])
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_inetnum = parse_change_requests(
            SAMPLE_INETNUM + "password: wrong-pw", mock_dh, auth_validator, reference_validator
        )[0]
        assert not result_inetnum._check_auth()
        assert "Authorisation for inetnum 192.0.2.0 - 192.0.2.255 failed" in result_inetnum.error_messages[0]
        assert "one of: TEST-MNT" in result_inetnum.error_messages[0]
        assert result_inetnum.notification_targets() == {"notify@example.com", "upd-to@example.net"}

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["rpsl_pk", ("192.0.2.0 - 192.0.2.255",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
        ]

    def test_check_auth_invalid_update_with_nonexistent_referenced_mntner(self, prepare_mocks):
        # This is a case that shouldn't happen, but in legacy databases it might.
        mock_dq, mock_dh = prepare_mocks

        query_results = iter(
            [
                [{"object_text": SAMPLE_INETNUM.replace("test-MNT", "FAIL-MNT")}],
                [{"object_text": SAMPLE_MNTNER}],
                [],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_inetnum = parse_change_requests(
            SAMPLE_INETNUM + "password: md5-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert not result_inetnum._check_auth(), result_inetnum
        assert "Authorisation for inetnum 192.0.2.0 - 192.0.2.255 failed" in result_inetnum.error_messages[0]
        assert "one of: FAIL-MNT" in result_inetnum.error_messages[0]
        assert result_inetnum.notification_targets() == {"notify@example.com"}

        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["rpsl_pk", ("192.0.2.0 - 192.0.2.255",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"FAIL-MNT"},), {}],
        ]

    def test_check_auth_valid_update_mntner_using_override(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_result1 = {"object_text": SAMPLE_INETNUM}
        query_result2 = {"object_text": SAMPLE_MNTNER}
        query_results = itertools.cycle([[query_result1], [query_result2]])
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_inetnum = parse_change_requests(
            SAMPLE_INETNUM + "override: override-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert result_inetnum._check_auth()
        assert not result_inetnum.error_messages
        assert not result_inetnum.notification_targets()

    def test_check_auth_invalid_update_mntner_using_incorrect_override(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_result1 = {"object_text": SAMPLE_INETNUM}
        query_result2 = {"object_text": SAMPLE_MNTNER}
        query_results = itertools.cycle([[query_result1], [query_result2]])
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_inetnum = parse_change_requests(
            SAMPLE_INETNUM + "override: wrong-override", mock_dh, auth_validator, reference_validator
        )[0]
        assert not result_inetnum._check_auth()
        assert result_inetnum.error_messages == [
            (
                "Authorisation for inetnum 192.0.2.0 - 192.0.2.255 failed: must be authenticated by one of:"
                " TEST-MNT"
            ),
        ]
        assert result_inetnum.notification_targets() == {"notify@example.com", "upd-to@example.net"}

    def test_check_auth_invalid_update_mntner_override_hash_misconfigured(
        self, prepare_mocks, monkeypatch, caplog
    ):
        mock_dq, mock_dh = prepare_mocks
        monkeypatch.setenv("IRRD_AUTH_OVERRIDE_PASSWORD", "invalid-hash")

        query_result1 = {"object_text": SAMPLE_INETNUM}
        query_result2 = {"object_text": SAMPLE_MNTNER}
        query_results = itertools.cycle([[query_result1], [query_result2]])
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_inetnum = parse_change_requests(
            SAMPLE_INETNUM + "override: override-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert not result_inetnum._check_auth()
        assert result_inetnum.error_messages == [
            (
                "Authorisation for inetnum 192.0.2.0 - 192.0.2.255 failed: must be authenticated by one of:"
                " TEST-MNT"
            ),
        ]
        assert result_inetnum.notification_targets() == {"notify@example.com", "upd-to@example.net"}
        assert "possible misconfigured hash" in caplog.text

    def test_check_auth_invalid_update_mntner_override_hash_empty(self, prepare_mocks, monkeypatch, caplog):
        mock_dq, mock_dh = prepare_mocks
        monkeypatch.setenv("IRRD_AUTH_OVERRIDE_PASSWORD", "")

        query_result1 = {"object_text": SAMPLE_INETNUM}
        query_result2 = {"object_text": SAMPLE_MNTNER}
        query_results = itertools.cycle([[query_result1], [query_result2]])
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_inetnum = parse_change_requests(
            SAMPLE_INETNUM + "override: override-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert not result_inetnum._check_auth()
        assert result_inetnum.error_messages == [
            (
                "Authorisation for inetnum 192.0.2.0 - 192.0.2.255 failed: must be authenticated by one of:"
                " TEST-MNT"
            ),
        ]
        assert result_inetnum.notification_targets() == {"notify@example.com", "upd-to@example.net"}
        assert "Ignoring override password, auth.override_password not set." in caplog.text

    def test_check_valid_related_mntners_disabled(self, prepare_mocks, config_override):
        config_override({"auth": {"authenticate_parents_route_creation": False}})
        mock_dq, mock_dh = prepare_mocks

        query_answers = [
            [],  # existing object version
            [{"object_text": SAMPLE_MNTNER}],  # mntner for object
            # No further queries expected
        ]
        query_results = itertools.cycle(query_answers)
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_route = parse_change_requests(
            SAMPLE_ROUTE + "password: md5-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert result_route._check_auth()
        assert not result_route.error_messages
        assert result_route.notification_targets() == {"mnt-nfy@example.net", "mnt-nfy2@example.net"}

        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["route"],), {}],
            ["rpsl_pk", ("192.0.2.0/24AS65537",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
        ]

    def test_check_invalid_related_mntners_inetnum_exact(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        # Break the hash so auth fails for the related mntner only
        related_mntner = SAMPLE_MNTNER.replace("8PCh", "aaa").replace("upd-to@", "upd-to-related@")

        query_answers = [
            [],  # existing object version
            [{"object_text": SAMPLE_MNTNER}],  # mntner for object
            [
                {
                    # attempt to look for exact inetnum
                    "object_class": "route",
                    "rpsl_pk": "192.0.2.0/24AS65537",
                    "parsed_data": {"mnt-by": ["RELATED-MNT"]},
                }
            ],
            [{"object_text": related_mntner}],  # related mntner retrieval
        ]
        query_results = itertools.cycle(query_answers)
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_route = parse_change_requests(
            SAMPLE_ROUTE + "password: md5-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert not result_route._check_auth()
        assert (
            result_route.error_messages[0]
            == "Authorisation for route 192.0.2.0/24AS65537 failed: must be authenticated by one of: "
            "RELATED-MNT - from parent route 192.0.2.0/24AS65537"
        )
        assert result_route.notification_targets() == {"upd-to-related@example.net"}

        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["route"],), {}],
            ["rpsl_pk", ("192.0.2.0/24AS65537",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["first_only", (), {}],
            ["ip_exact", ("192.0.2.0/24",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"RELATED-MNT"},), {}],
        ]

    def test_check_valid_related_mntners_inet6num_exact(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        related_mntner = SAMPLE_MNTNER.replace("TEST-MNT", "RELATED-MNT")

        query_answers = [
            [],  # existing object version
            [{"object_text": SAMPLE_MNTNER}],  # mntner for object
            [
                {
                    # attempt to look for exact inetnum
                    "object_class": "route6",
                    "rpsl_pk": "2001:db8::/48AS65537",
                    "parsed_data": {"mnt-by": ["RELATED-MNT"]},
                }
            ],
            [{"object_text": related_mntner}],  # related mntner retrieval
        ]
        query_results = itertools.cycle(query_answers)
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_route = parse_change_requests(
            SAMPLE_ROUTE6 + "password: md5-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert result_route._check_auth()
        assert result_route._check_auth()  # should be cached, no extra db queries
        assert not result_route.error_messages
        assert result_route.notification_targets() == {"mnt-nfy2@example.net", "mnt-nfy@example.net"}

        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["route6"],), {}],
            ["rpsl_pk", ("2001:DB8::/48AS65537",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inet6num"],), {}],
            ["first_only", (), {}],
            ["ip_exact", ("2001:db8::/48",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"RELATED-MNT"},), {}],
        ]

    def test_check_valid_related_mntners_inetnum_less_specific(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_answers = [
            [],  # existing object version
            [{"object_text": SAMPLE_MNTNER}],  # mntner for object
            [],  # attempt to look for exact inetnum
            [
                {
                    # attempt to look for less specific inetnum
                    "object_class": "route",
                    "rpsl_pk": "192.0.2.0/24AS65537",
                    "parsed_data": {"mnt-by": ["RELATED-MNT"]},
                }
            ],
            [{"object_text": SAMPLE_MNTNER}],  # related mntner retrieval
        ]
        query_results = itertools.cycle(query_answers)
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_route = parse_change_requests(
            SAMPLE_ROUTE + "password: md5-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert result_route._check_auth()
        assert not result_route.error_messages
        assert result_route.notification_targets() == {"mnt-nfy2@example.net", "mnt-nfy@example.net"}

        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["route"],), {}],
            ["rpsl_pk", ("192.0.2.0/24AS65537",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["first_only", (), {}],
            ["ip_exact", ("192.0.2.0/24",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["first_only", (), {}],
            ["ip_less_specific_one_level", ("192.0.2.0/24",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"RELATED-MNT"},), {}],
        ]

    def test_check_valid_related_mntners_route(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_answers = [
            [],  # existing object version
            [{"object_text": SAMPLE_MNTNER}],  # mntner for object
            [],  # attempt to look for exact inetnum
            [],  # attempt to look for less specific inetnum
            [
                {
                    # attempt to look for less specific route
                    "object_class": "route",
                    "rpsl_pk": "192.0.2.0/24AS65537",
                    "parsed_data": {"mnt-by": ["RELATED-MNT"]},
                }
            ],
            [{"object_text": SAMPLE_MNTNER}],  # related mntner retrieval
        ]
        query_results = itertools.cycle(query_answers)
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_route = parse_change_requests(
            SAMPLE_ROUTE + "password: md5-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert result_route._check_auth()
        assert not result_route.error_messages
        assert result_route.notification_targets() == {"mnt-nfy2@example.net", "mnt-nfy@example.net"}

        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["route"],), {}],
            ["rpsl_pk", ("192.0.2.0/24AS65537",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["first_only", (), {}],
            ["ip_exact", ("192.0.2.0/24",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["first_only", (), {}],
            ["ip_less_specific_one_level", ("192.0.2.0/24",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["route"],), {}],
            ["first_only", (), {}],
            ["ip_less_specific_one_level", ("192.0.2.0/24",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"RELATED-MNT"},), {}],
        ]

    def test_check_valid_no_related_mntners(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_answers = [
            [],  # existing object version
            [{"object_text": SAMPLE_MNTNER}],  # mntner for object
            [],  # attempt to look for exact inetnum
            [],  # attempt to look for less specific inetnum
            [],  # attempt to look for less specific route
        ]
        query_results = itertools.cycle(query_answers)
        mock_dh.execute_query = lambda query: next(query_results)

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        result_route = parse_change_requests(
            SAMPLE_ROUTE + "password: md5-password", mock_dh, auth_validator, reference_validator
        )[0]
        assert result_route._check_auth()
        assert not result_route.error_messages
        assert result_route.notification_targets() == {"mnt-nfy2@example.net", "mnt-nfy@example.net"}

        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["route"],), {}],
            ["rpsl_pk", ("192.0.2.0/24AS65537",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["first_only", (), {}],
            ["ip_exact", ("192.0.2.0/24",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inetnum"],), {}],
            ["first_only", (), {}],
            ["ip_less_specific_one_level", ("192.0.2.0/24",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["route"],), {}],
            ["first_only", (), {}],
            ["ip_less_specific_one_level", ("192.0.2.0/24",), {}],
        ]

    def test_rpki_validation(self, prepare_mocks, monkeypatch, config_override):
        config_override({"rpki": {"roa_source": None}})
        mock_roa_validator = Mock()
        monkeypatch.setattr("irrd.updates.parser.SingleRouteROAValidator", lambda dh: mock_roa_validator)
        mock_dq, mock_dh = prepare_mocks

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        # New object, RPKI invalid, RPKI-aware mode disabled
        mock_dh.execute_query = lambda query: []
        mock_roa_validator.validate_route = lambda prefix, asn, source: RPKIStatus.invalid
        result_route = parse_change_requests(SAMPLE_ROUTE, mock_dh, auth_validator, reference_validator)[0]
        assert result_route._check_conflicting_roa()
        assert not result_route.error_messages

        config_override({"rpki": {"roa_source": "https://example.com/roa.json"}})

        # New object, RPKI-aware mode enabled but object not RPKI relevant
        mock_dh.execute_query = lambda query: []
        mock_roa_validator.validate_route = lambda prefix, asn, source: RPKIStatus.invalid
        result_inetnum = parse_change_requests(SAMPLE_INETNUM, mock_dh, auth_validator, reference_validator)[
            0
        ]
        assert result_inetnum._check_conflicting_roa()
        assert not result_inetnum.error_messages

        # New object, RPKI not_found
        mock_dh.execute_query = lambda query: []
        mock_roa_validator.validate_route = lambda prefix, asn, source: RPKIStatus.not_found
        result_route = parse_change_requests(SAMPLE_ROUTE, mock_dh, auth_validator, reference_validator)[0]
        assert result_route._check_conflicting_roa()
        assert not result_route.error_messages

        # New object, RPKI invalid
        mock_dh.execute_query = lambda query: []
        mock_roa_validator.validate_route = lambda prefix, asn, source: RPKIStatus.invalid
        result_route = parse_change_requests(SAMPLE_ROUTE, mock_dh, auth_validator, reference_validator)[0]
        assert not result_route._check_conflicting_roa()
        assert result_route.error_messages[0].startswith(
            "RPKI ROAs were found that conflict with this object."
        )

        # Update object, RPKI invalid
        mock_dh.execute_query = lambda query: [{"object_text": SAMPLE_ROUTE}]
        mock_roa_validator.validate_route = lambda prefix, asn, source: RPKIStatus.invalid
        result_route = parse_change_requests(SAMPLE_ROUTE, mock_dh, auth_validator, reference_validator)[0]
        assert not result_route._check_conflicting_roa()
        assert not result_route._check_conflicting_roa()  # Should use cache
        assert result_route.error_messages[0].startswith(
            "RPKI ROAs were found that conflict with this object."
        )

        # Delete object, RPKI invalid
        mock_dh.execute_query = lambda query: [{"object_text": SAMPLE_ROUTE}]
        mock_roa_validator.validate_route = lambda prefix, asn, source: RPKIStatus.invalid
        obj_text = SAMPLE_ROUTE + "delete: delete"
        result_route = parse_change_requests(obj_text, mock_dh, auth_validator, reference_validator)[0]
        assert result_route._check_conflicting_roa()

    def test_scopefilter_validation(self, prepare_mocks, monkeypatch, config_override):
        mock_scopefilter_validator = Mock(spec=ScopeFilterValidator)
        monkeypatch.setattr("irrd.updates.parser.ScopeFilterValidator", lambda: mock_scopefilter_validator)
        mock_dq, mock_dh = prepare_mocks

        reference_validator = ReferenceValidator(mock_dh)
        auth_validator = AuthValidator(mock_dh)

        # New object, in scope
        mock_dh.execute_query = lambda query: []
        mock_scopefilter_validator.validate_rpsl_object = lambda obj: (ScopeFilterStatus.in_scope, "")
        result_route = parse_change_requests(SAMPLE_ROUTE, mock_dh, auth_validator, reference_validator)[0]
        assert result_route._check_scopefilter()
        assert not result_route.error_messages

        # New object, out of scope
        mock_dh.execute_query = lambda query: []
        mock_scopefilter_validator.validate_rpsl_object = lambda obj: (
            ScopeFilterStatus.out_scope_as,
            "out of scope AS",
        )
        result_route = parse_change_requests(SAMPLE_ROUTE, mock_dh, auth_validator, reference_validator)[0]
        assert not result_route._check_scopefilter()
        assert result_route.error_messages[0] == "Contains out of scope information: out of scope AS"

        # Update object, out of scope, permitted
        mock_dh.execute_query = lambda query: [{"object_text": SAMPLE_ROUTE}]
        mock_scopefilter_validator.validate_rpsl_object = lambda obj: (
            ScopeFilterStatus.out_scope_prefix,
            "out of scope prefix",
        )
        result_route = parse_change_requests(SAMPLE_ROUTE, mock_dh, auth_validator, reference_validator)[0]
        assert result_route._check_scopefilter()
        assert not result_route.error_messages
        assert result_route.info_messages[1] == "Contains out of scope information: out of scope prefix"

        # Delete object, out of scope
        mock_dh.execute_query = lambda query: [{"object_text": SAMPLE_ROUTE}]
        mock_scopefilter_validator.validate_rpsl_object = lambda obj: (
            ScopeFilterStatus.out_scope_as,
            "out of scope AS",
        )
        obj_text = SAMPLE_ROUTE + "delete: delete"
        result_route = parse_change_requests(obj_text, mock_dh, auth_validator, reference_validator)[0]
        assert result_route._check_scopefilter()

    def test_user_report(self, prepare_mocks):
        mock_dq, mock_dh = prepare_mocks

        query_results = iter(
            [
                [{"object_text": SAMPLE_INETNUM + "remarks: MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM."}],
                [],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_results)

        result_inetnum, result_as_set, result_unknown, result_invalid = parse_change_requests(
            self._request_text(), mock_dh, AuthValidator(mock_dh), None
        )
        report_inetnum = result_inetnum.submitter_report_human()
        report_as_set = result_as_set.submitter_report_human()
        report_unknown = result_unknown.submitter_report_human()
        report_invalid = result_invalid.submitter_report_human()

        assert "Delete succeeded" in report_inetnum
        assert "remarks: " in report_inetnum  # full RPSL object should be included
        assert "INFO: Address range 192" in report_inetnum

        assert report_as_set == "Create succeeded: [as-set] AS65537:AS-SETTEST\n"

        assert "FAILED" in report_unknown
        assert "ERROR: unknown object class" in report_unknown

        assert "FAILED" in report_invalid
        assert "aut-num: pw1"  # full RPSL object should be included
        assert "ERROR: Mandatory attribute" in report_invalid
        assert "ERROR: Invalid AS number PW1" in report_invalid

        # The extra MD5-PW is a workaround to test #722 until we can address #412
        query_results = iter(
            [
                [{"object_text": SAMPLE_INETNUM + "remarks: MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM."}],
                [],
            ]
        )
        mock_dh.execute_query = lambda query: next(query_results)

        assert (
            result_inetnum.notification_target_report()
            == textwrap.dedent(
                """
            Delete succeeded for object below: [inetnum] 192.0.2.0 - 192.0.2.255:
            
            inetnum:        192.0.2.0 - 192.0.2.255
            netname:        NET-TEST-V4
            descr:          description
            country:        IT
            notify:         notify@example.com
            geofeed:        https://example.com/geofeed
            admin-c:        PERSON-TEST
            tech-c:         PERSON-TEST
            status:         ASSIGNED PA
            mnt-by:         test-MNT
            changed:        changed@example.com 20190701 # comment
            source:         TEST
            remarks:        remark
            remarks:        MD5-pw DummyValue  # Filtered for security
        """
            ).strip()
            + "\n"
        )

        assert (
            result_as_set.notification_target_report()
            == textwrap.dedent(
                """
            Create succeeded for object below: [as-set] AS65537:AS-SETTEST:
            
            as-set:         AS65537:AS-SETTEST
            descr:          description
            members:        AS65538,AS65539
            members:        AS65537
            members:        AS-OTHERSET
            tech-c:         PERSON-TEST
            admin-c:        PERSON-TEST
            notify:         notify@example.com
            mnt-by:         TEST-MNT
            changed:        changed@example.com 20190701 # comment
            source:         TEST
            remarks:        remark
        """
            ).strip()
            + "\n"
        )

        inetnum_modify = SAMPLE_INETNUM.replace("PERSON-TEST", "NEW-TEST")
        result_inetnum_modify = parse_change_requests(inetnum_modify, mock_dh, AuthValidator(mock_dh), None)[
            0
        ]
        assert (
            result_inetnum_modify.notification_target_report()
            == textwrap.dedent(
                """
            Modify succeeded for object below: [inetnum] 192.0.2.0 - 192.0.2.255:
            
            @@ -4,11 +4,10 @@
             country:        IT
             notify:         notify@example.com
             geofeed:        https://example.com/geofeed
            -admin-c:        PERSON-TEST
            -tech-c:         PERSON-TEST
            +admin-c:        NEW-TEST
            +tech-c:         NEW-TEST
             status:         ASSIGNED PA
             mnt-by:         test-MNT
             changed:        changed@example.com 20190701 # comment
             source:         TEST
             remarks:        remark
            -remarks:        MD5-pw DummyValue  # Filtered for security
            
            New version of this object:
            
            inetnum:        192.0.2.0 - 192.0.2.255
            netname:        NET-TEST-V4
            descr:          description
            country:        IT
            notify:         notify@example.com
            geofeed:        https://example.com/geofeed
            admin-c:        NEW-TEST
            tech-c:         NEW-TEST
            status:         ASSIGNED PA
            mnt-by:         test-MNT
            changed:        changed@example.com 20190701 # comment
            source:         TEST
            remarks:        remark
        """
            ).strip()
            + "\n"
        )

        # Fake the result to look like an authentication failure
        result_inetnum_modify.status = UpdateRequestStatus.ERROR_AUTH
        assert (
            result_inetnum_modify.notification_target_report()
            == textwrap.dedent(
                """
            Modify FAILED AUTHORISATION for object below: [inetnum] 192.0.2.0 - 192.0.2.255:
            
            @@ -4,11 +4,10 @@
             country:        IT
             notify:         notify@example.com
             geofeed:        https://example.com/geofeed
            -admin-c:        PERSON-TEST
            -tech-c:         PERSON-TEST
            +admin-c:        NEW-TEST
            +tech-c:         NEW-TEST
             status:         ASSIGNED PA
             mnt-by:         test-MNT
             changed:        changed@example.com 20190701 # comment
             source:         TEST
             remarks:        remark
            -remarks:        MD5-pw DummyValue  # Filtered for security

            *Rejected* new version of this object:
            
            inetnum:        192.0.2.0 - 192.0.2.255
            netname:        NET-TEST-V4
            descr:          description
            country:        IT
            notify:         notify@example.com
            geofeed:        https://example.com/geofeed
            admin-c:        NEW-TEST
            tech-c:         NEW-TEST
            status:         ASSIGNED PA
            mnt-by:         test-MNT
            changed:        changed@example.com 20190701 # comment
            source:         TEST
            remarks:        remark
        """
            ).strip()
            + "\n"
        )

        with pytest.raises(ValueError) as ve:
            result_unknown.notification_target_report()
        assert "changes that are valid or have failed authorisation" in str(ve.value)

    def _request_text(self):
        unknown_class = "unknown-object: foo\n"
        invalid_object = "aut-num: pw1\n"

        request_text = "password: pw1\n" + SAMPLE_INETNUM + "delete: delete\n\r\n\r\n\r\n"
        request_text += SAMPLE_AS_SET + "password: pw2\n\n"
        request_text += "password: pw3\n" + unknown_class + "\r\n"
        request_text += invalid_object + "\noverride: override-pw"
        return request_text


class TestSuspensionRequest:
    @pytest.fixture
    def prepare_suspension_request_test(self, prepare_mocks, monkeypatch, config_override):
        config_override({"sources": {"TEST": {"suspension_enabled": True}}})
        mock_dq, mock_dh = prepare_mocks
        mock_auth_validator = Mock(spec=AuthValidator)
        mock_suspend_for_mntner = Mock(suspend_for_mntner)
        monkeypatch.setattr("irrd.updates.parser.suspend_for_mntner", mock_suspend_for_mntner)
        mock_reactivate_for_mntner = Mock(suspend_for_mntner)
        monkeypatch.setattr("irrd.updates.parser.reactivate_for_mntner", mock_reactivate_for_mntner)
        mock_auth_validator.check_override.return_value = True

        default_request = (
            textwrap.dedent(
                """
            override: override-pw
            
            suspension: suspend
            mntner: MNT-SUSPEND
            source: TEST
            """
            ).strip()
            + "\n"
        )

        return (
            mock_dh,
            mock_auth_validator,
            mock_suspend_for_mntner,
            mock_reactivate_for_mntner,
            default_request,
        )

    def test_valid_suspension(self, prepare_suspension_request_test):
        mock_dh, mock_auth_validator, mock_suspend_for_mntner, mock_reactivate_for_mntner, default_request = (
            prepare_suspension_request_test
        )

        (r, *_) = parse_change_requests(default_request, mock_dh, mock_auth_validator, None)

        assert r.request_type == SuspensionRequestType.SUSPEND
        assert r.status == UpdateRequestStatus.PROCESSING, r.error_messages
        assert r.is_valid()
        assert mock_auth_validator.overrides == ["override-pw"]

        mock_suspend_for_mntner.return_value = [
            {"object_class": "route", "rpsl_pk": "192.0.2.0/24", "source": "TEST"},
        ]
        r.save()
        assert r.status == UpdateRequestStatus.SAVED
        assert not r.error_messages
        assert r.info_messages == ["Suspended route/192.0.2.0/24/TEST"]

        assert mock_suspend_for_mntner.call_count == 1
        assert mock_suspend_for_mntner.call_args[0][1].pk() == "MNT-SUSPEND"
        assert flatten_mock_calls(mock_auth_validator) == [["check_override", (), {}]]

        assert not r.notification_targets()
        assert r.request_type_str() == "suspend"
        assert r.object_pk_str() == "MNT-SUSPEND"
        assert r.object_class_str() == "mntner"

        assert r.submitter_report_json() == {
            "successful": True,
            "type": "suspend",
            "object_class": "mntner",
            "rpsl_pk": "MNT-SUSPEND",
            "info_messages": ["Suspended route/192.0.2.0/24/TEST"],
            "error_messages": [],
        }
        assert (
            r.submitter_report_human()
            == "Suspend succeeded: [mntner] MNT-SUSPEND\nINFO: Suspended route/192.0.2.0/24/TEST\n"
        )

    def test_valid_reactivation(self, prepare_suspension_request_test):
        mock_dh, mock_auth_validator, mock_suspend_for_mntner, mock_reactivate_for_mntner, default_request = (
            prepare_suspension_request_test
        )

        request = default_request.replace("suspend", "reactivate")
        (r, *_) = parse_change_requests(request, mock_dh, mock_auth_validator, None)

        assert r.request_type == SuspensionRequestType.REACTIVATE
        assert r.status == UpdateRequestStatus.PROCESSING, r.error_messages
        assert r.is_valid()
        assert mock_auth_validator.overrides == ["override-pw"]

        mock_reactivate_for_mntner.return_value = [
            ["route/192.0.2.0/24/TEST"],
            ["info msg"],
        ]
        r.save()
        assert r.status == UpdateRequestStatus.SAVED
        assert not r.error_messages
        assert r.info_messages == ["info msg", "Restored route/192.0.2.0/24/TEST"]

        assert mock_reactivate_for_mntner.call_count == 1
        assert mock_reactivate_for_mntner.call_args[0][1].pk() == "MNT-SUSPEND"
        assert flatten_mock_calls(mock_auth_validator) == [["check_override", (), {}]]

    def test_failed_reactivation(self, prepare_suspension_request_test):
        mock_dh, mock_auth_validator, mock_suspend_for_mntner, mock_reactivate_for_mntner, default_request = (
            prepare_suspension_request_test
        )

        request = default_request.replace("suspend", "reactivate")
        (r, *_) = parse_change_requests(request, mock_dh, mock_auth_validator, None)

        mock_reactivate_for_mntner.side_effect = ValueError("failure")
        r.save()
        assert r.status == UpdateRequestStatus.ERROR_PARSING
        assert r.error_messages == ["failure"]
        assert not r.info_messages
        assert "failure" in r.submitter_report_human()

    def test_not_authoritative(self, prepare_suspension_request_test, config_override):
        mock_dh, mock_auth_validator, mock_suspend_for_mntner, mock_reactivate_for_mntner, default_request = (
            prepare_suspension_request_test
        )
        config_override({"sources": {"TEST": {"suspension_enabled": False}}})

        (r, *_) = parse_change_requests(default_request, mock_dh, mock_auth_validator, None)

        assert r.request_type == SuspensionRequestType.SUSPEND
        assert r.status == UpdateRequestStatus.ERROR_NON_AUTHORITIVE
        assert r.error_messages == [
            "This instance is not authoritative for source TEST or suspension is not enabled",
        ]
        assert not r.is_valid()

        with pytest.raises(ValueError):
            r.save()

    def test_unknown_suspension(self, prepare_suspension_request_test):
        mock_dh, mock_auth_validator, mock_suspend_for_mntner, mock_reactivate_for_mntner, default_request = (
            prepare_suspension_request_test
        )

        request = default_request.replace("suspend", "invalid")
        (r, *_) = parse_change_requests(request, mock_dh, mock_auth_validator, None)

        assert not r.request_type
        assert r.status == UpdateRequestStatus.ERROR_PARSING
        assert r.error_messages == [
            "Unknown suspension type: invalid",
        ]
        assert not r.is_valid()

    def test_invalid_rpsl_object(self, prepare_suspension_request_test):
        mock_dh, mock_auth_validator, mock_suspend_for_mntner, mock_reactivate_for_mntner, default_request = (
            prepare_suspension_request_test
        )

        request = "suspension: suspend\nmntner: TEST"
        (r, *_) = parse_change_requests(request, mock_dh, mock_auth_validator, None)

        assert r.status == UpdateRequestStatus.ERROR_PARSING
        assert r.error_messages == [
            'Primary key attribute "source" on object mntner is missing',
        ]
        assert not r.is_valid()

    def test_invalid_rpsl_object_class(self, prepare_suspension_request_test):
        mock_dh, mock_auth_validator, mock_suspend_for_mntner, mock_reactivate_for_mntner, default_request = (
            prepare_suspension_request_test
        )

        request = "suspension: suspend\nsource: TEST"
        (r, *_) = parse_change_requests(request, mock_dh, mock_auth_validator, None)

        assert r.status == UpdateRequestStatus.ERROR_UNKNOWN_CLASS
        assert r.error_messages == [
            "unknown object class: source",
        ]
        assert not r.is_valid()

    def test_incorrect_object_class(self, prepare_suspension_request_test):
        mock_dh, mock_auth_validator, mock_suspend_for_mntner, mock_reactivate_for_mntner, default_request = (
            prepare_suspension_request_test
        )

        request = "override: override-pw\n\nsuspension: suspend\n" + SAMPLE_INETNUM
        (r, *_) = parse_change_requests(request, mock_dh, mock_auth_validator, None)

        assert r.status == UpdateRequestStatus.ERROR_PARSING
        assert r.error_messages == [
            "Suspensions/reactivations can only be done on mntner objects",
        ]
        assert not r.is_valid()

    def test_invalid_override_password(self, prepare_suspension_request_test):
        mock_dh, mock_auth_validator, mock_suspend_for_mntner, mock_reactivate_for_mntner, default_request = (
            prepare_suspension_request_test
        )
        mock_auth_validator.check_override.return_value = False

        (r, *_) = parse_change_requests(default_request, mock_dh, mock_auth_validator, None)

        assert not r.is_valid()
        assert r.status == UpdateRequestStatus.ERROR_AUTH
        assert r.error_messages == [
            "Invalid authentication: override password invalid or missing",
        ]
