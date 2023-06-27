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

    query = session_provider.session.query(ChangeLog).filter(
        (ChangeLog.auth_through_mntner_id == str(mntner.pk))
        | (
            (ChangeLog.auth_through_rpsl_mntner_pk == str(mntner.rpsl_mntner_pk))
            & (ChangeLog.rpsl_target_source == mntner.rpsl_mntner_source)
        )
    )
    change_logs = await session_provider.run(query.all)

    return template_context_render(
        "change_log_mntner.html", request, {"mntner": mntner, "change_logs": change_logs}
    )
