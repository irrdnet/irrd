import uuid
from datetime import datetime, timezone
from unittest.mock import create_autospec

import pytest
from starlette.testclient import TestClient

from irrd.updates.handler import ChangeSubmissionHandler
from irrd.utils.rpsl_samples import SAMPLE_MNTNER
from irrd.webui import datetime_format

from ...rpsl.rpsl_objects import rpsl_object_from_text
from ...server.http.app import app
from ...storage.database_handler import DatabaseHandler
from ...storage.models import JournalEntryOrigin
from ...updates.parser_state import UpdateRequestType
from ...utils.factories import AuthApiTokenFactory, AuthMntnerFactory, ChangeLogFactory
from .conftest import WebRequestTest, create_permission


def test_datetime_format():
    date = datetime(2022, 3, 14, 12, 34, 56, tzinfo=timezone.utc)
    assert datetime_format(date) == "2022-03-14 12:34"


class TestIndex(WebRequestTest):
    url = "/ui/"
    requires_login = False
    requires_mfa = False

    def test_index(self, test_client):
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert response.context["auth_sources"] == ["TEST"]
        assert response.context["mirrored_sources"] == ["MIRROR"]


class TestUserDetail(WebRequestTest):
    url = "/ui/user/"

    def test_get(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url)
        assert response.status_code == 200


class TestMaintainedObjects(WebRequestTest):
    url = "/ui/maintained-objects"

    def test_get_no_user_mntners(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert response.context["objects"] is None

    def test_get(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        create_permission(session_provider, user)
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert len(response.context["objects"]) == 3
        displayed_pks = {obj["rpsl_pk"] for obj in response.context["objects"]}
        assert displayed_pks == {"ROLE-TEST", "TEST-MNT", "PERSON-TEST"}


class TestRpslDetail(WebRequestTest):
    url = "/ui/rpsl/TEST/mntner/TEST-MNT"
    requires_login = False
    requires_mfa = False

    def test_valid_mntner_logged_in_mfa_complete_user_management(
        self, irrd_db_session_with_user, test_client
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "DUMMYVALUE" not in response.text.upper()

    def test_valid_mntner_not_logged_in(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "DUMMYVALUE" in response.text.upper()

    def test_valid_mntner_logged_in_mfa_incomplete_user_management(
        self, irrd_db_session_with_user, test_client
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        # No MFA
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "DUMMYVALUE" in response.text.upper()

    def test_valid_mntner_logged_in_mfa_complete_no_user_management(
        self, irrd_db_session_with_user, test_client
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user, user_management=False)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "DUMMYVALUE" in response.text.upper()

    def test_object_not_exists(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        create_permission(session_provider, user)

        response = test_client.get(self.url + "-none")
        assert response.status_code == 200
        assert "TEST-MNT" not in response.text


@pytest.fixture()
def mock_change_submission_handler(monkeypatch):
    mock_csh = create_autospec(ChangeSubmissionHandler)
    monkeypatch.setattr("irrd.webui.endpoints.ChangeSubmissionHandler", mock_csh)
    return mock_csh


class TestRpslUpdateNoInitial(WebRequestTest):
    url = "/ui/rpsl/update/"
    requires_login = False
    requires_mfa = False

    def test_valid_mntner_logged_in_mfa_complete_no_user_management(
        self,
        irrd_db_session_with_user,
        test_client,
        mock_change_submission_handler,
        tmp_gpg_dir,
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user, user_management=False)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "(you can not update this mntner itself)" in response.text

    def test_valid_mntner_logged_in_mfa_complete_user_management(
        self,
        irrd_db_session_with_user,
        test_client,
        mock_change_submission_handler,
        tmp_gpg_dir,
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "(you can not update this mntner itself)" not in response.text

        response = test_client.post(self.url, data={"data": SAMPLE_MNTNER})
        assert response.status_code == 200
        assert mock_change_submission_handler.mock_calls[1][0] == "().load_text_blob"
        mock_handler_kwargs = mock_change_submission_handler.mock_calls[1][2]
        assert mock_handler_kwargs["object_texts_blob"] == SAMPLE_MNTNER
        assert mock_handler_kwargs["internal_authenticated_user"].pk == user.pk

    def test_valid_mntner_logged_in_mfa_complete_user_management_no_csrf(
        self,
        irrd_db_session_with_user,
        test_client,
        mock_change_submission_handler,
        tmp_gpg_dir,
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user)

        app.force_csrf_in_testing = True
        with TestClient(app, cookies=test_client.cookies) as client_csrf:
            app.force_csrf_in_testing = False
            client_csrf.cookies = test_client.cookies
            response = client_csrf.post(self.url, data={"data": SAMPLE_MNTNER})
            assert response.status_code == 200
            assert mock_change_submission_handler.mock_calls[1][0] == "().load_text_blob"
            mock_handler_kwargs = mock_change_submission_handler.mock_calls[1][2]
            assert mock_handler_kwargs["object_texts_blob"] == SAMPLE_MNTNER
            assert mock_handler_kwargs["internal_authenticated_user"] is None

    def test_valid_mntner_logged_in_mfa_incomplete_user_management(
        self,
        irrd_db_session_with_user,
        test_client,
        mock_change_submission_handler,
        tmp_gpg_dir,
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" not in response.text

        response = test_client.post(self.url, data={"data": SAMPLE_MNTNER})
        assert response.status_code == 200
        assert mock_change_submission_handler.mock_calls[1][0] == "().load_text_blob"
        mock_handler_kwargs = mock_change_submission_handler.mock_calls[1][2]
        assert mock_handler_kwargs["object_texts_blob"] == SAMPLE_MNTNER
        assert mock_handler_kwargs["internal_authenticated_user"] is None

    def test_valid_mntner_not_logged_in(
        self,
        irrd_db_session_with_user,
        test_client,
        mock_change_submission_handler,
        tmp_gpg_dir,
    ):
        session_provider, user = irrd_db_session_with_user
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" not in response.text

        response = test_client.post(self.url, data={"data": SAMPLE_MNTNER})
        assert response.status_code == 200
        assert mock_change_submission_handler.mock_calls[1][0] == "().load_text_blob"
        mock_handler_kwargs = mock_change_submission_handler.mock_calls[1][2]
        assert mock_handler_kwargs["object_texts_blob"] == SAMPLE_MNTNER
        assert mock_handler_kwargs["internal_authenticated_user"] is None


class TestRpslUpdateWithInitial(WebRequestTest):
    url = "/ui/rpsl/update/TEST/mntner/TEST-MNT/"
    requires_login = False
    requires_mfa = False

    def test_valid_mntner_logged_in_mfa_complete_no_user_management(
        self,
        irrd_db_session_with_user,
        test_client,
        tmp_gpg_dir,
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user, user_management=False)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "(you can not update this mntner itself)" in response.text
        assert "DUMMYVALUE" in response.text.upper()

    def test_valid_mntner_logged_in_mfa_complete_user_management(
        self,
        irrd_db_session_with_user,
        test_client,
        tmp_gpg_dir,
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "(you can not update this mntner itself)" not in response.text
        assert "DUMMYVALUE" not in response.text.upper()

    def test_valid_mntner_logged_in_mfa_incomplete_user_management(
        self,
        irrd_db_session_with_user,
        test_client,
        tmp_gpg_dir,
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "DUMMYVALUE" in response.text.upper()

    def test_valid_mntner_not_logged_in(self, irrd_db_session_with_user, test_client, tmp_gpg_dir):
        session_provider, user = irrd_db_session_with_user
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "DUMMYVALUE" in response.text.upper()


class TestChangeLogMntner(WebRequestTest):
    url_template = "/ui/change-log/{uuid}/"

    def pre_login(self, session_provider, user, user_management=True):
        self.permission = create_permission(session_provider, user, user_management=user_management)
        self.url = self.url_template.format(uuid=self.permission.mntner.pk)

    def test_render(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        ChangeLogFactory(
            auth_through_mntner_id=str(self.permission.mntner.pk),
            auth_change_descr="auth change descr",
        )
        api_token = AuthApiTokenFactory()
        ChangeLogFactory(
            auth_through_rpsl_mntner_pk=str(self.permission.mntner.rpsl_mntner_pk),
            rpsl_target_pk="TARGET-PK",
            rpsl_target_object_class="person",
            rpsl_target_source=self.permission.mntner.rpsl_mntner_source,
            auth_by_api_key_id_fixed=str(api_token.pk),
            from_ip="127.0.0.1",
            rpsl_target_request_type=UpdateRequestType.MODIFY,
        )

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert self.permission.mntner.rpsl_mntner_pk in response.text
        assert "auth change descr" in response.text
        assert str(api_token.pk) in response.text
        assert "127.0.0.1" in response.text
        assert "modify of person TARGET-PK" in response.text

    def test_no_entries(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert self.permission.mntner.rpsl_mntner_pk in response.text

    def test_no_permissions(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)
        session_provider.session.delete(self.permission)
        session_provider.session.commit()

        response = test_client.get(self.url)
        assert response.status_code == 404

    def test_wrong_permissions(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)
        session_provider.session.delete(self.permission)
        session_provider.session.commit()

        # Creating a second mntner with separate permissions is kind of tricky
        dh = DatabaseHandler()
        dh.upsert_rpsl_object(
            rpsl_object_from_text(SAMPLE_MNTNER.replace("TEST", "TEST2")), origin=JournalEntryOrigin.unknown
        )
        dh.commit()
        dh.close()
        create_permission(
            session_provider, user, user_management=True, mntner=AuthMntnerFactory(rpsl_mntner_source="TEST2")
        )

        response = test_client.get(self.url)
        assert response.status_code == 404


class TestChangeLogEntry(WebRequestTest):
    url_template = "/ui/change-log/entry/{uuid}/"

    def pre_login(self, session_provider, user, user_management=True):
        self.permission = create_permission(session_provider, user, user_management=user_management)
        self.change_log = ChangeLogFactory(
            auth_through_mntner_id=str(self.permission.mntner.pk),
            auth_change_descr="auth change descr",
        )
        self.url = self.url_template.format(uuid=self.change_log.pk)

    def test_render(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "auth change descr" in response.text

    def test_render_rpsl_change(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)

        api_token = AuthApiTokenFactory()
        change_log = ChangeLogFactory(
            auth_through_rpsl_mntner_pk=str(self.permission.mntner.rpsl_mntner_pk),
            rpsl_target_pk="TARGET-PK",
            rpsl_target_object_class="person",
            rpsl_target_source=self.permission.mntner.rpsl_mntner_source,
            auth_by_api_key_id_fixed=str(api_token.pk),
            from_ip="127.0.0.1",
            rpsl_target_request_type=UpdateRequestType.MODIFY,
        )
        self.url = self.url_template.format(uuid=change_log.pk)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert str(api_token.pk) in response.text
        assert "127.0.0.1" in response.text
        assert "modify of person TARGET-PK" in response.text

    def test_no_permissions(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)
        session_provider.session.delete(self.permission)
        session_provider.session.commit()

        response = test_client.get(self.url)
        assert response.status_code == 404

    def test_object_not_exists(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url_template.format(uuid=uuid.uuid4()))
        assert response.status_code == 404
