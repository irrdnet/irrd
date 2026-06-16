import pytest
from starlette.testclient import TestClient

from irrd.server.http.app import app
from irrd.utils.factories import SAMPLE_USER_PASSWORD
from irrd.webui.helpers import secret_key_derive


@pytest.fixture()
def https_client(config_override, irrd_db_session_with_user):
    secret_key_derive("scope", thread_safe=False)
    config_override(
        {
            "server": {"http": {"url": "https://testserver/"}},
            "secret_key": "s",
            "sources": {"TEST": {"authoritative": True}, "MIRROR": {}},
            "auth": {"irrd_internal_migration_enabled": True, "webui_auth_failure_rate_limit": "100/second"},
        }
    )
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def _session_set_cookies(response):
    return [c for c in response.headers.get_list("set-cookie") if "session=" in c.lower()]


def _login_response(client, user):
    # SessionMiddleware only emits Set-Cookie when session is modified; a
    # successful login POST writes the user id and reliably triggers it.
    return client.post(
        "/ui/auth/login/",
        data={"email": user.email, "password": SAMPLE_USER_PASSWORD},
        follow_redirects=False,
    )


class TestSecurityHeaders:
    def test_cookie_uses_host_prefix_and_security_attributes(self, https_client, irrd_db_session_with_user):
        _, user = irrd_db_session_with_user
        response = _login_response(https_client, user)
        session_cookies = _session_set_cookies(response)
        assert session_cookies, response.headers
        cookie = session_cookies[0]
        lower = cookie.lower()
        assert cookie.startswith("__Host-session="), cookie
        assert "path=/" in lower, cookie
        assert "secure" in lower, cookie
        assert "httponly" in lower, cookie
        assert "samesite=lax" in lower, cookie
        assert "domain=" not in lower, cookie

    def test_csp_no_unsafe_inline(self, https_client):
        csp = https_client.get("/ui/auth/login/").headers["content-security-policy"]
        assert "'unsafe-inline'" not in csp, csp
        assert "'unsafe-eval'" not in csp, csp

    def test_permissions_policy_grants_webauthn(self, https_client):
        policy = https_client.get("/ui/auth/login/").headers["permissions-policy"]
        assert "publickey-credentials-create=(self)" in policy
        assert "publickey-credentials-get=(self)" in policy

    def test_permissions_policy_denies_sensitive_features(self, https_client):
        policy = https_client.get("/ui/auth/login/").headers["permissions-policy"]
        assert "camera=()" in policy, policy


class TestCacheControlNoStore:
    def test_session_bearing_response_is_no_store(self, https_client, irrd_db_session_with_user):
        _, user = irrd_db_session_with_user
        response = _login_response(https_client, user)
        assert _session_set_cookies(response)
        assert response.headers.get("cache-control") == "no-store"

    def test_non_session_response_is_not_no_store(self, https_client):
        response = https_client.get("/static/css/bootstrap.min.css")
        assert not _session_set_cookies(response)
        assert response.headers.get("cache-control") != "no-store"
