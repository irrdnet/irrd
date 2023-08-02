import logging
import secrets
import textwrap
from typing import Optional

import wtforms
from IPy import IP
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette_wtf import StarletteForm, csrf_protect, csrf_token

from irrd.conf import get_setting
from irrd.rpsl.rpsl_objects import RPSLMntner
from irrd.storage.models import (
    AuthApiToken,
    AuthMntner,
    AuthPermission,
    AuthUser,
    ChangeLog,
    JournalEntryOrigin,
    RPSLDatabaseObject,
)
from irrd.storage.orm_provider import ORMSessionProvider, session_provider_manager
from irrd.utils.email import send_email
from irrd.utils.text import clean_ip_value_error
from irrd.webui.auth.decorators import authentication_required
from irrd.webui.auth.users import CurrentPasswordForm
from irrd.webui.helpers import (
    client_ip,
    client_ip_str,
    message,
    rate_limit_post,
    send_template_email,
)
from irrd.webui.rendering import render_form, template_context_render

logger = logging.getLogger(__name__)


class ApiTokenForm(StarletteForm):
    name = wtforms.StringField(
        "Name of the new token",
        validators=[wtforms.validators.DataRequired()],
        description="For your own reference.",
    )
    # TODO: cidr validator
    ip_restriction = wtforms.StringField(
        "Restrict to IP/CIDR (optional)",
        description="You can include multiple IP/CIDRs, separated by commas.",
    )
    enabled_webapi = wtforms.BooleanField("Enable this token for HTTPS API submissions")
    enabled_email = wtforms.BooleanField("Enable this token for email submissions")
    submit = wtforms.SubmitField("Save API token")

    def validate_ip_restriction(self, field):
        if not field.data:
            field.data = None
            return
        try:
            field.data = ",".join([str(IP(data)) for data in field.data.split(",")])
        except ValueError as ve:
            raise wtforms.ValidationError(f"Invalid IP or CIDR ranges: {clean_ip_value_error(ve)}")

    async def validate(self, **kwargs):
        if not await super().validate():  # pragma: no cover
            return False

        if self.enabled_email.data and self.ip_restriction.data:
            self.enabled_email.errors.append("Email submissions can not be combined with an IP restriction.")
            return False

        return True


@csrf_protect
@session_provider_manager
@authentication_required
async def api_token_add(request: Request, session_provider: ORMSessionProvider) -> Response:
    """
    Create a new API token.
    """
    query = session_provider.session.query(AuthMntner).join(AuthPermission)
    query = query.filter(
        AuthMntner.pk == request.path_params["mntner"],
        AuthPermission.user_id == str(request.auth.user.pk),
    )
    mntner = await session_provider.run(query.one)

    if not mntner or not mntner.migration_complete:
        return Response(status_code=404)

    form = await ApiTokenForm.from_formdata(request=request)
    if not form.is_submitted() or not await form.validate():
        form_html = render_form(form)
        return template_context_render(
            "api_token_form.html", request, {"form_html": form_html, "api_token": None, "mntner": mntner}
        )

    new_token = AuthApiToken(
        mntner_id=str(mntner.pk),
        creator_id=str(request.auth.user.pk),
        name=form.data["name"],
        ip_restriction=form.data["ip_restriction"],
        enabled_webapi=form.data["enabled_webapi"],
        enabled_email=form.data["enabled_email"],
    )
    session_provider.session.add(new_token)
    message_text = f"An API key for '{new_token.name}' on {mntner.rpsl_mntner_pk} has been added."
    message(request, message_text)
    await notify_mntner(session_provider, request.auth.user, mntner, explanation=message_text)
    logger.info(
        f'{client_ip_str(request)}{request.auth.user.email}: added API token "{new_token.name}"'
        f" ({new_token.pk}) on mntner {mntner.rpsl_mntner_pk}"
    )
    session_provider.session.add(
        ChangeLog(
            auth_by_user_id=str(request.auth.user.pk),
            auth_by_user_email=request.auth.user.email,
            auth_through_mntner_id=str(mntner.pk),
            auth_through_rpsl_mntner_pk=str(mntner.rpsl_mntner_pk),
            from_ip=client_ip(request),
            auth_change_descr=f'added API token "{new_token.name}" ({new_token.pk})',
            auth_affected_mntner_id=str(mntner.pk),
        )
    )

    return RedirectResponse(request.url_for("ui:user_permissions"), status_code=302)


@csrf_protect
@session_provider_manager
@authentication_required
async def api_token_edit(request: Request, session_provider: ORMSessionProvider) -> Response:
    """
    Edit an existing API token
    """
    query = session_provider.session.query(AuthApiToken)
    query = query.filter(
        AuthApiToken.pk == request.path_params["token_pk"],
        AuthApiToken.mntner_id.in_([perm.mntner_id for perm in request.auth.user.permissions]),
    )
    api_token = await session_provider.run(query.one)

    if not api_token:
        return Response(status_code=404)

    form = await ApiTokenForm.from_formdata(request=request, obj=api_token)
    if not form.is_submitted() or not await form.validate():
        form_html = render_form(form)
        return template_context_render(
            "api_token_form.html",
            request,
            {"form_html": form_html, "api_token": api_token, "mntner": api_token.mntner},
        )

    api_token.name = form.data["name"]
    api_token.ip_restriction = form.data["ip_restriction"]
    api_token.enabled_webapi = form.data["enabled_webapi"]
    api_token.enabled_email = form.data["enabled_email"]
    session_provider.session.add(api_token)
    message_text = f"The API key for '{api_token.name}' on {api_token.mntner.rpsl_mntner_pk} was modified."
    message(request, message_text)
    logger.info(
        f'{client_ip_str(request)}{request.auth.user.email}: updated API token "{api_token.name}"'
        f" ({api_token.pk}) on mntner {api_token.mntner.rpsl_mntner_pk}"
    )
    session_provider.session.add(
        ChangeLog(
            auth_by_user_id=str(request.auth.user.pk),
            auth_by_user_email=request.auth.user.email,
            auth_through_mntner_id=str(api_token.mntner.pk),
            auth_through_rpsl_mntner_pk=str(api_token.mntner.rpsl_mntner_pk),
            from_ip=client_ip(request),
            auth_change_descr=f'modified API token "{api_token.name}" ({api_token.pk})',
            auth_affected_mntner_id=str(api_token.mntner.pk),
        )
    )

    return RedirectResponse(request.url_for("ui:user_permissions"), status_code=302)


@csrf_protect
@session_provider_manager
@authentication_required
async def api_token_delete(request: Request, session_provider: ORMSessionProvider) -> Response:
    """
    Delete an API token
    """
    query = session_provider.session.query(AuthApiToken)
    query = query.filter(
        AuthApiToken.pk == request.path_params["token_pk"],
        AuthApiToken.mntner_id.in_([perm.mntner_id for perm in request.auth.user.permissions]),
    )
    api_token = await session_provider.run(query.one)

    if not api_token:
        return Response(status_code=404)

    if request.method == "GET":
        return template_context_render(
            "api_token_delete.html",
            request,
            {
                "api_token": api_token,
                "csrf_token": csrf_token(request),
            },
        )

    session_provider.session.query(AuthApiToken).filter(
        AuthApiToken.pk == request.path_params["token_pk"]
    ).delete()
    message_text = (
        f"The API token named '{api_token.name}' on {api_token.mntner.rpsl_mntner_pk} has been deleted."
    )
    message(request, message_text)
    await notify_mntner(session_provider, request.auth.user, api_token.mntner, explanation=message_text)
    logger.info(
        f'{client_ip_str(request)}{request.auth.user.email}: removed API token "{api_token.name}"'
        f" ({api_token.pk}) on mntner {api_token.mntner.rpsl_mntner_pk}"
    )
    session_provider.session.add(
        ChangeLog(
            auth_by_user_id=str(request.auth.user.pk),
            auth_by_user_email=request.auth.user.email,
            auth_through_mntner_id=str(api_token.mntner.pk),
            auth_through_rpsl_mntner_pk=str(api_token.mntner.rpsl_mntner_pk),
            from_ip=client_ip(request),
            auth_change_descr=f'removed API token "{api_token.name}" ({api_token.pk})',
            auth_affected_mntner_id=str(api_token.mntner.pk),
        )
    )

    return RedirectResponse(request.url_for("ui:user_permissions"), status_code=302)


class PermissionAddForm(CurrentPasswordForm):
    def __init__(self, *args, session_provider: ORMSessionProvider, **kwargs):
        super().__init__(*args, **kwargs)
        self.new_user = None
        self.session_provider = session_provider

    new_user_email = wtforms.EmailField(
        "Email address of the newly authorised user",
        validators=[wtforms.validators.DataRequired()],
    )
    confirm = wtforms.BooleanField(
        "Give this user access to modify all objects maintained by this mntner",
        validators=[wtforms.validators.DataRequired()],
    )
    user_management = wtforms.BooleanField(
        "Give this user access to user management, including adding and removing other users (including"
        " myself)",
    )
    submit = wtforms.SubmitField("Authorise this user")

    async def validate(self, current_user: AuthUser, mntner: Optional[AuthMntner] = None):
        if not await super().validate(current_user=current_user):
            return False

        query = self.session_provider.session.query(AuthUser).filter_by(email=self.new_user_email.data)
        self.new_user = await self.session_provider.run(query.one)

        if not self.new_user:
            self.new_user_email.errors.append("Unknown user account.")
            return False

        query = self.session_provider.session.query(AuthPermission).filter_by(
            mntner=mntner, user=self.new_user
        )
        existing_perms = await self.session_provider.run(query.count)

        if existing_perms:
            self.new_user_email.errors.append("This user already has permissions on this mntner.")
            return False

        return True


@rate_limit_post
@csrf_protect
@session_provider_manager
@authentication_required
async def permission_add(request: Request, session_provider: ORMSessionProvider) -> Response:
    """
    Add a new permission for an existing user on a migrated mntner.
    """
    query = session_provider.session.query(AuthMntner).join(AuthPermission)
    query = query.filter(
        AuthMntner.pk == request.path_params["mntner"],
        AuthPermission.user_id == str(request.auth.user.pk),
        AuthPermission.user_management.is_(True),
    )
    mntner = await session_provider.run(query.one)

    if not mntner or not mntner.migration_complete:
        return Response(status_code=404)

    form = await PermissionAddForm.from_formdata(request=request, session_provider=session_provider)
    if not form.is_submitted() or not await form.validate(current_user=request.auth.user, mntner=mntner):
        form_html = render_form(form)
        return template_context_render(
            "permission_form.html", request, {"form_html": form_html, "mntner": mntner}
        )

    new_permission = AuthPermission(
        user_id=str(form.new_user.pk),
        mntner_id=str(mntner.pk),
        user_management=bool(form.user_management.data),
    )
    session_provider.session.add(new_permission)
    message_text = (
        f"A permission for {form.new_user.name} ({form.new_user.email}) on "
        f"{mntner.rpsl_mntner_pk} has been added."
    )
    message(request, message_text)
    await notify_mntner(session_provider, request.auth.user, mntner, explanation=message_text)
    logger.info(
        f"{client_ip_str(request)}{request.auth.user.email}: added permission {new_permission.pk} on mntner"
        f" {mntner.rpsl_mntner_pk} for user {form.new_user.email}"
    )
    session_provider.session.add(
        ChangeLog(
            auth_by_user_id=str(request.auth.user.pk),
            auth_by_user_email=request.auth.user.email,
            auth_through_mntner_id=str(mntner.pk),
            auth_through_rpsl_mntner_pk=str(mntner.rpsl_mntner_pk),
            from_ip=client_ip(request),
            auth_change_descr=(
                f"added permission for {new_permission.user.email},"
                f" {'with' if new_permission.user_management else 'without'} user management"
            ),
            auth_affected_user_id=str(new_permission.user.pk),
            auth_affected_mntner_id=str(mntner.pk),
        )
    )

    return RedirectResponse(request.url_for("ui:user_permissions"), status_code=302)


class PermissionDeleteForm(CurrentPasswordForm):
    confirm = wtforms.BooleanField(
        "Remove this user's access to this mntner", validators=[wtforms.validators.DataRequired()]
    )
    confirm_self_delete = wtforms.BooleanField(
        "I understand I am deleting my own permission on this mntner, and will immediately lose access",
        validators=[wtforms.validators.DataRequired()],
    )
    submit = wtforms.SubmitField("Remove this user's authorisation")


@rate_limit_post
@csrf_protect
@session_provider_manager
@authentication_required
async def permission_delete(request: Request, session_provider: ORMSessionProvider) -> Response:
    """
    Remove a permission for a user on a mntner.
    Users can not delete the last permission, and must provide extra confirmation
    when deleting their own permission.
    """
    query = session_provider.session.query(AuthPermission)
    user_mntner_pks = [perm.mntner_id for perm in request.auth.user.permissions if perm.user_management]
    query = query.filter(
        AuthPermission.pk == request.path_params["permission"],
        AuthPermission.mntner_id.in_(user_mntner_pks),
    )
    permission = await session_provider.run(query.one)

    if not permission or not permission.mntner.migration_complete:
        return Response(status_code=404)

    if len(permission.mntner.permissions) == 1:
        return template_context_render(
            "permission_delete.html", request, {"refused_last_permission": True, "permission": permission}
        )

    form = await PermissionDeleteForm.from_formdata(request=request)
    if request.auth.user != permission.user:
        del form.confirm_self_delete

    if not form.is_submitted() or not await form.validate(current_user=request.auth.user):
        form_html = render_form(form)
        return template_context_render(
            "permission_delete.html", request, {"form_html": form_html, "permission": permission}
        )

    message_text = (
        f"The permission for {permission.user.name} ({permission.user.email}) on"
        f" {permission.mntner.rpsl_mntner_pk} has been deleted."
    )
    await notify_mntner(session_provider, request.auth.user, permission.mntner, explanation=message_text)
    session_provider.session.query(AuthPermission).filter(
        AuthPermission.pk == request.path_params["permission"]
    ).delete()
    message(request, message_text)
    logger.info(
        f"{client_ip_str(request)}{request.auth.user.email}: removed permission {permission.pk} on mntner"
        f" {permission.mntner.rpsl_mntner_pk} for user {permission.user.email}"
    )
    session_provider.session.add(
        ChangeLog(
            auth_by_user_id=str(request.auth.user.pk),
            auth_by_user_email=request.auth.user.email,
            auth_through_mntner_id=str(permission.mntner.pk),
            auth_through_rpsl_mntner_pk=str(permission.mntner.rpsl_mntner_pk),
            from_ip=client_ip(request),
            auth_change_descr=(
                f"deleted permission for {permission.user.email}"
                f" {'with' if permission.user_management else 'without'} user management"
            ),
            auth_affected_user_id=str(permission.user.pk),
            auth_affected_mntner_id=str(permission.mntner.pk),
        )
    )

    return RedirectResponse(request.url_for("ui:user_permissions"), status_code=302)


class MntnerMigrateInitiateForm(StarletteForm):
    def __init__(self, *args, session_provider: ORMSessionProvider, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_provider = session_provider
        self.rpsl_mntner = None
        self.rpsl_mntner_db_pk = None
        auth_sources = [
            name for name, settings in get_setting("sources").items() if settings.get("authoritative")
        ]
        self.mntner_source.choices = sorted([(source, source) for source in auth_sources])

    mntner_key = wtforms.StringField(
        "Mntner name",
        description="The name (primary key) of the mntner to migrate.",
        validators=[wtforms.validators.DataRequired()],
        filters=[lambda x: x.upper() if x else None],
    )
    mntner_source = wtforms.SelectField(
        "Mntner source",
        description="The RPSL database for your mntner.",
        validators=[wtforms.validators.DataRequired()],
    )
    mntner_password = wtforms.StringField(
        "Mntner password",
        description="One of the current passwords on the mntner",
        validators=[wtforms.validators.DataRequired()],
    )
    confirm = wtforms.BooleanField(
        "I understand that this migration can not be reversed", validators=[wtforms.validators.DataRequired()]
    )
    submit = wtforms.SubmitField("Migrate this mntner")

    async def validate(self):
        if not await super().validate():
            return False

        query = self.session_provider.session.query(RPSLDatabaseObject).outerjoin(AuthMntner)
        query = query.filter(
            RPSLDatabaseObject.rpsl_pk == self.mntner_key.data,
            RPSLDatabaseObject.source == self.mntner_source.data,
            RPSLDatabaseObject.object_class == "mntner",
        )
        mntner_obj = await self.session_provider.run(query.one)
        if not mntner_obj:
            self.mntner_key.errors.append("Unable to find this mntner object.")
            return False
        if mntner_obj.auth_mntner:
            self.mntner_key.errors.append(
                "This maintainer was already migrated or a migration is in progress."
            )
            return False
        self.rpsl_mntner_db_pk = mntner_obj.pk
        self.rpsl_mntner = RPSLMntner(mntner_obj.object_text, strict_validation=False)

        valid_scheme = self.rpsl_mntner.verify_auth(passwords=[self.mntner_password.data])
        if not valid_scheme:
            logger.info(
                f"invalid password provided for mntner {self.rpsl_mntner.pk()} "
                " while attempting to start migration"
            )
            self.mntner_password.errors.append("Invalid password for the methods on this mntner object.")
            return False

        return True


@rate_limit_post
@csrf_protect
@session_provider_manager
@authentication_required
async def mntner_migrate_initiate(request: Request, session_provider: ORMSessionProvider) -> Response:
    """
    Initiate the migration of a mntner.
    Current mntner is authenticated by a password and mail confirmation on admin-c.
    Current user gets permission with user_management if successful.
    A random secret token is stored in the DB and mailed to the admin-c's.

    Migration itself consists of creating an AuthMntner.
    """
    if not get_setting("auth.irrd_internal_migration_enabled"):
        return template_context_render("mntner_migrate_initiate.html", request, {})

    form = await MntnerMigrateInitiateForm.from_formdata(request=request, session_provider=session_provider)
    if not form.is_submitted() or not await form.validate():
        form_html = render_form(form)
        return template_context_render("mntner_migrate_initiate.html", request, {"form_html": form_html})

    new_auth_mntner = AuthMntner(
        rpsl_mntner_pk=form.rpsl_mntner.pk(),
        rpsl_mntner_obj_id=str(form.rpsl_mntner_db_pk),
        rpsl_mntner_source=form.mntner_source.data,
        migration_token=secrets.token_urlsafe(24),
    )
    session_provider.session.add(new_auth_mntner)
    session_provider.session.commit()

    new_permission = AuthPermission(
        user_id=str(request.auth.user.pk),
        mntner_id=str(new_auth_mntner.pk),
        user_management=True,
    )
    session_provider.session.add(new_permission)

    await send_mntner_migrate_initiate_mail(session_provider, request, new_auth_mntner, form.rpsl_mntner)
    message(request, "The mntner's admin-c's have been sent a confirmation email to complete the migration.")
    logger.info(
        f"{client_ip_str(request)}{request.auth.user.email}: initiated migration of {form.rpsl_mntner.pk()},"
        " pending confirmation"
    )
    session_provider.session.add(
        ChangeLog(
            auth_by_user_id=str(request.auth.user.pk),
            auth_by_user_email=request.auth.user.email,
            auth_through_mntner_id=str(new_auth_mntner.pk),
            auth_through_rpsl_mntner_pk=str(new_auth_mntner.rpsl_mntner_pk),
            from_ip=client_ip(request),
            auth_change_descr="maintainer migration initiated",
            auth_affected_mntner_id=str(new_auth_mntner.pk),
        )
    )
    return RedirectResponse(request.url_for("ui:user_permissions"), status_code=302)


class MntnerMigrateCompleteForm(StarletteForm):
    def __init__(self, *args, auth_mntner: AuthMntner, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_mntner = auth_mntner
        self.rpsl_mntner_obj = None

    mntner_password = wtforms.StringField(
        "Mntner password",
        description="One of the current passwords on the mntner",
        validators=[wtforms.validators.DataRequired()],
    )
    confirm = wtforms.BooleanField(
        "I understand that this migration can not be reversed", validators=[wtforms.validators.DataRequired()]
    )
    submit = wtforms.SubmitField("Migrate this mntner")

    async def validate(self):
        if not await super().validate():
            return False

        self.rpsl_mntner_obj = RPSLMntner(
            self.auth_mntner.rpsl_mntner_obj.object_text, strict_validation=False
        )
        valid_scheme = self.rpsl_mntner_obj.verify_auth(passwords=[self.mntner_password.data])
        if not valid_scheme:
            logger.info(
                f"invalid password provided for mntner {self.auth_mntner.rpsl_mntner_pk} while attempting to"
                " confirm migration"
            )
            self.mntner_password.errors.append("Invalid password for the methods on this mntner object.")
            return False

        return True


@rate_limit_post
@csrf_protect
@session_provider_manager
@authentication_required
async def mntner_migrate_complete(request: Request, session_provider: ORMSessionProvider) -> Response:
    """
    Complete maintainer migration that was previously initiated.
    Must be done by same user, and again requires existing mntner password.

    Completion consists of removing the migration token on the AuthMntner
    and adding IRRD-INTERNAL-AUTH to the auth: lines in the RPSL object.
    """
    query = session_provider.session.query(AuthMntner).join(AuthPermission)
    query = query.filter(
        AuthMntner.pk == str(request.path_params["pk"]),
        AuthMntner.migration_token == request.path_params["token"],
        AuthPermission.user_id == str(request.auth.user.pk),
        AuthPermission.user_management.is_(True),
    )
    auth_mntner = await session_provider.run(query.one)

    if not auth_mntner:
        return Response(status_code=404)
    form = await MntnerMigrateCompleteForm.from_formdata(request=request, auth_mntner=auth_mntner)
    if not form.is_submitted() or not await form.validate():
        form_html = render_form(form)
        return template_context_render(
            "mntner_migrate_complete.html", request, {"form_html": form_html, "auth_mntner": auth_mntner}
        )

    form.auth_mntner.migration_token = None
    session_provider.session.add(form.auth_mntner)

    form.rpsl_mntner_obj.add_irrd_internal_auth()
    session_provider.database_handler.upsert_rpsl_object(
        form.rpsl_mntner_obj, origin=JournalEntryOrigin.unknown
    )

    msg = textwrap.dedent("""
        The maintainer has been migrated to IRRD internal authentication.
        Existing authentication methods have been kept. 
    """)
    await notify_mntner(session_provider, request.auth.user, auth_mntner, explanation=msg)

    message(request, f"The mntner {auth_mntner.rpsl_mntner_pk} has been migrated.")
    logger.info(
        f"{client_ip_str(request)}{request.auth.user.email}: completed migration of"
        f" {auth_mntner.rpsl_mntner_pk}"
    )
    session_provider.session.add(
        ChangeLog(
            auth_by_user_id=str(request.auth.user.pk),
            auth_by_user_email=request.auth.user.email,
            auth_through_mntner_id=str(auth_mntner.pk),
            auth_through_rpsl_mntner_pk=str(auth_mntner.rpsl_mntner_pk),
            from_ip=client_ip(request),
            auth_change_descr="maintainer migration completed",
            auth_affected_mntner_id=str(auth_mntner.pk),
        )
    )
    return RedirectResponse(request.url_for("ui:user_permissions"), status_code=302)


async def notify_mntner(session_provider, user: AuthUser, mntner: AuthMntner, explanation: str):
    """
    Notify a mntner's contact of changes made to authentication.

    This is analogous to the notifications sent from irrd.updates.ChangeRequest,
    for completed migrations and permission add/remove.
    Mails are sent to the notify and mnt-nfy contacts.
    """
    query = session_provider.session.query(RPSLDatabaseObject).outerjoin(AuthMntner)
    query = query.filter(
        RPSLDatabaseObject.pk == str(mntner.rpsl_mntner_obj_id),
    )
    rpsl_mntner = await session_provider.run(query.one)
    recipients = set(rpsl_mntner.parsed_data.get("mnt-nfy", []) + rpsl_mntner.parsed_data.get("notify", []))

    subject = f"Notification of {mntner.rpsl_mntner_source} database changes"
    body = get_setting("email.notification_header", "").format(sources_str=mntner.rpsl_mntner_source)
    body += textwrap.dedent(f"""
        This message is auto-generated.
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        Internal authentication was changed for
        mntner {mntner.rpsl_mntner_pk} in source {mntner.rpsl_mntner_source}
        by user {user.name} ({user.email}).
    """)
    body += f"\n{explanation.strip()}\n"
    body += textwrap.dedent("""
        Note that this change is not visible in the RPSL object,
        as these authentication settings are stored internally in IRRD.
    """)
    for recipient in recipients:
        send_email(recipient, subject, body)


async def send_mntner_migrate_initiate_mail(
    session_provider, request: Request, new_auth_mntner: AuthMntner, affected_mntner: RPSLMntner
):
    """
    Send the mntner migration initiation mail.
    Looks at admin-c of the existing mntner, and then looks up all emails
    of all contacts, and mails them the token.
    """
    admin_cs = affected_mntner.parsed_data["admin-c"]
    query = session_provider.session.query(RPSLDatabaseObject)
    query = query.filter(
        RPSLDatabaseObject.rpsl_pk.in_(admin_cs),
        RPSLDatabaseObject.source == affected_mntner.source(),
    )
    recipients = {
        email
        for admin_c_obj in await session_provider.run(query.all)
        for email in admin_c_obj.parsed_data.get("e-mail", [])
    }
    for recipient in recipients:
        send_template_email(
            recipient,
            "mntner_migrate_initiate",
            request,
            {"auth_mntner": new_auth_mntner, "user": request.auth.user},
        )
