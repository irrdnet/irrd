from starlette.routing import Route

from .endpoints import (
    change_password,
    change_profile,
    create_account,
    login,
    logout,
    reset_password_request,
    set_password,
)
from .endpoints_mfa import (
    mfa_authenticate,
    mfa_status,
    totp_register,
    totp_remove,
    webauthn_register,
    webauthn_remove,
    webauthn_verify_authentication_response,
    webauthn_verify_registration_response,
)

AUTH_ROUTES = [
    Route("/create/", create_account, name="create_account", methods=["GET", "POST"]),
    Route("/login/", login, name="login", methods=["GET", "POST"]),
    Route("/logout/", logout, name="logout"),
    Route(
        "/set-password/{pk:uuid}/{token}/{initial:int}/",
        set_password,
        name="set_password",
        methods=["GET", "POST"],
    ),
    Route("/reset-password/", reset_password_request, name="reset_password_request", methods=["GET", "POST"]),
    Route("/change-password/", change_password, name="change_password", methods=["GET", "POST"]),
    Route("/change-profile/", change_profile, name="change_profile", methods=["GET", "POST"]),
    Route("/mfa-status/", mfa_status, name="mfa_status"),
    Route("/totp-register/", totp_register, name="totp_register", methods=["GET", "POST"]),
    Route("/totp-remove/", totp_remove, name="totp_remove", methods=["GET", "POST"]),
    Route(
        "/webauthn-remove/{webauthn:uuid}/",
        webauthn_remove,
        name="webauthn_remove",
        methods=["GET", "POST"],
    ),
    Route("/webauthn-register/", webauthn_register, name="webauthn_register"),
    Route(
        "/webauthn-verify-registration-response/",
        webauthn_verify_registration_response,
        name="webauthn_verify_registration_response",
        methods=["POST"],
    ),
    Route("/mfa-authenticate/", mfa_authenticate, name="mfa_authenticate", methods=["GET", "POST"]),
    Route(
        "/webauthn-verify-authentication-response/",
        webauthn_verify_authentication_response,
        name="webauthn_verify_authentication_response",
        methods=["POST"],
    ),
]
