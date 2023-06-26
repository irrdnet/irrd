import uuid

from irrd.conf import RPSL_MNTNER_AUTH_INTERNAL
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.storage.models import AuthApiToken, AuthPermission
from irrd.utils.factories import (
    SAMPLE_USER_PASSWORD,
    AuthApiTokenFactory,
    AuthUserFactory,
)
from irrd.utils.rpsl_samples import SAMPLE_MNTNER, SAMPLE_MNTNER_BCRYPT

from .conftest import WebRequestTest, create_permission


class TestApiTokenAdd(WebRequestTest):
    url_template = "/ui/api_token/add/{uuid}/"

    def pre_login(self, session_provider, user, user_management=True):
        self.permission = create_permission(session_provider, user, user_management=user_management)
        self.url = self.url_template.format(uuid=self.permission.mntner.pk)

    def test_render_form(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text

    def test_valid_new_token(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        api_token_name = "token name"
        response = test_client.post(
            self.url,
            data={
                "name": api_token_name,
                "enabled_webapi": "1",
                "ip_restriction": " 192.0.2.1 ,192.0.02.0/24",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        new_api_token = session_provider.run_sync(session_provider.session.query(AuthApiToken).one)
        assert new_api_token.token
        assert new_api_token.creator == user
        assert new_api_token.name == api_token_name
        assert new_api_token.enabled_webapi
        assert new_api_token.ip_restriction == "192.0.2.1,192.0.2.0/24"
        assert not new_api_token.enabled_email
        assert len(smtpd.messages) == 3
        assert new_api_token.name in smtpd.messages[1].as_string()

    def test_invalid_cidr_range(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        api_token_name = "token name"
        response = test_client.post(
            self.url,
            data={"name": api_token_name, "ip_restriction": "192.0.2.1.1"},
            follow_redirects=False,
        )
        assert response.status_code == 200

        new_api_token = session_provider.run_sync(session_provider.session.query(AuthApiToken).one)
        assert not new_api_token
        assert "Invalid IP" in response.text

    def test_invalid_ip_restriction_with_email(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        api_token_name = "token name"
        response = test_client.post(
            self.url,
            data={
                "name": api_token_name,
                "enabled_email": "1",
                "ip_restriction": " 192.0.2.1 ,192.0.02.0/24",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200

        new_api_token = session_provider.run_sync(session_provider.session.query(AuthApiToken).one)
        assert not new_api_token
        assert "can not be combined" in response.text

    def test_object_not_exists(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url_template.format(uuid=uuid.uuid4()))
        assert response.status_code == 404


class TestApiTokenEdit(WebRequestTest):
    url_template = "/ui/api_token/edit/{uuid}/"

    def pre_login(self, session_provider, user, user_management=True):
        self.permission = create_permission(session_provider, user, user_management=user_management)
        self.api_token = AuthApiTokenFactory(
            mntner_id=str(self.permission.mntner.pk), creator_id=str(user.pk)
        )
        self.url = self.url_template.format(uuid=self.api_token.pk)

    def test_render_form(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text

    def test_valid_edit(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        api_token_name = "new name"
        old_api_token_token = self.api_token.token
        response = test_client.post(
            self.url,
            data={"name": api_token_name, "enabled_email": "1"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        session_provider.session.refresh(self.api_token)
        assert self.api_token.token == old_api_token_token
        assert self.api_token.creator == user
        assert self.api_token.name == api_token_name
        assert not self.api_token.enabled_webapi
        assert self.api_token.enabled_email

    def test_object_not_exists(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url_template.format(uuid=uuid.uuid4()))
        assert response.status_code == 404


class TestApiTokenDelete(WebRequestTest):
    url_template = "/ui/api_token/delete/{uuid}/"

    def pre_login(self, session_provider, user, user_management=True):
        self.permission = create_permission(session_provider, user, user_management=user_management)
        self.api_token = AuthApiTokenFactory(
            mntner_id=str(self.permission.mntner.pk), creator_id=str(user.pk)
        )
        self.url = self.url_template.format(uuid=self.api_token.pk)

    def test_render_form(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text

    def test_valid_delete(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)
        api_token_name = self.api_token.name

        response = test_client.post(
            self.url,
            follow_redirects=False,
        )
        assert response.status_code == 302

        deleted_api_token = session_provider.run_sync(session_provider.session.query(AuthApiToken).one)
        assert deleted_api_token is None

        assert len(smtpd.messages) == 3
        assert api_token_name in smtpd.messages[1].as_string()

    def test_object_not_exists(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url_template.format(uuid=uuid.uuid4()))
        assert response.status_code == 404


class TestPermissionAdd(WebRequestTest):
    url_template = "/ui/permission/add/{uuid}/"

    def pre_login(self, session_provider, user, user_management=True):
        self.permission = create_permission(session_provider, user, user_management=user_management)
        self.url = self.url_template.format(uuid=self.permission.mntner.pk)

    def test_render_form(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text

    def test_valid_without_new_user_management(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        user2 = AuthUserFactory()
        response = test_client.post(
            self.url,
            data={"new_user_email": user2.email, "confirm": "1", "current_password": SAMPLE_USER_PASSWORD},
            follow_redirects=False,
        )
        assert response.status_code == 302

        new_permission = session_provider.run_sync(
            session_provider.session.query(AuthPermission).filter(AuthPermission.user_id != str(user.pk)).one
        )
        assert new_permission.user == user2
        assert new_permission.mntner == self.permission.mntner
        assert not new_permission.user_management
        assert len(smtpd.messages) == 3
        assert user2.email in smtpd.messages[1].as_string()

        # Try a second time with the same user
        response = test_client.post(
            self.url,
            data={"new_user_email": user2.email, "confirm": "1", "current_password": SAMPLE_USER_PASSWORD},
            follow_redirects=False,
        )
        assert response.status_code == 200
        permission_count = session_provider.run_sync(session_provider.session.query(AuthPermission).count)
        assert permission_count == 2

    def test_valid_with_new_user_management(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        user2 = AuthUserFactory()
        response = test_client.post(
            self.url,
            data={
                "new_user_email": user2.email,
                "confirm": "1",
                "user_management": "1",
                "current_password": SAMPLE_USER_PASSWORD,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        new_permission = session_provider.run_sync(
            session_provider.session.query(AuthPermission).filter(AuthPermission.user_id != str(user.pk)).one
        )
        assert new_permission.user == user2
        assert new_permission.mntner == self.permission.mntner
        assert new_permission.user_management

        assert len(smtpd.messages) == 3
        assert user2.email in smtpd.messages[1].as_string()

    def test_invalid_incorrect_current_password(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        user2 = AuthUserFactory()
        response = test_client.post(
            self.url,
            data={
                "new_user_email": user2.email,
                "confirm": "1",
                "user_management": "1",
                "current_password": "incorrect",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200

        new_permission = session_provider.run_sync(
            session_provider.session.query(AuthPermission).filter(AuthPermission.user_id != str(user.pk)).one
        )
        assert new_permission is None

    def test_invalid_new_user_does_not_exist(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url,
            data={
                "new_user_email": "doesnotexist@example.com",
                "confirm": "1",
                "user_management": "1",
                "current_password": SAMPLE_USER_PASSWORD,
            },
            follow_redirects=False,
        )
        assert response.status_code == 200

        new_permission = session_provider.run_sync(
            session_provider.session.query(AuthPermission).filter(AuthPermission.user_id != str(user.pk)).one
        )
        assert new_permission is None

    def test_missing_user_management_on_mntner(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user, user_management=False)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 404

    def test_object_not_exists(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url_template.format(uuid=uuid.uuid4()))
        assert response.status_code == 404


class TestPermissionDelete(WebRequestTest):
    url_template = "/ui/permission/delete/{uuid}/"

    def pre_login(self, session_provider, user, user_management=True):
        self.permission = create_permission(session_provider, user, user_management=user_management)
        self.user2 = AuthUserFactory()
        self.permission2 = create_permission(
            session_provider, self.user2, mntner=self.permission.mntner, user_management=user_management
        )
        self.url = self.url_template.format(uuid=self.permission2.pk)

    def test_render_form(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text

    def test_valid_other_delete(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url,
            data={
                "confirm": "1",
                "current_password": SAMPLE_USER_PASSWORD,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        deleted_permission = session_provider.run_sync(
            session_provider.session.query(AuthPermission).filter(AuthPermission.user_id != str(user.pk)).one
        )
        assert deleted_permission is None

        assert len(smtpd.messages) == 3
        assert self.user2.email in smtpd.messages[1].as_string()

    def test_valid_self_delete(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            f"/ui/permission/delete/{self.permission.pk}/",
            data={
                "confirm": "1",
                "confirm_self_delete": "1",
                "current_password": SAMPLE_USER_PASSWORD,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        deleted_permission = session_provider.run_sync(
            session_provider.session.query(AuthPermission).filter(AuthPermission.user_id == str(user.pk)).one
        )
        assert deleted_permission is None

        assert len(smtpd.messages) == 3
        assert user.email in smtpd.messages[1].as_string()

    def test_invalid_refuse_last_delete(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)
        session_provider.session.delete(self.permission2)
        session_provider.session.commit()

        response = test_client.post(
            f"/ui/permission/delete/{self.permission.pk}/",
            data={
                "confirm": "1",
                "current_password": SAMPLE_USER_PASSWORD,
            },
            follow_redirects=False,
        )
        assert response.status_code == 200

        deleted_permission = session_provider.run_sync(
            session_provider.session.query(AuthPermission).filter(AuthPermission.user_id == str(user.pk)).one
        )
        assert deleted_permission is not None

    def test_invalid_incorrect_current_password(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url,
            data={
                "confirm": "1",
                "current_password": "incorrect",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200

        deleted_permission = session_provider.run_sync(
            session_provider.session.query(AuthPermission).filter(AuthPermission.user_id != str(user.pk)).one
        )
        assert deleted_permission is not None

    def test_missing_user_management_on_mntner(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user, user_management=False)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 404

    def test_object_not_exists(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url_template.format(uuid=uuid.uuid4()))
        assert response.status_code == 404


class TestMntnerMigrateInitiate(WebRequestTest):
    url = "/ui/migrate-mntner/"

    def pre_login(self, session_provider, user):
        self.mntner_obj = rpsl_object_from_text(SAMPLE_MNTNER)

    def test_render_form(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200

    def test_render_form_disabled(self, test_client, irrd_db_session_with_user, config_override):
        config_override(
            {
                "server": {"http": {"url": "http://testserver/"}},
                "secret_key": "s",
                "auth": {"irrd_internal_migration_enabled": False},
            }
        )
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "mntners is not enabled on this instance" in response.text

    def test_valid_submit(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url,
            data={
                "mntner_key": self.mntner_obj.pk(),
                "mntner_source": self.mntner_obj.source(),
                "mntner_password": SAMPLE_MNTNER_BCRYPT,
                "confirm": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        new_permission = session_provider.run_sync(session_provider.session.query(AuthPermission).one)
        assert new_permission.mntner.rpsl_mntner_pk == self.mntner_obj.pk()
        assert new_permission.user == user
        assert new_permission.user_management

        assert len(smtpd.messages) == 1
        assert "email@example.com" == smtpd.messages[0]["To"]
        assert self.mntner_obj.pk() in smtpd.messages[0].as_string()
        assert new_permission.mntner.migration_token in smtpd.messages[0].as_string()

    def test_invalid_password(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url,
            data={
                "mntner_key": self.mntner_obj.pk(),
                "mntner_source": self.mntner_obj.source(),
                "mntner_password": SAMPLE_MNTNER_BCRYPT + "-invalid",
                "confirm": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "Invalid password" in response.text

        new_permission = session_provider.run_sync(session_provider.session.query(AuthPermission).one)
        assert not new_permission

    def test_already_migrated(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        create_permission(session_provider, user)
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url,
            data={
                "mntner_key": self.mntner_obj.pk(),
                "mntner_source": self.mntner_obj.source(),
                "mntner_password": SAMPLE_MNTNER_BCRYPT,
                "confirm": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "already migrated" in response.text

    def test_missing_confirm(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url,
            data={
                "mntner_key": self.mntner_obj.pk(),
                "mntner_source": self.mntner_obj.source(),
                "mntner_password": SAMPLE_MNTNER_BCRYPT + "-invalid",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "This field is required" in response.text

        new_permission = session_provider.run_sync(session_provider.session.query(AuthPermission).one)
        assert not new_permission

    def test_mntner_does_not_exist(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)
        response = test_client.post(
            self.url,
            data={
                "mntner_key": self.mntner_obj.pk() + "-not-exist",
                "mntner_source": self.mntner_obj.source(),
                "mntner_password": SAMPLE_MNTNER_BCRYPT,
                "confirm": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "Unable to find" in response.text

        new_permission = session_provider.run_sync(session_provider.session.query(AuthPermission).one)
        assert not new_permission


class TestMntnerMigrateComplete(WebRequestTest):
    url_template = "/ui/migrate-mntner/complete/{uuid}/{token}/"

    def pre_login(self, session_provider, user, user_management=True):
        self.permission = create_permission(session_provider, user, user_management=user_management)
        self.permission.mntner.migration_token = "migration-token"
        session_provider.session.commit()
        self.url = self.url_template.format(
            uuid=self.permission.mntner.pk, token=self.permission.mntner.migration_token
        )

    def test_render_form(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200

    def test_valid_submit(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url,
            data={
                "mntner_password": SAMPLE_MNTNER_BCRYPT,
                "confirm": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        session_provider.session.refresh(self.permission.mntner)
        assert not self.permission.mntner.migration_token
        assert RPSL_MNTNER_AUTH_INTERNAL in self.permission.mntner.rpsl_mntner_obj.parsed_data["auth"]

        assert len(smtpd.messages) == 3
        assert user.email in smtpd.messages[1].as_string()

    def test_invalid_password(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url,
            data={
                "mntner_password": SAMPLE_MNTNER_BCRYPT + "-invalid",
                "confirm": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "Invalid password" in response.text

        session_provider.session.refresh(self.permission.mntner)
        assert self.permission.mntner.migration_token
        assert RPSL_MNTNER_AUTH_INTERNAL not in self.permission.mntner.rpsl_mntner_obj.parsed_data["auth"]

    def test_invalid_token_or_unknown_id(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            url=f"/ui/migrate-mntner/complete/{uuid.uuid4()}/{self.permission.mntner.migration_token}/",
            data={
                "mntner_password": SAMPLE_MNTNER_BCRYPT,
                "confirm": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 404

        response = test_client.post(
            url=f"/ui/migrate-mntner/complete/{self.permission.mntner.pk}/bad-token/",
            data={
                "mntner_password": SAMPLE_MNTNER_BCRYPT,
                "confirm": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 404

        session_provider.session.refresh(self.permission.mntner)
        assert self.permission.mntner.migration_token
        assert RPSL_MNTNER_AUTH_INTERNAL not in self.permission.mntner.rpsl_mntner_obj.parsed_data["auth"]

    def test_missing_confirm(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url,
            data={
                "mntner_password": SAMPLE_MNTNER_BCRYPT,
            },
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "This field is required" in response.text

        session_provider.session.refresh(self.permission.mntner)
        assert self.permission.mntner.migration_token
        assert RPSL_MNTNER_AUTH_INTERNAL not in self.permission.mntner.rpsl_mntner_obj.parsed_data["auth"]
