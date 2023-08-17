import pyotp
import pytest
from starlette.testclient import TestClient

from irrd.server.http.app import app
from irrd.utils.factories import (
    SAMPLE_USER_PASSWORD,
    SAMPLE_USER_TOTP_TOKEN,
    AuthMntnerFactory,
    AuthPermissionFactory,
)
from irrd.webui.helpers import secret_key_derive


@pytest.fixture()
def test_client(config_override):
    secret_key_derive("scope", thread_safe=False)

    config_override(
        {
            "server": {"http": {"url": "http://testserver/"}},
            "secret_key": "s",
            "sources": {"TEST": {"authoritative": True}, "MIRROR": {}},
            "auth": {"irrd_internal_migration_enabled": True, "webui_auth_failure_rate_limit": "100/second"},
        }
    )
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def test_client_with_smtp(config_override, smtpd):
    secret_key_derive("scope", thread_safe=False)

    config_override(
        {
            "server": {"http": {"url": "http://testserver/"}},
            "secret_key": "s",
            "sources": {"TEST": {"authoritative": True}, "MIRROR": {}},
            "email": {"smtp": f"localhost:{smtpd.port}", "from": "irrd@example.net"},
            "auth": {"irrd_internal_migration_enabled": True, "webui_auth_failure_rate_limit": "100/second"},
        }
    )
    with TestClient(app) as client:
        yield client, smtpd


class WebRequestTest:
    url: str
    requires_login = True
    requires_mfa = True

    def test_login_requirement(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        if not self.requires_login:
            return
        self.pre_login(session_provider, user)
        response = test_client.get(self.url)
        assert response.url.path == "/ui/auth/login/"

    def test_mfa_requirement(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        if not self.requires_mfa:
            return

        self.pre_login(session_provider, user)
        self._login(test_client, user)
        response = test_client.get("/ui/user/")
        assert response.url.path == "/ui/auth/mfa-authenticate/"

    def _login(self, test_client, user, password=SAMPLE_USER_PASSWORD):
        response = test_client.post(
            "/ui/auth/login/",
            data={"email": user.email, "password": password},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def _logout(self, test_client):
        response = test_client.get(
            "/ui/auth/logout/",
        )
        assert response.status_code == 302

    def _verify_mfa(self, test_client):
        response = test_client.post(
            "/ui/auth/mfa-authenticate/",
            data={"token": pyotp.TOTP(SAMPLE_USER_TOTP_TOKEN).now()},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def _login_if_needed(self, test_client, user):
        if self.requires_login:
            self._login(test_client, user)
        if self.requires_mfa:
            self._verify_mfa(test_client)

    def pre_login(self, session_provider, user):
        pass


def create_permission(session_provider, user, mntner=None, user_management=True):
    if not mntner:
        mntner = AuthMntnerFactory()
    return AuthPermissionFactory(
        user_id=str(user.pk), mntner_id=str(mntner.pk), user_management=user_management
    )
