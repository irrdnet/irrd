import base64
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Tuple
from urllib.parse import urlparse

import pyotp
import webauthn
import wtforms
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette_wtf import StarletteForm, csrf_protect
from webauthn import base64url_to_bytes
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticationCredential,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    UserVerificationRequirement,
)
from wtforms_bootstrap5 import RendererContext

from irrd.conf import get_setting
from irrd.storage.models import AuthUser, AuthWebAuthn
from irrd.storage.orm_provider import ORMSessionProvider, session_provider_manager
from irrd.webui import MFA_COMPLETE_SESSION_KEY
from irrd.webui.auth.decorators import authentication_required
from irrd.webui.auth.endpoints import clean_next_url
from irrd.webui.auth.users import CurrentPasswordForm
from irrd.webui.helpers import (
    client_ip_str,
    message,
    rate_limit_post,
    send_authentication_change_mail,
)
from irrd.webui.rendering import render_form, template_context_render

logger = logging.getLogger(__name__)

TOTP_REGISTRATION_SECRET_SESSION_KEY = "totp_registration_secret"
WN_CHALLENGE_SESSION_KEY = "webauthn_current_challenge"
WN_RP_NAME = "IRRD"
ENV_WEBAUTHN_TESTING_RP_OVERRIDE = "ENV_WEBAUTHN_TESTING_RP_OVERRIDE"
ENV_WEBAUTHN_TESTING_CHALLENGE_OVERRIDE = "ENV_WEBAUTHN_TESTING_CHALLENGE_OVERRIDE"


def get_webauthn_origin_rpid() -> Tuple[str, str]:
    """
    Determine the WebAuthn origin and Relying Party ID.
    This is either taken from env for tests, or from
    the full server URL in the config.
    """
    if ENV_WEBAUTHN_TESTING_RP_OVERRIDE in os.environ:
        origin, rpid = os.environ[ENV_WEBAUTHN_TESTING_RP_OVERRIDE].split(",")[:2]
        return origin, rpid
    url_parsed = urlparse(get_setting("server.http.url"))
    origin = f"{url_parsed.scheme}://{url_parsed.netloc}"
    rpid = url_parsed.netloc.split(":")[0]
    return origin, rpid


def webauthn_challenge_override() -> Optional[bytes]:
    """
    Override option for the WebAuthn challenge. Used only in tests.
    """
    try:
        return base64url_to_bytes(os.environ[ENV_WEBAUTHN_TESTING_CHALLENGE_OVERRIDE])
    except KeyError:  # pragma: no cover
        return None


@authentication_required
async def mfa_status(request: Request) -> Response:
    context = {
        "has_mfa": request.auth.user.has_mfa,
        "has_totp": request.auth.user.has_totp,
        "webauthns": request.auth.user.webauthns,
    }
    return template_context_render("mfa_status.html", request, context)


class TOTPAuthenticateForm(StarletteForm):
    token = wtforms.StringField(
        label="Enter the current token from your app",
        validators=[wtforms.validators.InputRequired()],
    )
    submit = wtforms.SubmitField("Authenticate with one time password")

    async def validate(self, totp: pyotp.totp.TOTP, last_used: str):
        if not await super().validate():
            return False

        self.token.data = self.token.data.replace(" ", "")

        if not totp.verify(self.token.data, valid_window=1):
            self.token.errors.append("Incorrect token.")
            logger.info("user provided incorrect TOTP token")
            return False

        if self.token.data == last_used and not os.environ["TESTING"]:  # pragma: no cover
            self.token.errors.append("Token already used. Wait for the next token.")
            logger.info("user attempted to reuse previous TOTP token")
            return False

        return True


@rate_limit_post
@authentication_required(mfa_check=False)
@session_provider_manager
async def mfa_authenticate(request: Request, session_provider: ORMSessionProvider) -> Response:
    """
    MFA authentication page for both TOTP and WebAuthn.
    For the TOTP flow, this endpoint processes the form POST request and checks it.
    For WebAuthn, a JSON post is made to webauthn_verify_authentication_response by JS.
    """
    next_url = clean_next_url(request)
    webauthn_options_json = None
    totp_form_html = None
    _, wn_rpid = get_webauthn_origin_rpid()

    if request.auth.user.has_webauthn:
        credentials = [
            PublicKeyCredentialDescriptor(id=auth.credential_id) for auth in request.auth.user.webauthns
        ]
        options = webauthn.generate_authentication_options(
            rp_id=wn_rpid,
            user_verification=UserVerificationRequirement.PREFERRED,
            allow_credentials=credentials,
            challenge=webauthn_challenge_override(),
        )

        request.session[WN_CHALLENGE_SESSION_KEY] = base64.b64encode(options.challenge).decode("ascii")
        webauthn_options_json = webauthn.options_to_json(options)

    if request.auth.user.has_totp:
        totp = pyotp.totp.TOTP(request.auth.user.totp_secret)
        form = await TOTPAuthenticateForm.from_formdata(request=request)
        if form.is_submitted():
            logger.info(f"{client_ip_str(request)}{request.auth.user.email}: attempting to log in with TOTP")
            if await form.validate(totp=totp, last_used=request.auth.user.totp_last_used):
                try:
                    del request.session[WN_CHALLENGE_SESSION_KEY]
                except KeyError:
                    pass
                request.session[MFA_COMPLETE_SESSION_KEY] = True
                request.auth.user.totp_last_used = form.token.data
                session_provider.session.add(request.auth.user)
                logger.info(
                    f"{client_ip_str(request)}{request.auth.user.email}: completed"
                    " TOTP authentication successfully"
                )
                return RedirectResponse(next_url, status_code=302)
        # Intentional non-horizontal form for consistency with WebAuthn button
        totp_form_html = RendererContext().render(form)

    return template_context_render(
        "mfa_authenticate.html",
        request,
        {
            "has_totp": request.auth.user.has_totp,
            "has_webauthn": request.auth.user.has_webauthn,
            "webauthn_options_json": webauthn_options_json,
            "totp_form_html": totp_form_html,
            "next": next_url,
        },
    )


@session_provider_manager
@authentication_required(mfa_check=False)
# No CSRF protection needed: protected by webauthn challenge
async def webauthn_verify_authentication_response(
    request: Request, session_provider: ORMSessionProvider
) -> Response:
    wn_origin, wn_rpid = get_webauthn_origin_rpid()
    try:
        expected_challenge = base64.b64decode(request.session[WN_CHALLENGE_SESSION_KEY])
        credential = AuthenticationCredential.parse_raw(await request.body())
        query = session_provider.session.query(AuthWebAuthn).filter_by(
            user=request.auth.user, credential_id=credential.raw_id
        )
        authn = await session_provider.run(query.one)

        verification = webauthn.verify_authentication_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=wn_rpid,
            expected_origin=wn_origin,
            credential_public_key=authn.credential_public_key,
            credential_current_sign_count=authn.credential_sign_count,
            require_user_verification=False,
        )
    except Exception as err:
        logger.info(
            f"{client_ip_str(request)}{request.auth.user.email}: unable to verify security token"
            f" authentication response: {err}",
            exc_info=err,
        )
        return JSONResponse({"verified": False})

    authn.credential_sign_count = verification.new_sign_count
    authn.last_used = datetime.now(timezone.utc)
    session_provider.session.add(authn)

    del request.session[WN_CHALLENGE_SESSION_KEY]
    request.session[MFA_COMPLETE_SESSION_KEY] = True
    logger.info(
        f"{client_ip_str(request)}{request.auth.user.email}: authenticated successfully with security token"
        f" {authn.pk}"
    )
    return JSONResponse({"verified": True})


@authentication_required
async def webauthn_register(request: Request) -> Response:
    existing_credentials = [
        PublicKeyCredentialDescriptor(id=auth.credential_id) for auth in request.auth.user.webauthns
    ]
    _, wn_rpid = get_webauthn_origin_rpid()

    options = webauthn.generate_registration_options(
        rp_name=WN_RP_NAME,
        rp_id=wn_rpid,
        # An assigned random identifier;
        # never anything user-identifying like an email address
        user_id=str(request.auth.user.pk),
        # A user-visible hint of which account this credential belongs to
        user_name=request.auth.user.email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        attestation=AttestationConveyancePreference.NONE,
        exclude_credentials=existing_credentials,
        challenge=webauthn_challenge_override(),
    )

    # Remember the challenge for later, you'll need it in the next step
    request.session[WN_CHALLENGE_SESSION_KEY] = base64.b64encode(options.challenge).decode("ascii")

    webauthn_options_json = webauthn.options_to_json(options)
    return template_context_render(
        "webauthn_register.html", request, {"webauthn_options_json": webauthn_options_json}
    )


@session_provider_manager
@authentication_required
# No CSRF protection needed: protected by webauthn challenge
async def webauthn_verify_registration_response(
    request: Request, session_provider: ORMSessionProvider
) -> Response:
    wn_origin, wn_rpid = get_webauthn_origin_rpid()
    try:
        expected_challenge = base64.b64decode(request.session[WN_CHALLENGE_SESSION_KEY])
        body = await request.json()
        credential = RegistrationCredential.parse_raw(body["registration_response"])
        verification = webauthn.verify_registration_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=wn_rpid,
            expected_origin=wn_origin,
            require_user_verification=False,
        )
    except Exception as err:
        logger.info(
            f"{client_ip_str(request)}{request.auth.user.email}: unable to verify security"
            f"token registration response: {err}",
            exc_info=err,
        )
        return JSONResponse({"success": False})

    new_auth = AuthWebAuthn(
        user_id=str(request.auth.user.pk),
        name=body["name"],
        credential_id=verification.credential_id,
        credential_public_key=verification.credential_public_key,
        credential_sign_count=verification.sign_count,
    )
    session_provider.session.add(new_auth)
    del request.session[WN_CHALLENGE_SESSION_KEY]
    message(request, "Your security token has been added to your account. You may need to re-authenticate.")
    logger.info(f"{client_ip_str(request)}{request.auth.user.email}: added security token {new_auth.pk}")
    send_authentication_change_mail(request.auth.user, request, "A security token was added to your account.")

    return JSONResponse({"success": True})


class WebAuthnRemoveForm(CurrentPasswordForm):
    submit = wtforms.SubmitField("Remove this security token")


@rate_limit_post
@csrf_protect
@session_provider_manager
@authentication_required
async def webauthn_remove(request: Request, session_provider: ORMSessionProvider) -> Response:
    query = session_provider.session.query(AuthWebAuthn)
    query = query.filter(
        AuthWebAuthn.pk == request.path_params["webauthn"], AuthWebAuthn.user_id == str(request.auth.user.pk)
    )
    target = await session_provider.run(query.one)

    if not target:
        return Response(status_code=404)

    form = await WebAuthnRemoveForm.from_formdata(request=request)
    if not form.is_submitted() or not await form.validate(current_user=request.auth.user):
        return template_context_render(
            "webauthn_remove.html",
            request,
            {"target": target, "form_html": render_form(form)},
        )

    session_provider.session.delete(target)
    message(request, "The security token has been removed.")
    logger.info(f"{client_ip_str(request)}{request.auth.user.email}: removed security token {target.pk}")
    send_authentication_change_mail(
        request.auth.user, request, "A security token was removed from your account."
    )
    return RedirectResponse(request.url_for("ui:auth:mfa_status"), status_code=302)


class TOTPRegisterForm(CurrentPasswordForm):
    token = wtforms.StringField(
        label="Enter the current token from your app",
        validators=[wtforms.validators.InputRequired()],
    )
    submit = wtforms.SubmitField("Enable one time password")

    async def validate(self, current_user: AuthUser, totp: Optional[pyotp.totp.TOTP] = None):
        if not await super().validate(current_user):
            return False

        if not totp or not totp.verify(self.token.data.replace(" ", ""), valid_window=1):
            self.token.errors.append("Incorrect token.")
            return False

        return True


@authentication_required
@session_provider_manager
async def totp_register(request: Request, session_provider: ORMSessionProvider) -> Response:
    form = await TOTPRegisterForm.from_formdata(request=request)
    totp_secret = request.session.get(TOTP_REGISTRATION_SECRET_SESSION_KEY, pyotp.random_base32())
    totp = pyotp.totp.TOTP(totp_secret)
    _, wn_rpid = get_webauthn_origin_rpid()

    if not form.is_submitted() or not await form.validate(current_user=request.auth.user, totp=totp):
        totp_secret = pyotp.random_base32()
        request.session[TOTP_REGISTRATION_SECRET_SESSION_KEY] = totp_secret
        totp_url = pyotp.totp.TOTP(totp_secret).provisioning_uri(
            name=request.auth.user.email, issuer_name=f"IRRD on {wn_rpid}"
        )

        return template_context_render(
            "totp_register.html",
            request,
            {"secret": totp_secret, "totp_url": totp_url, "form_html": render_form(form)},
        )

    request.auth.user.totp_secret = totp_secret
    session_provider.session.add(request.auth.user)
    message(request, "One time passwords have been enabled. You may need to re-authenticate.")
    logger.info(f"{client_ip_str(request)}{request.auth.user.email}: configured new TOTP on account")
    send_authentication_change_mail(
        request.auth.user, request, "One time password was added to your account."
    )
    return RedirectResponse(request.url_for("ui:auth:mfa_status"), status_code=302)


class TOTPRemoveForm(CurrentPasswordForm):
    submit = wtforms.SubmitField("Remove one time password (TOTP)")


@rate_limit_post
@csrf_protect
@session_provider_manager
@authentication_required
async def totp_remove(request: Request, session_provider: ORMSessionProvider) -> Response:
    form = await TOTPRemoveForm.from_formdata(request=request)
    if not form.is_submitted() or not await form.validate(current_user=request.auth.user):
        return template_context_render(
            "totp_remove.html",
            request,
            {"form_html": render_form(form)},
        )

    request.auth.user.totp_secret = None
    session_provider.session.add(request.auth.user)
    message(request, "The one time password been removed.")
    logger.info(f"{client_ip_str(request)}{request.auth.user.email}: removed TOTP from account")
    send_authentication_change_mail(
        request.auth.user, request, "One time password was removed from your account."
    )
    return RedirectResponse(request.url_for("ui:auth:mfa_status"), status_code=302)
