import logging
import secrets
from urllib.parse import unquote_plus, urlparse

import wtforms
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette_wtf import StarletteForm, csrf_protect

from irrd.storage.models import AuthUser
from irrd.storage.orm_provider import ORMSessionProvider, session_provider_manager
from irrd.webui import MFA_COMPLETE_SESSION_KEY
from irrd.webui.auth.decorators import authentication_required
from irrd.webui.auth.users import (
    CurrentPasswordForm,
    PasswordResetToken,
    get_login_manager,
    password_handler,
    validate_password_strength,
)
from irrd.webui.helpers import (
    client_ip_str,
    message,
    rate_limit_post,
    send_authentication_change_mail,
    send_template_email,
)
from irrd.webui.rendering import render_form, template_context_render

logger = logging.getLogger(__name__)

DEFAULT_REDIRECT_URL = "ui:index"


def clean_next_url(request: Request, default: str = DEFAULT_REDIRECT_URL):
    """
    Prevent an open redirect by cleaning the redirection URL.
    This discards everything except the path from the next parameter.
    Not very flexible, but sufficient for IRRD needs.
    """
    next_param = unquote_plus(request.query_params.get("next", ""))
    _, _, next_path, _, _, _ = urlparse(next_param)
    return next_path if next_path else request.url_for(default)


@rate_limit_post
async def login(request: Request):
    if request.method == "GET":
        return template_context_render(
            "login.html",
            request,
            {
                "errors": None,
            },
        )

    if request.method == "POST":
        data = await request.form()
        email = data["email"]
        password = data["password"]
        default_next = "ui:auth:mfa_authenticate"

        user_token = await get_login_manager().login(request, email, password)
        if user_token:
            logger.info(f"{client_ip_str(request)}{email}: successfully logged in")
            if not user_token.user.has_mfa:
                default_next = "ui:index"
                request.session[MFA_COMPLETE_SESSION_KEY] = True
            return RedirectResponse(clean_next_url(request, default_next), status_code=302)
        else:
            logger.info(f"{client_ip_str(request)}user failed login due to invalid account or password")
            return template_context_render(
                "login.html",
                request,
                {
                    "errors": "Invalid account or password.",
                },
            )


@authentication_required(mfa_check=False)
async def logout(request: Request):
    await get_login_manager().logout(request)
    return RedirectResponse(request.url_for("ui:index"), status_code=302)


class CreateAccountForm(StarletteForm):
    def __init__(self, *args, session_provider: ORMSessionProvider, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_provider = session_provider

    email = wtforms.EmailField(
        "Your email address",
        validators=[wtforms.validators.DataRequired(), wtforms.validators.Email()],
    )
    name = wtforms.StringField(
        "Your name",
        validators=[wtforms.validators.DataRequired()],
    )
    submit = wtforms.SubmitField("Create account")

    async def validate(self):
        if not await super().validate():
            return False

        query = self.session_provider.session.query(AuthUser).filter_by(email=self.email.data)
        if await self.session_provider.run(query.count):
            self.email.errors.append("An account with this email address already exists.")
            return False

        return True


@rate_limit_post(any_response_code=True)
@csrf_protect
@session_provider_manager
async def create_account(request: Request, session_provider: ORMSessionProvider) -> Response:
    form = await CreateAccountForm.from_formdata(request=request, session_provider=session_provider)
    if not form.is_submitted() or not await form.validate():
        return template_context_render("create_account_form.html", request, {"form_html": render_form(form)})

    new_user = AuthUser(
        email=form.email.data,
        password=secrets.token_hex(24),
        name=form.name.data,
    )
    session_provider.session.add(new_user)
    session_provider.session.commit()

    token = PasswordResetToken(new_user).generate_token()
    send_template_email(form.email.data, "create_account", request, {"user_pk": new_user.pk, "token": token})
    message(request, f"You have been sent an email to confirm your account on {form.email.data}.")
    logger.info(f"{client_ip_str(request)}{form.email.data}: created new account, confirmation pending")
    return RedirectResponse(request.url_for("ui:index"), status_code=302)


class ResetPasswordRequestForm(StarletteForm):
    email = wtforms.EmailField(
        "Your email address",
        validators=[wtforms.validators.DataRequired(), wtforms.validators.Email()],
    )
    submit = wtforms.SubmitField("Reset password")


@rate_limit_post(any_response_code=True)
@csrf_protect
@session_provider_manager
async def reset_password_request(request: Request, session_provider: ORMSessionProvider) -> Response:
    form = await ResetPasswordRequestForm.from_formdata(request=request)
    if not form.is_submitted() or not await form.validate():
        return template_context_render(
            "reset_password_request_form.html", request, {"form_html": render_form(form)}
        )

    query = session_provider.session.query(AuthUser).filter_by(email=form.email.data)
    user = await session_provider.run(query.one)

    if user:
        token = PasswordResetToken(user).generate_token()
        send_template_email(
            form.email.data, "reset_password_request", request, {"user_pk": user.pk, "token": token}
        )
    message(
        request,
        f"You have been sent an email to reset your password on {form.email.data}, if this account exists.",
    )
    logger.info(f"{client_ip_str(request)}{form.email.data}: password reset email requested")
    return RedirectResponse(request.url_for("ui:index"), status_code=302)


class ChangePasswordForm(CurrentPasswordForm):
    new_password = wtforms.PasswordField(
        validators=[wtforms.validators.DataRequired()],
    )
    new_password_confirmation = wtforms.PasswordField(
        validators=[wtforms.validators.DataRequired()],
    )
    submit = wtforms.SubmitField("Change password")

    async def validate(self, current_user: AuthUser):
        if not await super().validate(current_user=current_user):
            return False

        is_sufficient, tips = validate_password_strength(self.new_password.data)
        if not is_sufficient:
            self.new_password.errors.append("Passwords is not strong enough. " + tips)
            return False

        if self.new_password.data != self.new_password_confirmation.data:
            self.new_password_confirmation.errors.append("Passwords do not match.")
            return False

        return True


@rate_limit_post
@csrf_protect
@session_provider_manager
@authentication_required
async def change_password(request: Request, session_provider: ORMSessionProvider) -> Response:
    form = await ChangePasswordForm.from_formdata(request=request)
    if not form.is_submitted() or not await form.validate(current_user=request.auth.user):
        return template_context_render(
            "password_change_form.html",
            request,
            {"form_html": render_form(form)},
        )

    request.auth.user.password = password_handler.hash(form.new_password.data)
    session_provider.session.add(request.auth.user)
    message(request, "Your password has been changed.")
    logger.info(f"{client_ip_str(request)}{request.auth.user.email}: password changed successfully")
    send_authentication_change_mail(request.auth.user, request, "Your password was changed.")
    return RedirectResponse(request.url_for("ui:index"), status_code=302)


class ChangeProfileForm(CurrentPasswordForm):
    email = wtforms.EmailField(
        validators=[wtforms.validators.DataRequired(), wtforms.validators.Email()],
    )
    name = wtforms.StringField(
        validators=[wtforms.validators.DataRequired()],
    )
    submit = wtforms.SubmitField("Change name/email")


@rate_limit_post
@csrf_protect
@session_provider_manager
@authentication_required
async def change_profile(request: Request, session_provider: ORMSessionProvider) -> Response:
    form = await ChangeProfileForm.from_formdata(
        request=request, email=request.auth.user.email, name=request.auth.user.name
    )
    if not form.is_submitted() or not await form.validate(current_user=request.auth.user):
        return template_context_render(
            "profile_change_form.html",
            request,
            {"form_html": render_form(form)},
        )

    request.auth.user.name = form.name.data
    old_email = request.auth.user.email
    request.auth.user.email = form.email.data
    session_provider.session.add(request.auth.user)
    message(request, "Your name/e-mail address have been changed.")
    logger.info(
        f"{client_ip_str(request)}{request.auth.user.email}: name/email changed successfully (old email"
        f" {old_email}"
    )
    send_authentication_change_mail(
        request.auth.user,
        request,
        "Your name and/or email address were updated. The current email address on your account is"
        f" {request.auth.user.email}.",
        recipient_override=old_email,
    )
    return RedirectResponse(request.url_for("ui:index"), status_code=302)


class SetPasswordForm(StarletteForm):
    new_password = wtforms.PasswordField(
        validators=[wtforms.validators.DataRequired()],
    )
    new_password_confirmation = wtforms.PasswordField(
        validators=[wtforms.validators.DataRequired()],
    )
    submit = wtforms.SubmitField("Set password")

    async def validate(self):
        if not await super().validate():
            return False

        is_sufficient, tips = validate_password_strength(self.new_password.data)
        if not is_sufficient:
            self.new_password.errors.append("Passwords is not strong enough. " + tips)
            return False

        if self.new_password.data != self.new_password_confirmation.data:
            self.new_password_confirmation.errors.append("Passwords do not match.")
            return False

        return True


@csrf_protect
@session_provider_manager
async def set_password(request: Request, session_provider: ORMSessionProvider) -> Response:
    query = session_provider.session.query(AuthUser).filter(
        AuthUser.pk == request.path_params["pk"],
    )
    user = await session_provider.run(query.one)

    if not user or not PasswordResetToken(user).validate_token(request.path_params["token"]):
        return Response(status_code=404)

    form = await SetPasswordForm.from_formdata(request=request)
    initial = int(request.path_params.get("initial", "0"))
    if not form.is_submitted() or not await form.validate():
        return template_context_render(
            "create_account_confirm_form.html",
            request,
            {"form_html": render_form(form), "initial": initial},
        )

    user.password = password_handler.hash(form.new_password.data)
    session_provider.session.add(user)
    message(request, "Your password has been changed.")
    logger.info(f"{client_ip_str(request)}{user.email}: password (re)set successfully")
    if not initial:
        send_authentication_change_mail(user, request, "Your password was reset.")
    return RedirectResponse(request.url_for("ui:auth:login"), status_code=302)
