from starlette.requests import Request
from starlette.responses import Response

from irrd.storage.models import AuthMntner, AuthPermission, ChangeLog
from irrd.storage.orm_provider import ORMSessionProvider, session_provider_manager
from irrd.webui.auth.decorators import authentication_required
from irrd.webui.rendering import template_context_render


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
    mntners = list(request.auth.user.mntners)
    if not mntners:
        return Response(status_code=404)

    query = session_provider.session.query(ChangeLog)
    query = query.filter(
        ChangeLog.pk == request.path_params["entry"],
        AuthPermission.user_id == str(request.auth.user.pk),
        AuthPermission.user_management == True,  # noqa
    ).filter(
        (ChangeLog.auth_through_mntner_id.in_([str(mntner.pk) for mntner in mntners]))
        | (
            ChangeLog.auth_through_rpsl_mntner_pk.in_([mntner.rpsl_mntner_pk for mntner in mntners])
            & ChangeLog.rpsl_target_source.in_([mntner.rpsl_mntner_source for mntner in mntners])
        )
    )
    entry = await session_provider.run(query.one)
    if not entry:
        return Response(status_code=404)

    return template_context_render("change_log_entry.html", request, {"entry": entry})
