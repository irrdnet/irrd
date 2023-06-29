import itertools
import uuid
from unittest import mock
from unittest.mock import Mock

import pytest
from IPy import IP

from irrd.conf import AUTH_SET_CREATION_COMMON_KEY, RPSL_MNTNER_AUTH_INTERNAL
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseSuspendedQuery
from irrd.updates.parser_state import AuthMethod, UpdateRequestType
from irrd.utils.rpsl_samples import (
    SAMPLE_AS_SET,
    SAMPLE_FILTER_SET,
    SAMPLE_MNTNER,
    SAMPLE_MNTNER_CRYPT,
    SAMPLE_MNTNER_MD5,
    SAMPLE_PERSON,
    SAMPLE_ROUTE,
    SAMPLE_ROUTE6,
)
from irrd.utils.test_utils import flatten_mock_calls
from irrd.utils.text import remove_auth_hashes
from irrd.vendor.mock_alchemy.mocking import UnifiedAlchemyMagicMock

from ...storage.models import (
    AuthApiToken,
    AuthMntner,
    AuthoritativeChangeOrigin,
    AuthUser,
)
from ...utils.factories import AuthApiTokenFactory, AuthMntnerFactory, AuthUserFactory
from ..validators import AuthValidator, RulesValidator, ValidatorResult

VALID_PW = "override-password"
INVALID_PW = "not-override-password"
VALID_PW_HASH = "$1$J6KycItM$MbPaBU6iFSGFV299Rk7Di0"
MNTNER_OBJ_CRYPT_PW = SAMPLE_MNTNER.replace("MD5", "")
MNTNER_OBJ_MD5_PW = SAMPLE_MNTNER.replace("CRYPT", "")


def test_validator_result():
    user = AuthUserFactory.build(pk=uuid.uuid4())
    api_key = AuthApiTokenFactory.build(pk=uuid.uuid4())
    mntner = AuthMntnerFactory.build(pk=uuid.uuid4(), rpsl_mntner_obj_id=None)

    result = ValidatorResult(
        auth_through_internal_user=user,
        auth_through_api_key=api_key,
        auth_through_internal_mntner=mntner,
        auth_through_mntner="TEST-MNT",
    ).to_change_log()
    assert result.auth_by_user_id == str(user.pk)
    assert result.auth_by_user_email == user.email
    assert result.auth_by_api_key_id == str(api_key.pk)
    assert result.auth_by_api_key_id_fixed == str(api_key.pk)
    assert result.auth_through_rpsl_mntner_pk == "TEST-MNT"

    assert (
        ValidatorResult(auth_method=AuthMethod.MNTNER_PASSWORD).to_change_log().auth_by_rpsl_mntner_password
    )
    assert ValidatorResult(auth_method=AuthMethod.MNTNER_PGP_KEY).to_change_log().auth_by_rpsl_mntner_pgp_key
    assert ValidatorResult(auth_method=AuthMethod.OVERRIDE_PASSWORD).to_change_log().auth_by_override


class TestAuthValidator:
    @pytest.fixture()
    def prepare_mocks(self, monkeypatch, config_override):
        mock_dh = Mock()
        mock_dq = Mock()
        monkeypatch.setattr("irrd.updates.validators.RPSLDatabaseQuery", lambda: mock_dq)

        config_override(
            {
                "auth": {"password_hashers": {"crypt-pw": "enabled"}},
            }
        )

        validator = AuthValidator(mock_dh, AuthoritativeChangeOrigin.webapi)
        yield validator, mock_dq, mock_dh

    def test_override_valid(self, prepare_mocks, config_override):
        config_override(
            {
                "auth": {"override_password": VALID_PW_HASH},
            }
        )
        validator, mock_dq, mock_dh = prepare_mocks
        person = rpsl_object_from_text(SAMPLE_PERSON)

        validator.overrides = [VALID_PW]
        result = validator.process_auth(person, None)
        assert result.is_valid(), result.error_messages
        assert result.auth_method == AuthMethod.OVERRIDE_PASSWORD
        assert result.auth_method
        assert result.auth_method.used_override()

        person = rpsl_object_from_text(SAMPLE_PERSON)
        result = validator.process_auth(person, rpsl_obj_current=person)
        assert result.is_valid(), result.error_messages
        assert result.auth_method == AuthMethod.OVERRIDE_PASSWORD

    def test_override_internal_auth(self, prepare_mocks, config_override):
        validator, mock_dq, mock_dh = prepare_mocks
        mock_dh.execute_query = lambda q: []
        person = rpsl_object_from_text(SAMPLE_PERSON)

        user = AuthUser(override=True)
        validator = AuthValidator(mock_dh, keycert_obj_pk=None, internal_authenticated_user=user)

        result = validator.process_auth(person, None)
        assert result.is_valid(), result.error_messages
        assert result.auth_method == AuthMethod.OVERRIDE_INTERNAL_AUTH

        user.override = False
        result = validator.process_auth(person, None)
        assert not result.is_valid()
        assert result.auth_method == AuthMethod.NONE
        assert not result.auth_method.used_override()

    def test_override_invalid_or_missing(self, prepare_mocks, config_override):
        # This test mostly ignores the regular process that happens
        # after override validation fails.
        validator, mock_dq, mock_dh = prepare_mocks
        mock_dh.execute_query = lambda q: []
        person = rpsl_object_from_text(SAMPLE_PERSON)

        validator.overrides = [VALID_PW]
        result = validator.process_auth(person, None)
        assert not result.is_valid()
        assert result.auth_method == AuthMethod.NONE

        config_override(
            {
                "auth": {"override_password": VALID_PW_HASH},
            }
        )
        validator.overrides = []
        result = validator.process_auth(person, None)
        assert not result.is_valid()
        assert result.auth_method == AuthMethod.NONE

        validator.overrides = [INVALID_PW]
        result = validator.process_auth(person, None)
        assert not result.is_valid()
        assert result.auth_method == AuthMethod.NONE

        config_override(
            {
                "auth": {"override_password": "not-valid-hash"},
            }
        )
        person = rpsl_object_from_text(SAMPLE_PERSON)
        result = validator.process_auth(person, None)
        assert not result.is_valid()
        assert result.auth_method == AuthMethod.NONE

    def test_valid_new_person(self, prepare_mocks):
        validator, mock_dq, mock_dh = prepare_mocks
        person = rpsl_object_from_text(SAMPLE_PERSON)
        mock_dh.execute_query = lambda q: [
            {"object_class": "mntner", "object_text": SAMPLE_MNTNER},
        ]

        validator.passwords = [SAMPLE_MNTNER_MD5]
        result = validator.process_auth(person, None)
        assert result.is_valid(), result.error_messages
        assert result.auth_method == AuthMethod.MNTNER_PASSWORD
        assert len(result.mntners_notify) == 1
        assert result.mntners_notify[0].pk() == "TEST-MNT"

        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
        ]

    def test_valid_new_person_api_key(self, prepare_mocks, monkeypatch):
        validator, mock_dq, mock_dh = prepare_mocks
        person = rpsl_object_from_text(SAMPLE_PERSON)
        mock_mntner = AuthMntner(rpsl_mntner_pk="TEST-MNT")
        mock_sa_session = UnifiedAlchemyMagicMock(
            data=[
                (
                    [
                        mock.call.query(AuthMntner),
                        mock.call.filter(
                            AuthMntner.rpsl_mntner_pk == "TEST-MNT", AuthMntner.rpsl_mntner_source == "TEST"
                        ),
                    ],
                    [mock_mntner],
                )
            ]
        )
        mock_api_key = AuthApiTokenFactory.build(mntner=mock_mntner)
        monkeypatch.setattr("irrd.updates.validators.saorm.Session", lambda bind: mock_sa_session)

        mock_dh._connection = None
        mock_dh.execute_query = lambda q: [
            {"object_class": "mntner", "object_text": SAMPLE_MNTNER},
        ]
        mock_sa_session.all = lambda: [mock_api_key]

        validator.api_keys = ["key"]
        result = validator.process_auth(person, None)
        assert result.is_valid(), result.error_messages
        assert result.mntners_notify[0].pk() == "TEST-MNT"
        assert result.auth_method == AuthMethod.MNTNER_API_KEY
        assert result.auth_through_mntner == "TEST-MNT"
        assert result.auth_through_internal_mntner.rpsl_mntner_pk == "TEST-MNT"

        mock_sa_session.filter.assert_has_calls(
            [
                mock.call(
                    AuthMntner.rpsl_mntner_pk == "TEST-MNT",
                    AuthMntner.rpsl_mntner_source == "TEST",
                    AuthApiToken.token.in_(["key"]),
                ),
            ]
        )

        validator.origin = AuthoritativeChangeOrigin.webui
        result = validator.process_auth(person, None)
        assert not result.is_valid(), result.error_messages

        validator.origin = AuthoritativeChangeOrigin.email
        result = validator.process_auth(person, None)
        assert result.is_valid(), result.error_messages

        mock_api_key.enabled_email = False
        validator.origin = AuthoritativeChangeOrigin.email
        result = validator.process_auth(person, None)
        assert not result.is_valid(), result.error_messages

        mock_api_key.ip_restriction = "192.0.2.0/26,192.0.2.64/26"
        validator.remote_ip = IP("192.0.2.1")
        validator.origin = AuthoritativeChangeOrigin.webapi
        result = validator.process_auth(person, None)
        assert result.is_valid(), result.error_messages

        validator.remote_ip = IP("192.0.2.200")
        validator.origin = AuthoritativeChangeOrigin.webapi
        result = validator.process_auth(person, None)
        assert not result.is_valid(), result.error_messages

    def test_existing_person_mntner_change(self, prepare_mocks):
        validator, mock_dq, mock_dh = prepare_mocks
        # TEST-MNT is in both maintainers
        person_new = rpsl_object_from_text(SAMPLE_PERSON + "mnt-by: TEST-NEW-MNT\n")
        person_old = rpsl_object_from_text(SAMPLE_PERSON + "mnt-by: TEST-OLD-MNT\n")
        query_results = itertools.cycle(
            [
                [
                    {
                        "object_class": "mntner",
                        "object_text": MNTNER_OBJ_CRYPT_PW.replace("TEST-MNT", "TEST-NEW-MNT"),
                    },
                    {"object_class": "mntner", "object_text": MNTNER_OBJ_MD5_PW.replace("MD5", "nomd5")},
                ],
                [
                    {
                        "object_class": "mntner",
                        "object_text": MNTNER_OBJ_MD5_PW.replace("TEST-MNT", "TEST-OLD-MNT"),
                    },
                ],
            ]
        )
        mock_dh.execute_query = lambda q: next(query_results)

        validator.passwords = [SAMPLE_MNTNER_CRYPT, SAMPLE_MNTNER_MD5]
        result = validator.process_auth(person_new, rpsl_obj_current=person_old)

        assert result.is_valid(), result.error_messages
        assert result.auth_method == AuthMethod.MNTNER_PASSWORD
        assert {m.pk() for m in result.mntners_notify} == {"TEST-MNT", "TEST-OLD-MNT"}

        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT", "TEST-NEW-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-OLD-MNT"},), {}],  # TEST-MNT is cached
        ]

        validator.passwords = [SAMPLE_MNTNER_MD5]
        result = validator.process_auth(person_new, rpsl_obj_current=person_old)
        assert not result.is_valid()
        assert result.error_messages == {
            "Authorisation for person PERSON-TEST failed: "
            "must be authenticated by one of: TEST-MNT, TEST-NEW-MNT"
        }

        validator.passwords = [SAMPLE_MNTNER_CRYPT]
        result = validator.process_auth(person_new, rpsl_obj_current=person_old)
        assert not result.is_valid()
        assert result.error_messages == {
            "Authorisation for person PERSON-TEST failed: "
            "must be authenticated by one of: TEST-MNT, TEST-OLD-MNT"
        }

    def test_valid_new_person_preapproved_mntner(self, prepare_mocks):
        validator, mock_dq, mock_dh = prepare_mocks
        person = rpsl_object_from_text(SAMPLE_PERSON)
        mock_dh.execute_query = lambda q: [
            {"object_class": "mntner", "object_text": SAMPLE_MNTNER},
        ]
        validator.pre_approve([rpsl_object_from_text(SAMPLE_MNTNER)])

        result = validator.process_auth(person, None)
        assert result.is_valid(), result.error_messages
        assert result.auth_method == AuthMethod.MNTNER_IN_SAME_REQUEST
        assert len(result.mntners_notify) == 1
        assert result.mntners_notify[0].pk() == "TEST-MNT"

    def test_create_mntner_requires_override(self, prepare_mocks, config_override):
        validator, mock_dq, mock_dh = prepare_mocks
        mntner = rpsl_object_from_text(SAMPLE_MNTNER)
        mock_dh.execute_query = lambda q: [
            {"object_class": "mntner", "object_text": SAMPLE_MNTNER},
        ]

        validator.passwords = [SAMPLE_MNTNER_MD5]
        result = validator.process_auth(mntner, None)
        assert not result.is_valid()
        assert result.auth_method == AuthMethod.NONE
        assert not result.auth_method
        assert result.error_messages == {"New mntner objects must be added by an administrator."}

        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT", "OTHER1-MNT", "OTHER2-MNT"},), {}],
        ]

        validator.overrides = [VALID_PW]
        config_override(
            {
                "auth": {"override_password": VALID_PW_HASH},
            }
        )

        result = validator.process_auth(mntner, None)
        assert result.is_valid(), result.error_messages
        assert result.auth_method == AuthMethod.OVERRIDE_PASSWORD

    def test_modify_mntner(self, prepare_mocks, config_override):
        validator, mock_dq, mock_dh = prepare_mocks
        mntner = rpsl_object_from_text(SAMPLE_MNTNER)
        mock_dh.execute_query = lambda q: [
            {"object_class": "mntner", "object_text": SAMPLE_MNTNER},
        ]

        # This counts as submitting all new hashes.
        validator.passwords = [SAMPLE_MNTNER_MD5]
        result = validator.process_auth(mntner, mntner)
        assert result.is_valid()
        assert not result.info_messages

        # This counts as submitting all new hashes, but not matching any password
        new_mntner = rpsl_object_from_text(MNTNER_OBJ_CRYPT_PW.replace("CRYPT", ""))
        validator.passwords = [SAMPLE_MNTNER_MD5]
        result = validator.process_auth(new_mntner, mntner)
        assert not result.is_valid()
        assert result.error_messages == {"Authorisation failed for the auth methods on this mntner object."}

        # This counts as submitting all dummy hashes.
        mntner_no_auth_hashes = remove_auth_hashes(SAMPLE_MNTNER)
        new_mntner = rpsl_object_from_text(mntner_no_auth_hashes)
        result = validator.process_auth(new_mntner, mntner)
        assert result.is_valid()
        assert not new_mntner.has_dummy_auth_value()
        assert result.info_messages == {
            "As you submitted dummy hash values, all password hashes on this "
            "object were replaced with a new BCRYPT-PW hash of the password you "
            "provided for authentication."
        }

        # # This is a multi password submission with dummy hashes which is rejected
        validator.passwords = [SAMPLE_MNTNER_MD5, SAMPLE_MNTNER_CRYPT]
        new_mntner = rpsl_object_from_text(mntner_no_auth_hashes)
        result = validator.process_auth(new_mntner, mntner)
        assert not result.is_valid()
        assert not result.info_messages
        assert result.error_messages == {
            "Object submitted with dummy hash values, but multiple or no passwords "
            "submitted. Either submit only full hashes, or a single password."
        }

    def test_modify_mntner_internal_auth(self, prepare_mocks, config_override):
        validator, mock_dq, mock_dh = prepare_mocks
        mntner = rpsl_object_from_text(SAMPLE_MNTNER)
        person = rpsl_object_from_text(SAMPLE_PERSON)
        mock_dh.execute_query = lambda q: []

        mock_mntners = [AuthMntner(rpsl_mntner_pk="TEST-MNT", rpsl_mntner_source="TEST")]

        # Modifying the mntner itself requires user management, this should work
        user = AuthUser(mntners_user_management=mock_mntners)
        validator = AuthValidator(mock_dh, keycert_obj_pk=None, internal_authenticated_user=user)
        result = validator.process_auth(mntner, mntner)
        assert result.is_valid()
        assert result.auth_method == AuthMethod.MNTNER_INTERNAL_AUTH
        assert result.auth_through_mntner == "TEST-MNT"
        assert result.auth_through_internal_mntner == mock_mntners[0]

        # Modifying mntner should fail without user_management
        user = AuthUser(mntners=mock_mntners)
        validator = AuthValidator(mock_dh, keycert_obj_pk=None, internal_authenticated_user=user)
        result = validator.process_auth(mntner, mntner)
        assert not result.is_valid()

        # Modifying different object should succeed without user_management, matching mntner PK
        user = AuthUser(mntners=mock_mntners)
        validator = AuthValidator(mock_dh, keycert_obj_pk=None, internal_authenticated_user=user)
        result = validator.process_auth(person, person)
        assert result.is_valid()

        # Mntner with entirely different PK should not work
        user = AuthUser(mntners=[AuthMntner(rpsl_mntner_pk="INVALID-MNT", rpsl_mntner_source="TEST")])
        validator = AuthValidator(mock_dh, keycert_obj_pk=None, internal_authenticated_user=user)
        result = validator.process_auth(person, person)
        assert not result.is_valid()

    def test_related_route_exact_inetnum(self, prepare_mocks, config_override):
        validator, mock_dq, mock_dh = prepare_mocks
        route = rpsl_object_from_text(SAMPLE_ROUTE)
        query_results = itertools.cycle(
            [
                [{"object_text": MNTNER_OBJ_CRYPT_PW}],  # mntner for object
                [
                    {
                        # attempt to look for exact inetnum
                        "object_class": "inetnum",
                        "rpsl_pk": "192.0.2.0-192.0.2.255",
                        "parsed_data": {"mnt-by": ["RELATED-MNT"]},
                    }
                ],
                [{"object_text": MNTNER_OBJ_MD5_PW}],  # related mntner retrieval
            ]
        )
        mock_dh.execute_query = lambda q: next(query_results)

        validator.passwords = [SAMPLE_MNTNER_MD5, SAMPLE_MNTNER_CRYPT]
        result = validator.process_auth(route, None)
        assert result.is_valid()
        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
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

        validator = AuthValidator(mock_dh, None)
        validator.passwords = [SAMPLE_MNTNER_CRYPT]  # related only has MD5, so this is invalid
        result = validator.process_auth(route, None)
        assert not result.is_valid()
        assert result.error_messages == {
            "Authorisation for route 192.0.2.0/24AS65537 failed: must be authenticated by one of: "
            "RELATED-MNT - from parent inetnum 192.0.2.0-192.0.2.255"
        }

        config_override(
            {
                "auth": {
                    "authenticate_parents_route_creation": False,
                    "password_hashers": {"crypt-pw": "enabled"},
                }
            }
        )
        result = validator.process_auth(route, None)
        assert result.is_valid()
        config_override({"auth": {"password_hashers": {"crypt-pw": "enabled"}}})

        result = validator.process_auth(route, route)
        assert result.is_valid()

    def test_related_route_less_specific_inetnum(self, prepare_mocks):
        validator, mock_dq, mock_dh = prepare_mocks
        route = rpsl_object_from_text(SAMPLE_ROUTE)
        query_results = itertools.cycle(
            [
                [{"object_text": MNTNER_OBJ_CRYPT_PW}],  # mntner for object
                [],  # attempt to look for exact inetnum
                [
                    {
                        # attempt to look for one level less specific inetnum
                        "object_class": "inetnum",
                        "rpsl_pk": "192.0.2.0-192.0.2.255",
                        "parsed_data": {"mnt-by": ["RELATED-MNT"]},
                    }
                ],
                [{"object_text": MNTNER_OBJ_MD5_PW}],  # related mntner retrieval
            ]
        )
        mock_dh.execute_query = lambda q: next(query_results)

        validator.passwords = [SAMPLE_MNTNER_MD5, SAMPLE_MNTNER_CRYPT]
        result = validator.process_auth(route, None)
        assert result.is_valid()
        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
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

        validator = AuthValidator(mock_dh, None)
        validator.passwords = [SAMPLE_MNTNER_CRYPT]  # related only has MD5, so this is invalid
        result = validator.process_auth(route, None)
        assert not result.is_valid()
        assert result.error_messages == {
            "Authorisation for route 192.0.2.0/24AS65537 failed: must be authenticated by one of: "
            "RELATED-MNT - from parent inetnum 192.0.2.0-192.0.2.255"
        }

    def test_related_route_less_specific_route(self, prepare_mocks):
        validator, mock_dq, mock_dh = prepare_mocks
        route = rpsl_object_from_text(SAMPLE_ROUTE)
        query_results = itertools.cycle(
            [
                [{"object_text": MNTNER_OBJ_CRYPT_PW}],  # mntner for object
                [],  # attempt to look for exact inetnum
                [],  # attempt to look for one level less specific inetnum
                [
                    {
                        # attempt to look for less specific route
                        "object_class": "route",
                        "rpsl_pk": "192.0.2.0/24AS65537",
                        "parsed_data": {"mnt-by": ["RELATED-MNT"]},
                    }
                ],
                [{"object_text": MNTNER_OBJ_MD5_PW}],  # related mntner retrieval
            ]
        )
        mock_dh.execute_query = lambda q: next(query_results)

        validator.passwords = [SAMPLE_MNTNER_MD5, SAMPLE_MNTNER_CRYPT]
        result = validator.process_auth(route, None)
        assert result.is_valid()

        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
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

        validator = AuthValidator(mock_dh, None)
        validator.passwords = [SAMPLE_MNTNER_CRYPT]  # related only has MD5, so this is invalid
        result = validator.process_auth(route, None)
        assert not result.is_valid()
        assert result.error_messages == {
            "Authorisation for route 192.0.2.0/24AS65537 failed: must be authenticated by one of: "
            "RELATED-MNT - from parent route 192.0.2.0/24AS65537"
        }

    def test_related_route_no_match_v6(self, prepare_mocks):
        validator, mock_dq, mock_dh = prepare_mocks
        route = rpsl_object_from_text(SAMPLE_ROUTE6)
        query_results = itertools.cycle(
            [
                [{"object_text": SAMPLE_MNTNER}],  # mntner for object
                [],  # attempt to look for exact inetnum
                [],  # attempt to look for one level less specific inetnum
                [],  # attempt to look for less specific route
            ]
        )
        mock_dh.execute_query = lambda q: next(query_results)

        validator.passwords = [SAMPLE_MNTNER_MD5]
        result = validator.process_auth(route, None)
        assert result.is_valid()

        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inet6num"],), {}],
            ["first_only", (), {}],
            ["ip_exact", ("2001:db8::/48",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["inet6num"],), {}],
            ["first_only", (), {}],
            ["ip_less_specific_one_level", ("2001:db8::/48",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["route6"],), {}],
            ["first_only", (), {}],
            ["ip_less_specific_one_level", ("2001:db8::/48",), {}],
        ]

    def test_as_set_autnum_disabled(self, prepare_mocks, config_override):
        config_override(
            {
                "auth": {
                    "set_creation": {"as-set": {"autnum_authentication": "disabled"}},
                    "password_hashers": {"crypt-pw": "enabled"},
                },
            }
        )
        validator, mock_dq, mock_dh = prepare_mocks
        as_set = rpsl_object_from_text(SAMPLE_AS_SET)
        assert as_set.clean_for_create()  # fill pk_asn_segment
        mock_dh.execute_query = lambda q: [
            {"object_text": MNTNER_OBJ_CRYPT_PW},  # mntner for object
        ]

        validator.passwords = [SAMPLE_MNTNER_MD5, SAMPLE_MNTNER_CRYPT]
        result = validator.process_auth(as_set, None)
        assert result.is_valid()
        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
        ]

    def test_as_set_autnum_opportunistic_exists_default(self, prepare_mocks, config_override):
        config_override({"auth": {"password_hashers": {"crypt-pw": "enabled"}}})
        validator, mock_dq, mock_dh = prepare_mocks
        as_set = rpsl_object_from_text(SAMPLE_AS_SET)
        assert as_set.clean_for_create()  # fill pk_asn_segment
        query_results = itertools.cycle(
            [
                [{"object_text": MNTNER_OBJ_CRYPT_PW}],  # mntner for object
                [
                    {
                        # attempt to look for matching aut-num
                        "object_class": "aut-num",
                        "rpsl_pk": "AS655375",
                        "parsed_data": {"mnt-by": ["RELATED-MNT"]},
                    }
                ],
                [{"object_text": MNTNER_OBJ_MD5_PW}],  # related mntner retrieval
            ]
        )
        mock_dh.execute_query = lambda q: next(query_results)

        validator.passwords = [SAMPLE_MNTNER_MD5, SAMPLE_MNTNER_CRYPT]
        result = validator.process_auth(as_set, None)
        assert result.is_valid()
        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["aut-num"],), {}],
            ["first_only", (), {}],
            ["rpsl_pk", ("AS65537",), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"RELATED-MNT"},), {}],
        ]

        validator = AuthValidator(mock_dh, None)
        validator.passwords = [SAMPLE_MNTNER_CRYPT]  # related only has MD5, so this is invalid
        result = validator.process_auth(as_set, None)
        assert not result.is_valid()
        assert result.error_messages == {
            "Authorisation for as-set AS65537:AS-SETTEST failed: must be authenticated by one of: "
            "RELATED-MNT - from parent aut-num AS655375"
        }

        result = validator.process_auth(as_set, rpsl_obj_current=as_set)
        assert result.is_valid()

        config_override(
            {
                "auth": {
                    "set_creation": {"as-set": {"autnum_authentication": "disabled"}},
                    "password_hashers": {"crypt-pw": "enabled"},
                },
            }
        )
        result = validator.process_auth(as_set, None)
        assert result.is_valid()

    def test_as_set_autnum_opportunistic_does_not_exist(self, prepare_mocks, config_override):
        config_override(
            {
                "auth": {
                    "set_creation": {
                        AUTH_SET_CREATION_COMMON_KEY: {"autnum_authentication": "opportunistic"}
                    },
                    "password_hashers": {"crypt-pw": "enabled"},
                }
            }
        )
        validator, mock_dq, mock_dh = prepare_mocks
        as_set = rpsl_object_from_text(SAMPLE_AS_SET)
        assert as_set.clean_for_create()  # fill pk_first_segment
        query_results = itertools.cycle(
            [
                [{"object_text": MNTNER_OBJ_CRYPT_PW}],  # mntner for object
                [],  # attempt to look for matching aut-num
            ]
        )
        mock_dh.execute_query = lambda q: next(query_results)

        validator.passwords = [SAMPLE_MNTNER_MD5, SAMPLE_MNTNER_CRYPT]
        result = validator.process_auth(as_set, None)
        assert result.is_valid()
        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
            ["sources", (["TEST"],), {}],
            ["object_classes", (["aut-num"],), {}],
            ["first_only", (), {}],
            ["rpsl_pk", ("AS65537",), {}],
        ]

    def test_as_set_autnum_required_does_not_exist(self, prepare_mocks, config_override):
        config_override(
            {
                "auth": {
                    "set_creation": {AUTH_SET_CREATION_COMMON_KEY: {"autnum_authentication": "required"}},
                    "password_hashers": {"crypt-pw": "enabled"},
                }
            }
        )
        validator, mock_dq, mock_dh = prepare_mocks
        as_set = rpsl_object_from_text(SAMPLE_AS_SET)
        assert as_set.clean_for_create()  # fill pk_first_segment
        query_results = itertools.cycle(
            [
                [{"object_text": MNTNER_OBJ_CRYPT_PW}],  # mntner for object
                [],  # attempt to look for matching aut-num
            ]
        )
        mock_dh.execute_query = lambda q: next(query_results)

        validator.passwords = [SAMPLE_MNTNER_MD5, SAMPLE_MNTNER_CRYPT]
        result = validator.process_auth(as_set, None)
        assert not result.is_valid()
        assert result.error_messages == {
            "Creating this object requires an aut-num for AS65537 to exist.",
        }

    def test_filter_set_autnum_required_no_prefix(self, prepare_mocks, config_override):
        config_override(
            {
                "auth": {
                    "set_creation": {
                        AUTH_SET_CREATION_COMMON_KEY: {
                            "autnum_authentication": "required",
                            "prefix_required": False,
                        }
                    },
                    "password_hashers": {"crypt-pw": "enabled"},
                }
            }
        )
        validator, mock_dq, mock_dh = prepare_mocks
        filter_set = rpsl_object_from_text(SAMPLE_FILTER_SET)
        assert filter_set.clean_for_create()
        mock_dh.execute_query = lambda q: [
            {"object_text": MNTNER_OBJ_CRYPT_PW},  # mntner for object
        ]

        validator.passwords = [SAMPLE_MNTNER_MD5, SAMPLE_MNTNER_CRYPT]
        result = validator.process_auth(filter_set, None)
        assert result.is_valid()
        assert flatten_mock_calls(mock_dq, flatten_objects=True) == [
            ["sources", (["TEST"],), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", ({"TEST-MNT"},), {}],
        ]


class TestRulesValidator:
    @pytest.fixture()
    def prepare_mocks(self, monkeypatch):
        mock_dh = Mock(spec=DatabaseHandler)
        mock_dsq = Mock(spec=RPSLDatabaseSuspendedQuery)
        monkeypatch.setattr("irrd.updates.validators.RPSLDatabaseSuspendedQuery", mock_dsq)

        validator = RulesValidator(mock_dh)
        yield validator, mock_dsq, mock_dh

    def test_check_suspended_mntner_with_same_pk(self, prepare_mocks, monkeypatch):
        validator, mock_dsq, mock_dh = prepare_mocks
        monkeypatch.setattr(
            "irrd.updates.validators.RulesValidator._check_mntner_migrated", lambda slf, pk, source: False
        )

        person = rpsl_object_from_text(SAMPLE_PERSON)
        mntner = rpsl_object_from_text(SAMPLE_MNTNER)

        mock_dh.execute_query.return_value = []
        assert validator.validate(person, UpdateRequestType.CREATE).is_valid()
        assert validator.validate(mntner, UpdateRequestType.MODIFY).is_valid()
        assert validator.validate(mntner, UpdateRequestType.DELETE).is_valid()
        assert validator.validate(mntner, UpdateRequestType.CREATE).is_valid()

        validator._check_suspended_mntner_with_same_pk.cache_clear()
        mock_dh.execute_query.return_value = [
            {"rpsl_pk": "conflicting entry which is only counted, not used"}
        ]
        assert validator.validate(person, UpdateRequestType.CREATE).is_valid()
        assert validator.validate(mntner, UpdateRequestType.MODIFY).is_valid()
        assert validator.validate(mntner, UpdateRequestType.DELETE).is_valid()
        invalid = validator.validate(mntner, UpdateRequestType.CREATE)
        assert not invalid.is_valid()
        assert invalid.error_messages == {
            "A suspended mntner with primary key TEST-MNT already exists for TEST"
        }

        assert flatten_mock_calls(mock_dsq, flatten_objects=True) == [
            ["", (), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["sources", (["TEST"],), {}],
            ["first_only", (), {}],
            ["", (), {}],
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["sources", (["TEST"],), {}],
            ["first_only", (), {}],
        ]

    def test_check_mntner_migrated(self, prepare_mocks, monkeypatch):
        validator, mock_dsq, mock_dh = prepare_mocks
        mock_dh._connection = None
        monkeypatch.setattr(
            "irrd.updates.validators.RulesValidator._check_suspended_mntner_with_same_pk",
            lambda slf, pk, source: False,
        )
        mock_sa_session = UnifiedAlchemyMagicMock(
            data=[
                (
                    [
                        mock.call.query(AuthMntner),
                        mock.call.filter(
                            AuthMntner.rpsl_mntner_pk == "TEST-MNT", AuthMntner.rpsl_mntner_source == "TEST"
                        ),
                    ],
                    [AuthMntner(rpsl_mntner_pk="TEST-MNT")],
                )
            ]
        )
        monkeypatch.setattr("irrd.updates.validators.saorm.Session", lambda bind: mock_sa_session)

        person = rpsl_object_from_text(SAMPLE_PERSON)
        mntner = rpsl_object_from_text(SAMPLE_MNTNER)
        mntner_internal = rpsl_object_from_text(SAMPLE_MNTNER + f"auth: {RPSL_MNTNER_AUTH_INTERNAL}")

        mock_sa_session.count = lambda: False
        assert validator.validate(person, UpdateRequestType.CREATE).is_valid()
        assert validator.validate(mntner, UpdateRequestType.MODIFY).is_valid()

        mock_sa_session.filter.assert_has_calls(
            [
                mock.call(AuthMntner.rpsl_mntner_pk == "TEST-MNT", AuthMntner.rpsl_mntner_source == "TEST"),
            ]
        )

        validator._check_mntner_migrated.cache_clear()
        mock_sa_session.count = lambda: True
        assert validator.validate(person, UpdateRequestType.CREATE).is_valid()
        invalid = validator.validate(mntner, UpdateRequestType.CREATE)
        assert not invalid.is_valid()
        assert invalid.error_messages == {
            "This maintainer is migrated and must include the IRRD-INTERNAL-AUTH method."
        }

        validator._check_mntner_migrated.cache_clear()
        mock_sa_session.count = lambda: True
        assert validator.validate(mntner_internal, UpdateRequestType.MODIFY).is_valid()

        validator._check_mntner_migrated.cache_clear()
        mock_sa_session.count = lambda: False
        assert validator.validate(person, UpdateRequestType.CREATE).is_valid()
        invalid = validator.validate(mntner_internal, UpdateRequestType.CREATE)
        assert not invalid.is_valid()
        assert invalid.error_messages == {
            "This maintainer is not migrated, and therefore can not use the IRRD-INTERNAL-AUTH method."
        }
