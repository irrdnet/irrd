import base64
import json
import os
import uuid

import pyotp

from irrd.storage.models import AuthWebAuthn
from irrd.utils.factories import (
    SAMPLE_USER_PASSWORD,
    SAMPLE_USER_TOTP_TOKEN,
    AuthWebAuthnFactory,
)
from irrd.webui.auth.endpoints_mfa import (
    ENV_WEBAUTHN_TESTING_CHALLENGE_OVERRIDE,
    ENV_WEBAUTHN_TESTING_RP_OVERRIDE,
)
from irrd.webui.tests.conftest import WebRequestTest


class TestMfaStatus(WebRequestTest):
    url = "/ui/auth/mfa-status"

    def test_render(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        webauthn = AuthWebAuthnFactory(user_id=str(user.pk))
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert webauthn.name in response.text
        assert "enabled for your account" in response.text


class TestTOTPAuthenticate(WebRequestTest):
    url = "/ui/auth/mfa-authenticate/?next=/ui/user/"
    requires_mfa = False

    def test_render_form(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "one time password" in response.text

    def test_valid_totp(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.post(
            self.url,
            data={"token": pyotp.TOTP(SAMPLE_USER_TOTP_TOKEN).now()},
            follow_redirects=True,
        )
        assert response.url.path == "/ui/user/"

    def test_invalid_totp(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.post(
            self.url,
            data={"token": 3},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "Incorrect token." in response.text

    def test_missing_totp(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.post(
            self.url,
            data={},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "This field is required" in response.text


class TestWebAuthnAuthenticate(WebRequestTest):
    url = "/ui/auth/mfa-authenticate/"
    verify_url = "/ui/auth/webauthn-verify-authentication-response/"
    requires_login = True
    requires_mfa = False

    def test_render_form(self, irrd_db_session_with_user, test_client):
        if ENV_WEBAUTHN_TESTING_CHALLENGE_OVERRIDE in os.environ:
            del os.environ[ENV_WEBAUTHN_TESTING_CHALLENGE_OVERRIDE]  # pragma: no cover
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        token = AuthWebAuthnFactory(user_id=str(user.pk))
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert base64.b64encode(token.credential_id)[:10] in response.content

        challenge1 = json.loads(response.context["webauthn_options_json"])["challenge"]
        response = test_client.get(self.url)
        challenge2 = json.loads(response.context["webauthn_options_json"])["challenge"]
        assert challenge1 != challenge2

    def test_valid_authenticate(self, irrd_db_session_with_user, test_client):
        os.environ[ENV_WEBAUTHN_TESTING_RP_OVERRIDE] = "http://localhost:5000,localhost"
        os.environ[ENV_WEBAUTHN_TESTING_CHALLENGE_OVERRIDE] = (
            "iPmAi1Pp1XL6oAgq3PWZtZPnZa1zFUDoGbaQ0_KvVG1lF2s3Rt_3o4uSzccy0tmcTIpTTT4BU1T-I4maavndjQ"
        )

        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        AuthWebAuthnFactory(user_id=str(user.pk))

        # Sets WN_CHALLENGE_SESSION_KEY
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "simplewebauthn" in response.text

        verification_body = json.dumps(
            {
                "id": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
                "rawId": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
                "response": {
                    "authenticatorData": "SZYN5YgOjGh0NBcPZHZgW4_krrmihjLHmVzzuoMdl2MFAAAAAQ",
                    "clientDataJSON": (
                        "eyJ0eXBlIjoid2ViYXV0aG4uZ2V0IiwiY2hhbGxlbmdlIjoiaVBtQWkxUHAxWEw2b0FncTNQV1p0WlBuWmExekZVRG9HYmFRMF9LdlZHMWxGMnMzUnRfM280dVN6Y2N5MHRtY1RJcFRUVDRCVTFULUk0bWFhdm5kalEiLCJvcmlnaW4iOiJodHRwOi8vbG9jYWxob3N0OjUwMDAiLCJjcm9zc09yaWdpbiI6ZmFsc2V9"
                    ),
                    "signature": (
                        "iOHKX3erU5_OYP_r_9HLZ-CexCE4bQRrxM8WmuoKTDdhAnZSeTP0sjECjvjfeS8MJzN1ArmvV0H0C3yy_FdRFfcpUPZzdZ7bBcmPh1XPdxRwY747OrIzcTLTFQUPdn1U-izCZtP_78VGw9pCpdMsv4CUzZdJbEcRtQuRS03qUjqDaovoJhOqEBmxJn9Wu8tBi_Qx7A33RbYjlfyLm_EDqimzDZhyietyop6XUcpKarKqVH0M6mMrM5zTjp8xf3W7odFCadXEJg-ERZqFM0-9Uup6kJNLbr6C5J4NDYmSm3HCSA6lp2iEiMPKU8Ii7QZ61kybXLxsX4w4Dm3fOLjmDw"
                    ),
                    "userHandle": "T1RWa1l6VXdPRFV0WW1NNVlTMDBOVEkxTFRnd056Z3RabVZpWVdZNFpEVm1ZMk5p",
                },
                "type": "public-key",
                "authenticatorAttachment": "cross-platform",
                "clientExtensionResults": {},
            }
        )
        response = test_client.post(self.verify_url, content=verification_body)
        assert response.json()["verified"]

        response = test_client.get("/ui/user/", follow_redirects=False)
        assert response.status_code == 200

    def test_invalid_authenticate(self, irrd_db_session_with_user, test_client):
        os.environ[ENV_WEBAUTHN_TESTING_RP_OVERRIDE] = "http://localhost:5000,localhost"
        os.environ[ENV_WEBAUTHN_TESTING_CHALLENGE_OVERRIDE] = (
            "iPmAi1Pp1XL6oAgq3PWZtZPnZa1zFUDoGbaQ0_KvVG1lF2s3Rt_3o4uSzccy0tmcTIpTTT4BU1T-I4maavndjQ="
        )

        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        AuthWebAuthnFactory(user_id=str(user.pk))

        # Sets WN_CHALLENGE_SESSION_KEY
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "simplewebauthn" in response.text

        # corrupted signature
        verification_body = json.dumps(
            {
                "id": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
                "rawId": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
                "response": {
                    "authenticatorData": "SZYN5YgOjGh0NBcPZHZgW4_krrmihjLHmVzzuoMdl2MFAAAAAQ",
                    "clientDataJSON": (
                        "eyJ0eXBlIjoid2ViYXV0aG4uZ2V0IiwiY2hhbGxlbmdlIjoiaVBtQWkxUHAxWEw2b0FncTNQV1p0WlBuWmExekZVRG9HYmFRMF9LdlZHMWxGMnMzUnRfM280dVN6Y2N5MHRtY1RJcFRUVDRCVTFULUk0bWFhdm5kalEiLCJvcmlnaW4iOiJodHRwOi8vbG9jYWxob3N0OjUwMDAiLCJjcm9zc09yaWdpbiI6ZmFsc2V9"
                    ),
                    "signature": (
                        "iOHKX3erx5_OYP_r_9HLZ-CexCE4bQRrxM8WmuoKTDdhAnZSeTP0sjECjvjfeS8MJzN1ArmvV0H0C3yy_FdRFfcpUPZzdZ7bBcmPh1XPdxRwY747OrIzcTLTFQUPdn1U-izCZtP_78VGw9pCpdMsv4CUzZdJbEcRtQuRS03qUjqDaovoJhOqEBmxJn9Wu8tBi_Qx7A33RbYjlfyLm_EDqimzDZhyietyop6XUcpKarKqVH0M6mMrM5zTjp8xf3W7odFCadXEJg-ERZqFM0-9Uup6kJNLbr6C5J4NDYmSm3HCSA6lp2iEiMPKU8Ii7QZ61kybXLxsX4w4Dm3fOLjmDw"
                    ),
                    "userHandle": "T1RWa1l6VXdPRFV0WW1NNVlTMDBOVEkxTFRnd056Z3RabVZpWVdZNFpEVm1ZMk5p",
                },
                "type": "public-key",
                "authenticatorAttachment": "cross-platform",
                "clientExtensionResults": {},
            }
        )
        response = test_client.post(self.verify_url, content=verification_body)
        assert not response.json()["verified"]

        response = test_client.get("/ui/user/", follow_redirects=False)
        assert response.status_code != 200


class TestWebAuthnRegister(WebRequestTest):
    url = "/ui/auth/webauthn-register/"
    verify_url = "/ui/auth/webauthn-verify-registration-response/"
    requires_login = True
    requires_mfa = True

    def test_render_form(self, irrd_db_session_with_user, test_client):
        if ENV_WEBAUTHN_TESTING_CHALLENGE_OVERRIDE in os.environ:
            del os.environ[ENV_WEBAUTHN_TESTING_CHALLENGE_OVERRIDE]  # pragma: no cover
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        token = AuthWebAuthnFactory(user_id=str(user.pk))
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert base64.b64encode(token.credential_id)[:10] in response.content

        challenge1 = json.loads(response.context["webauthn_options_json"])["challenge"]
        response = test_client.get(self.url)
        challenge2 = json.loads(response.context["webauthn_options_json"])["challenge"]
        assert challenge1 != challenge2

    def test_valid_register(self, irrd_db_session_with_user, test_client_with_smtp):
        test_client, smtpd = test_client_with_smtp
        os.environ[ENV_WEBAUTHN_TESTING_RP_OVERRIDE] = "http://localhost:5000,localhost"
        os.environ[ENV_WEBAUTHN_TESTING_CHALLENGE_OVERRIDE] = (
            "CeTWogmg0cchuiYuFrv8DXXdMZSIQRVZJOga_xayVVEcBj0Cw3y73yhD4FkGSe-RrP6hPJJAIm3LVien4hXELg"
        )

        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)

        # Sets WN_CHALLENGE_SESSION_KEY
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "simplewebauthn" in response.text

        key_name = "key name"
        registration_body = {
            "name": key_name,
            "registration_response": json.dumps(
                {
                    "id": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
                    "rawId": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
                    "response": {
                        "attestationObject": (
                            "o2NmbXRkbm9uZWdhdHRTdG10oGhhdXRoRGF0YVkBZ0mWDeWIDoxodDQXD2R2YFuP5K65ooYyx5lc87qDHZdjRQAAAAAAAAAAAAAAAAAAAAAAAAAAACBmggo_UlC8p2tiPVtNQ8nZ5NSxst4WS_5fnElA2viTq6QBAwM5AQAgWQEA31dtHqc70D_h7XHQ6V_nBs3Tscu91kBL7FOw56_VFiaKYRH6Z4KLr4J0S12hFJ_3fBxpKfxyMfK66ZMeAVbOl_wemY4S5Xs4yHSWy21Xm_dgWhLJjZ9R1tjfV49kDPHB_ssdvP7wo3_NmoUPYMgK-edgZ_ehttp_I6hUUCnVaTvn_m76b2j9yEPReSwl-wlGsabYG6INUhTuhSOqG-UpVVQdNJVV7GmIPHCA2cQpJBDZBohT4MBGme_feUgm4sgqVCWzKk6CzIKIz5AIVnspLbu05SulAVnSTB3NxTwCLNJR_9v9oSkvphiNbmQBVQH1tV_psyi9HM1Jtj9VJVKMeyFDAQAB"
                        ),
                        "clientDataJSON": (
                            "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIiwiY2hhbGxlbmdlIjoiQ2VUV29nbWcwY2NodWlZdUZydjhEWFhkTVpTSVFSVlpKT2dhX3hheVZWRWNCajBDdzN5NzN5aEQ0RmtHU2UtUnJQNmhQSkpBSW0zTFZpZW40aFhFTGciLCJvcmlnaW4iOiJodHRwOi8vbG9jYWxob3N0OjUwMDAiLCJjcm9zc09yaWdpbiI6ZmFsc2V9"
                        ),
                        "transports": ["internal"],
                    },
                    "type": "public-key",
                    "authenticatorAttachment": "platform",
                    "clientExtensionResults": {},
                }
            ),
        }

        response = test_client.post(self.verify_url, json=registration_body)
        assert response.json()["success"]

        token = session_provider.run_sync(session_provider.session.query(AuthWebAuthn).one)
        assert token.name == key_name
        assert len(smtpd.messages) == 1
        assert "token was added" in smtpd.messages[0].as_string()

    def test_invalid_register(self, irrd_db_session_with_user, test_client_with_smtp):
        test_client, smtpd = test_client_with_smtp
        os.environ[ENV_WEBAUTHN_TESTING_RP_OVERRIDE] = "http://localhost:5000,localhost"
        os.environ[ENV_WEBAUTHN_TESTING_CHALLENGE_OVERRIDE] = (
            "CeTWogmg0cchuiYuFrv8DXXdMZSIQRVZJOga_xayVVEcBj0Cw3y73yhD4FkGSe-RrP6hPJJAIm3LVien4hXELg"
        )

        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)

        # Sets WN_CHALLENGE_SESSION_KEY
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "simplewebauthn" in response.text

        registration_body = {
            "name": "key name",
            "registration_response": json.dumps(
                {
                    "id": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
                    "rawId": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
                    "response": {
                        "attestationObject": (
                            "invalidXRkbm9uZWdhdHRTdG10oGhhdXRoRGF0YVkBZ0mWDeWIDoxodDQXD2R2YFuP5K65ooYyx5lc87qDHZdjRQAAAAAAAAAAAAAAAAAAAAAAAAAAACBmggo_UlC8p2tiPVtNQ8nZ5NSxst4WS_5fnElA2viTq6QBAwM5AQAgWQEA31dtHqc70D_h7XHQ6V_nBs3Tscu91kBL7FOw56_VFiaKYRH6Z4KLr4J0S12hFJ_3fBxpKfxyMfK66ZMeAVbOl_wemY4S5Xs4yHSWy21Xm_dgWhLJjZ9R1tjfV49kDPHB_ssdvP7wo3_NmoUPYMgK-edgZ_ehttp_I6hUUCnVaTvn_m76b2j9yEPReSwl-wlGsabYG6INUhTuhSOqG-UpVVQdNJVV7GmIPHCA2cQpJBDZBohT4MBGme_feUgm4sgqVCWzKk6CzIKIz5AIVnspLbu05SulAVnSTB3NxTwCLNJR_9v9oSkvphiNbmQBVQH1tV_psyi9HM1Jtj9VJVKMeyFDAQAB"
                        ),
                        "clientDataJSON": (
                            "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIiwiY2hhbGxlbmdlIjoiQ2VUV29nbWcwY2NodWlZdUZydjhEWFhkTVpTSVFSVlpKT2dhX3hheVZWRWNCajBDdzN5NzN5aEQ0RmtHU2UtUnJQNmhQSkpBSW0zTFZpZW40aFhFTGciLCJvcmlnaW4iOiJodHRwOi8vbG9jYWxob3N0OjUwMDAiLCJjcm9zc09yaWdpbiI6ZmFsc2V9"
                        ),
                        "transports": ["internal"],
                    },
                    "type": "public-key",
                    "authenticatorAttachment": "platform",
                    "clientExtensionResults": {},
                }
            ),
        }

        response = test_client.post(self.verify_url, json=registration_body)
        assert not response.json()["success"]

        assert not session_provider.run_sync(session_provider.session.query(AuthWebAuthn).one)
        assert not smtpd.messages


class TestWebAuthnRemove(WebRequestTest):
    url_template = "/ui/auth/webauthn-remove/{uuid}/"

    def pre_login(self, session_provider, user, user_management=True):
        self.webauthn = AuthWebAuthnFactory(user_id=str(user.pk))
        self.url = self.url_template.format(uuid=self.webauthn.pk)

    def test_render_form(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert self.webauthn.name in response.text

    def test_valid_remove(self, irrd_db_session_with_user, test_client_with_smtp):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url, data={"current_password": SAMPLE_USER_PASSWORD}, follow_redirects=False
        )
        assert response.status_code == 302

        assert not session_provider.run_sync(session_provider.session.query(AuthWebAuthn).one)
        assert len(smtpd.messages) == 1
        assert "token was removed" in smtpd.messages[0].as_string()

    def test_invalid_incorrect_current_password(self, irrd_db_session_with_user, test_client_with_smtp):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(self.url, data={"current_password": "invalid"}, follow_redirects=False)
        assert response.status_code == 200
        assert "Incorrect password." in response.text

        assert session_provider.run_sync(session_provider.session.query(AuthWebAuthn).one)
        assert not smtpd.messages

    def test_invalid_object_not_exists(self, irrd_db_session_with_user, test_client_with_smtp):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        url = self.url_template.format(uuid=uuid.uuid4())

        response = test_client.get(url)
        assert response.status_code == 404
        assert not smtpd.messages


class TestTOTPRegister(WebRequestTest):
    url = "/ui/auth/totp-register/"

    def get_secret(self, test_client, session_provider, user):
        self._login_if_needed(test_client, user)
        user.totp_secret = None
        session_provider.session.commit()

        response = test_client.get(self.url)
        assert response.status_code == 200
        return response.context["secret"]

    def test_valid(self, irrd_db_session_with_user, test_client_with_smtp):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        secret = self.get_secret(test_client, session_provider, user)

        response = test_client.post(
            self.url,
            data={"token": pyotp.TOTP(secret).now(), "current_password": SAMPLE_USER_PASSWORD},
            follow_redirects=False,
        )
        assert response.status_code == 302

        session_provider.session.refresh(user)
        assert user.totp_secret == secret
        assert len(smtpd.messages) == 1
        assert "time password was added" in smtpd.messages[0].as_string()

    def test_invalid_token(self, irrd_db_session_with_user, test_client_with_smtp):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.get_secret(test_client, session_provider, user)

        response = test_client.post(
            self.url,
            data={"token": "invalid", "current_password": SAMPLE_USER_PASSWORD},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "Incorrect token" in response.text

        session_provider.session.refresh(user)
        assert not user.totp_secret
        assert not smtpd.messages

    def test_invalid_current_password(self, irrd_db_session_with_user, test_client_with_smtp):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        secret = self.get_secret(test_client, session_provider, user)

        response = test_client.post(
            self.url,
            data={"token": pyotp.TOTP(secret).now(), "current_password": "invalid"},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "Incorrect password" in response.text

        session_provider.session.refresh(user)
        assert not user.totp_secret
        assert not smtpd.messages

    def test_missing_token(self, irrd_db_session_with_user, test_client_with_smtp):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.get_secret(test_client, session_provider, user)

        response = test_client.post(
            self.url, data={"current_password": SAMPLE_USER_PASSWORD}, follow_redirects=False
        )
        assert response.status_code == 200
        assert "This field is required" in response.text

        session_provider.session.refresh(user)
        assert not user.totp_secret
        assert not smtpd.messages


class TestTOTPRemove(WebRequestTest):
    url = "/ui/auth/totp-remove/"

    def test_render_form(self, irrd_db_session_with_user, test_client):
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.get(self.url)
        assert response.status_code == 200

    def test_valid_remove(self, irrd_db_session_with_user, test_client_with_smtp):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(
            self.url, data={"current_password": SAMPLE_USER_PASSWORD}, follow_redirects=False
        )
        assert response.status_code == 302

        session_provider.session.refresh(user)
        assert not user.totp_secret
        assert "time password was removed" in smtpd.messages[0].as_string()

    def test_invalid_incorrect_current_password(self, irrd_db_session_with_user, test_client_with_smtp):
        test_client, smtpd = test_client_with_smtp
        session_provider, user = irrd_db_session_with_user
        self.pre_login(session_provider, user)
        self._login_if_needed(test_client, user)

        response = test_client.post(self.url, data={"current_password": "invalid"}, follow_redirects=False)
        assert response.status_code == 200
        assert "Incorrect password." in response.text

        session_provider.session.refresh(user)
        assert user.totp_secret
        assert not smtpd.messages
