from collections import defaultdict

from asgiref.sync import sync_to_async
from starlette.requests import Request
from starlette.responses import Response
from starlette_wtf import csrf_protect, csrf_token

from irrd import META_KEY_HTTP_CLIENT_IP
from irrd.conf import get_setting
from irrd.storage.models import (
    AuthMntner,
    AuthoritativeChangeOrigin,
    AuthPermission,
    AuthUser,
    ChangeLog,
    RPSLDatabaseObject,
)
from irrd.storage.orm_provider import ORMSessionProvider, session_provider_manager
from irrd.storage.queries import RPSLDatabaseQuery
from irrd.updates.handler import ChangeSubmissionHandler
from irrd.webui.auth.decorators import authentication_required, mark_user_mfa_incomplete
from irrd.webui.helpers import filter_auth_hash_non_mntner
from irrd.webui.rendering import template_context_render


async def index(request: Request) -> Response:
    """Index page with an explanation of this site."""
    mirrored_sources = [
        name for name, settings in get_setting("sources").items() if not settings.get("authoritative")
    ]
    return template_context_render(
        "index.html",
        request,
        {"mirrored_sources": mirrored_sources},
    )


@session_provider_manager
@authentication_required
async def user_permissions(request: Request, session_provider: ORMSessionProvider) -> Response:
    # The user detail page needs a rich and bound instance of AuthUser
    query = session_provider.session.query(AuthUser).filter_by(email=request.auth.user.email)
    bound_user = await session_provider.run(query.one)
    return template_context_render("user_permissions.html", request, {"user": bound_user})


@session_provider_manager
@authentication_required
async def maintained_objects(request: Request, session_provider: ORMSessionProvider) -> Response:
    """Show a user all objects with a mnt-by on which they have access."""
    user_mntners = [
        (mntner.rpsl_mntner_pk, mntner.rpsl_mntner_source) for mntner in request.auth.user.mntners
    ]
    if not user_mntners:
        return template_context_render(
            "maintained_objects.html",
            request,
            {
                "objects": None,
            },
        )
    user_mntbys, user_sources = zip(*user_mntners)
    q = RPSLDatabaseQuery().lookup_attrs_in(["mnt-by"], user_mntbys).sources(user_sources)
    query_result = list(session_provider.database_handler.execute_query(q))
    objects = filter(
        lambda obj: any([(mntby, obj["source"]) in user_mntners for mntby in obj["parsed_data"]["mnt-by"]]),
        query_result,
    )

    return template_context_render(
        "maintained_objects.html",
        request,
        {
            "objects": list(objects),
        },
    )


@mark_user_mfa_incomplete
@session_provider_manager
async def rpsl_detail(request: Request, user_mfa_incomplete: bool, session_provider: ORMSessionProvider):
    """Details for a single RPSL object. Auth hashes filtered by default."""
    if request.method == "GET":
        query = session_provider.session.query(RPSLDatabaseObject).filter(
            RPSLDatabaseObject.rpsl_pk == str(request.path_params["rpsl_pk"].upper()),
            RPSLDatabaseObject.object_class == str(request.path_params["object_class"].lower()),
            RPSLDatabaseObject.source == str(request.path_params["source"].upper()),
        )
        rpsl_object = await session_provider.run(query.one)
        if rpsl_object:
            rpsl_object.object_text_display = filter_auth_hash_non_mntner(
                None if user_mfa_incomplete else request.auth.user, rpsl_object
            )

        return template_context_render(
            "rpsl_detail.html",
            request,
            {
                "object": rpsl_object,
            },
        )


@csrf_protect
@mark_user_mfa_incomplete
@session_provider_manager
async def rpsl_update(
    request: Request, user_mfa_incomplete: bool, session_provider: ORMSessionProvider
) -> Response:
    """
    Web form for submitting RPSL updates.
    Essentially a wrapper around the same submission handlers as emails,
    but with pre-authentication through the logged in user or override.
    Can also be used anonymously.
    """
    active_user = request.auth.user if request.auth.is_authenticated and not user_mfa_incomplete else None
    mntner_perms = defaultdict(list)
    if active_user:
        for mntner in request.auth.user.mntners_user_management:
            mntner_perms[mntner.rpsl_mntner_source].append((mntner.rpsl_mntner_pk, True))
        for mntner in request.auth.user.mntners_no_user_management:
            mntner_perms[mntner.rpsl_mntner_source].append((mntner.rpsl_mntner_pk, False))

    if request.method == "GET":
        existing_data = ""
        if all([key in request.path_params for key in ["rpsl_pk", "object_class", "source"]]):
            query = session_provider.session.query(RPSLDatabaseObject).filter(
                RPSLDatabaseObject.rpsl_pk == str(request.path_params["rpsl_pk"].upper()),
                RPSLDatabaseObject.object_class == str(request.path_params["object_class"].lower()),
                RPSLDatabaseObject.source == str(request.path_params["source"].upper()),
            )
            obj = await session_provider.run(query.one)
            if obj:
                existing_data = filter_auth_hash_non_mntner(active_user, obj)

        return template_context_render(
            "rpsl_form.html",
            request,
            {
                "existing_data": existing_data,
                "status": None,
                "report": None,
                "mntner_perms": mntner_perms,
                "csrf_token": csrf_token(request),
            },
        )

    elif request.method == "POST":
        form_data = await request.form()
        request_meta = {
            META_KEY_HTTP_CLIENT_IP: request.client.host if request.client else "",
            "HTTP-User-Agent": request.headers.get("User-Agent"),
        }

        if active_user:
            request_meta["HTTP-User-Email"] = active_user.email
            request_meta["HTTP-User-ID"] = active_user.pk

        # ChangeSubmissionHandler builds its own DB connection
        # and therefore needs wrapping in a thread
        @sync_to_async
        def save():
            return ChangeSubmissionHandler().load_text_blob(
                object_texts_blob=form_data["data"],
                origin=AuthoritativeChangeOrigin.webui,
                request_meta=request_meta,
                internal_authenticated_user=active_user,
            )

        handler = await save()
        return template_context_render(
            "rpsl_form.html",
            request,
            {
                "existing_data": form_data["data"],
                "status": handler.status(),
                "report": handler.submitter_report_human(),
                "mntner_perms": mntner_perms,
                "csrf_token": csrf_token(request),
            },
        )
    return Response(status_code=405)  # pragma: no cover


@session_provider_manager
@authentication_required
async def change_log_mntner(request: Request, session_provider: ORMSessionProvider) -> Response:
    query = session_provider.session.query(AuthMntner).join(AuthPermission)
    query = query.filter(
        AuthMntner.pk == request.path_params["mntner"],
        AuthPermission.user_id == str(request.auth.user.pk),
        AuthPermission.user_management == True,  # noqa
    )
    mntner = await session_provider.run(query.one)
    if not mntner or not mntner.migration_complete:
        return Response(status_code=404)

    query = (
        session_provider.session.query(ChangeLog)
        .filter(
            (ChangeLog.auth_through_mntner_id == str(mntner.pk))
            | (
                (ChangeLog.auth_through_rpsl_mntner_pk == mntner.rpsl_mntner_pk)
                & (ChangeLog.rpsl_target_source == mntner.rpsl_mntner_source)
            )
        )
        .order_by(ChangeLog.timestamp.desc())
    )
    change_logs = await session_provider.run(query.all)

    return template_context_render(
        "change_log_mntner.html", request, {"mntner": mntner, "change_logs": change_logs}
    )


@session_provider_manager
@authentication_required
async def change_log_entry(request: Request, session_provider: ORMSessionProvider) -> Response:
    mntners = list(request.auth.user.mntners_user_management)
    if not mntners:
        return Response(status_code=404)

    query = session_provider.session.query(ChangeLog)
    query = query.filter(
        (ChangeLog.pk == request.path_params["entry"])
        & (
            (ChangeLog.auth_through_mntner_id.in_([str(mntner.pk) for mntner in mntners]))
            | (
                ChangeLog.auth_through_rpsl_mntner_pk.in_([mntner.rpsl_mntner_pk for mntner in mntners])
                & ChangeLog.rpsl_target_source.in_([mntner.rpsl_mntner_source for mntner in mntners])
            )
        )
    )
    entry = await session_provider.run(query.one)
    if not entry:
        return Response(status_code=404)

    return template_context_render("change_log_entry.html", request, {"entry": entry})
