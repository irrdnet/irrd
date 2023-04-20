import secrets
import uuid

from irrd.storage.models import AuthUser
from irrd.utils.factories import SAMPLE_USER_PASSWORD
from irrd.webui.auth.users import PasswordResetToken
from irrd.webui.tests.conftest import WebRequestTest


class TestLogin:
    url = "/ui/auth/login/"

    def test_render_form(self, test_client):
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "password" in response.text

    def test_rate_limit(self, test_client, irrd_db_session_with_user, config_override):
        session_provider, user = irrd_db_session_with_user
        config_override(
            {
                "server": {"http": {"url": "http://testserver/"}},
                "secret_key": "s",
                "auth": {"webui_auth_failure_rate_limit": "1/hour"},
            }
        )
        response = test_client.post(
            self.url,
            data={"email": user.email, "password": "incorrect"},
            allow_redirects=False,
        )
        # This might already hit the limit from previous tests
        assert response.status_code in [200, 403]

        response = test_client.post(
            self.url,
            data={"email": user.email, "password": "incorrect"},
            allow_redirects=False,
        )
        assert response.status_code == 403

    def test_login_valid_mfa_pending(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        response = test_client.post(
            self.url,
            data={"email": user.email, "password": SAMPLE_USER_PASSWORD},
            allow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/ui/auth/mfa-authenticate/")

        # Check that MFA is still pending
        response = test_client.get("/ui/user/")
        assert response.url.startswith("http://testserver/ui/auth/mfa-authenticate/")

    def test_login_valid_no_mfa(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        user.totp_secret = None
        session_provider.session.commit()

        response = test_client.post(
            self.url,
            data={"email": user.email, "password": SAMPLE_USER_PASSWORD},
            allow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/ui/")

        # Check that MFA is not pending
        response = test_client.get("/ui/user/")
        assert response.url.startswith("http://testserver/ui/user/")

    def test_login_invalid(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        response = test_client.post(
            self.url,
            data={"email": user.email, "password": "incorrect"},
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "Invalid account" in response.text


class TestLogout(WebRequestTest):
    url = "/ui/auth/logout/"
    requires_login = True
    requires_mfa = False

    def test_logout(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert user.email not in response.text


class TestCreateAccount:
    url = "/ui/auth/create/"

    def test_render_form(self, test_client):
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "name" in response.text

    def test_create_valid(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        new_user_email = "new-user@example.com"

        response = test_client.post(
            self.url,
            data={"email": new_user_email, "name": "name"},
            allow_redirects=False,
        )
        assert response.status_code == 302

        new_user = session_provider.run_sync(
            session_provider.session.query(AuthUser).filter(AuthUser.email != user.email).one
        )
        assert new_user.email == new_user_email

        token = PasswordResetToken(new_user).generate_token()
        assert len(smtpd.messages) == 1
        assert [new_user_email] == smtpd.messages[0].get_all("to")
        assert str(new_user.pk) in smtpd.messages[0].as_string()
        assert token in smtpd.messages[0].as_string()

    def test_create_invalid_email_exists(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user

        response = test_client.post(
            self.url,
            data={"email": user.email, "name": "name"},
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "account with this email" in response.text

        new_user = session_provider.run_sync(
            session_provider.session.query(AuthUser).filter(AuthUser.email != user.email).one
        )
        assert not new_user
        assert not smtpd.messages

    def test_create_invalid_missing_required(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user

        response = test_client.post(
            self.url,
            data={},
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "This field is required" in response.text

        new_user = session_provider.run_sync(
            session_provider.session.query(AuthUser).filter(AuthUser.email != user.email).one
        )
        assert not new_user
        assert not smtpd.messages


class TestResetPasswordRequest:
    url = "/ui/auth/reset-password/"

    def test_render_form(self, test_client):
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "name" in response.text

    def test_request_valid(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user

        response = test_client.post(
            self.url,
            data={"email": user.email},
            allow_redirects=False,
        )
        assert response.status_code == 302

        token = PasswordResetToken(user).generate_token()
        assert len(smtpd.messages) == 1
        assert [user.email] == smtpd.messages[0].get_all("to")
        assert str(user.pk) in smtpd.messages[0].as_string()
        assert token in smtpd.messages[0].as_string()

    def test_request_unknown_user(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        response = test_client.post(
            self.url,
            data={"email": "invalid-user@example.com"},
            allow_redirects=False,
        )
        assert response.status_code == 302
        assert not smtpd.messages


class TestChangePassword(WebRequestTest):
    url = "/ui/auth/change-password/"

    def test_render_form(self, test_client):
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "name" in response.text

    def test_valid(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)

        new_password = secrets.token_hex(24)

        response = test_client.post(
            self.url,
            data={
                "new_password": new_password,
                "new_password_confirmation": new_password,
                "current_password": SAMPLE_USER_PASSWORD,
            },
            allow_redirects=False,
        )
        assert response.status_code == 302
        self._login(test_client, user, new_password)
        assert len(smtpd.messages) == 1
        assert "password was changed" in smtpd.messages[0].as_string()

    def test_invalid_too_long(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)

        new_password = "a" * 1100

        response = test_client.post(
            self.url,
            data={
                "new_password": new_password,
                "new_password_confirmation": new_password,
                "current_password": SAMPLE_USER_PASSWORD,
            },
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "too long" in response.text
        self._login(test_client, user, SAMPLE_USER_PASSWORD)
        assert not smtpd.messages

    def test_invalid_current_password(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)

        new_password = secrets.token_hex(24)

        response = test_client.post(
            self.url,
            data={
                "new_password": new_password,
                "new_password_confirmation": new_password,
                "current_password": "invalid",
            },
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "Incorrect password." in response.text
        self._login(test_client, user, SAMPLE_USER_PASSWORD)
        assert not smtpd.messages

    def test_invalid_password_mismatch(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)

        new_password = secrets.token_hex(24)
        new_password2 = secrets.token_hex(24)

        response = test_client.post(
            self.url,
            data={
                "new_password": new_password,
                "new_password_confirmation": new_password2,
                "current_password": SAMPLE_USER_PASSWORD,
            },
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "do not match" in response.text
        self._login(test_client, user, SAMPLE_USER_PASSWORD)
        assert not smtpd.messages

    def test_invalid_weak_password(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url,
            data={
                "new_password": "a",
                "new_password_confirmation": "a",
                "current_password": SAMPLE_USER_PASSWORD,
            },
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "not strong enough" in response.text
        self._login(test_client, user, SAMPLE_USER_PASSWORD)
        assert not smtpd.messages

    def test_invalid_missing_field(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)

        new_password = secrets.token_hex(24)

        response = test_client.post(
            self.url,
            data={
                "new_password": new_password,
                "new_password_confirmation": new_password,
            },
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "This field is required." in response.text
        self._login(test_client, user, SAMPLE_USER_PASSWORD)
        assert not smtpd.messages


class TestChangeProfile(WebRequestTest):
    url = "/ui/auth/change-profile/"

    def test_render_form(self, test_client):
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "name" in response.text

    def test_valid(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)

        old_email = user.email
        new_email = "new-email@example.com"
        new_name = "new-name"

        response = test_client.post(
            self.url,
            data={
                "email": new_email,
                "name": new_name,
                "current_password": SAMPLE_USER_PASSWORD,
            },
            allow_redirects=False,
        )
        assert response.status_code == 302

        session_provider.session.refresh(user)
        assert user.email == new_email
        assert user.name == new_name

        assert len(smtpd.messages) == 1
        assert old_email in smtpd.messages[0]["To"]
        assert "current email address" in smtpd.messages[0].as_string()
        assert new_email in smtpd.messages[0].as_string()

    def test_invalid_current_password(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)

        new_email = "new-email@example.com"
        new_name = "new-name"

        response = test_client.post(
            self.url,
            data={
                "email": new_email,
                "name": new_name,
                "current_password": "invalid",
            },
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "Incorrect password." in response.text

        old_email, old_name = user.email, user.name
        session_provider.session.refresh(user)
        assert user.email == old_email
        assert user.name == old_name
        assert not smtpd.messages

    def test_invalid_email(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url,
            data={
                "email": "invalid",
                "name": "new name",
                "current_password": SAMPLE_USER_PASSWORD,
            },
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "Invalid email address" in response.text

        old_email, old_name = user.email, user.name
        session_provider.session.refresh(user)
        assert user.email == old_email
        assert user.name == old_name
        assert not smtpd.messages


class TestSetPassword(WebRequestTest):
    requires_login = False
    requires_mfa = False

    def valid_url(self, user, initial=False):
        token = PasswordResetToken(user).generate_token()
        return f"/ui/auth/set-password/{user.pk}/{token}/{1 if initial else 0}/"

    def test_render_form(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        token = PasswordResetToken(user).generate_token()

        url = f"/ui/auth/set-password/{user.pk}/{token}/0/"
        response = test_client.get(url)
        assert response.status_code == 200
        assert "Reset password" in response.text

        url = f"/ui/auth/set-password/{user.pk}/{token}/1/"
        response = test_client.get(url)
        assert response.status_code == 200
        assert "Create account" in response.text

    def test_valid_reset(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        url = self.valid_url(user)
        new_password = secrets.token_hex(24)

        response = test_client.post(
            url,
            data={"new_password": new_password, "new_password_confirmation": new_password},
            allow_redirects=False,
        )
        assert response.status_code == 302
        self._login(test_client, user, new_password)
        assert len(smtpd.messages) == 1
        assert "password was reset" in smtpd.messages[0].as_string()

    def test_valid_reset_initial(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        url = self.valid_url(user, initial=True)
        new_password = secrets.token_hex(24)

        response = test_client.post(
            url,
            data={"new_password": new_password, "new_password_confirmation": new_password},
            allow_redirects=False,
        )
        assert response.status_code == 302
        self._login(test_client, user, new_password)
        assert not smtpd.messages

    def test_invalid_password_mismatch(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        url = self.valid_url(user)
        new_password = secrets.token_hex(24)
        new_password2 = secrets.token_hex(24)

        response = test_client.post(
            url,
            data={"new_password": new_password, "new_password_confirmation": new_password2},
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "do not match" in response.text
        self._login(test_client, user)  # uses original password
        assert not smtpd.messages

    def test_invalid_password_weak(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        url = self.valid_url(user)

        response = test_client.post(
            url,
            data={"new_password": "a", "new_password_confirmation": "a"},
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "not strong enough" in response.text
        self._login(test_client, user)  # uses original password
        assert not smtpd.messages

    def test_invalid_missing_required(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        url = self.valid_url(user)
        new_password = secrets.token_hex(24)

        response = test_client.post(
            url,
            data={
                "new_password": new_password,
            },
            allow_redirects=False,
        )
        assert response.status_code == 200
        assert "This field is required." in response.text
        self._login(test_client, user)  # uses original password
        assert not smtpd.messages

    def test_unknown_user_or_invalid_token(self, test_client_with_smtp, irrd_db_session_with_user):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user

        token = PasswordResetToken(user).generate_token()
        url = f"/ui/auth/set-password/invalid-uuid/{token}/0/"
        response = test_client.get(url)
        assert response.status_code == 404

        token = PasswordResetToken(user).generate_token()
        url = f"/ui/auth/set-password/{uuid.uuid4()}/{token}/0/"
        response = test_client.get(url)
        assert response.status_code == 404

        url = f"/ui/auth/set-password/{user.pk}/invalid-invalid/1/"
        response = test_client.get(url)
        assert response.status_code == 404

        url = f"/ui/auth/set-password/{user.pk}/a/1"
        response = test_client.get(url)
        assert response.status_code == 404
        assert not smtpd.messages
