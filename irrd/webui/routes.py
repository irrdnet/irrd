from starlette.routing import Mount, Route

from irrd.webui.auth.routes import AUTH_ROUTES
from irrd.webui.endpoints import (
    change_log_entry,
    change_log_mntner,
    index,
    maintained_objects,
    rpsl_detail,
    rpsl_update,
    user_permissions,
)
from irrd.webui.endpoints_mntners import (
    api_token_add,
    api_token_delete,
    api_token_edit,
    mntner_migrate_complete,
    mntner_migrate_initiate,
    permission_add,
    permission_delete,
)

UI_ROUTES = [
    Route("/", index, name="index"),
    Route("/maintained-objects/", maintained_objects, name="maintained_objects"),
    Route(
        "/rpsl/update/{source}/{object_class}/{rpsl_pk:path}/",
        rpsl_update,
        name="rpsl_update",
        methods=["GET", "POST"],
    ),
    Route("/rpsl/update/", rpsl_update, name="rpsl_update", methods=["GET", "POST"]),
    Route("/rpsl/{source}/{object_class}/{rpsl_pk:path}/", rpsl_detail, name="rpsl_detail"),
    Route(
        "/migrate-mntner/", mntner_migrate_initiate, name="mntner_migrate_initiate", methods=["GET", "POST"]
    ),
    Route(
        "/migrate-mntner/complete/{pk:uuid}/{token}/",
        mntner_migrate_complete,
        name="mntner_migrate_complete",
        methods=["GET", "POST"],
    ),
    Route("/user/", user_permissions, name="user_permissions"),
    Route("/permission/add/{mntner:uuid}/", permission_add, name="permission_add", methods=["GET", "POST"]),
    Route(
        "/permission/delete/{permission:uuid}/",
        permission_delete,
        name="permission_delete",
        methods=["GET", "POST"],
    ),
    Route("/api_token/add/{mntner:uuid}/", api_token_add, name="api_token_add", methods=["GET", "POST"]),
    Route("/api_token/edit/{token_pk:uuid}/", api_token_edit, name="api_token_edit", methods=["GET", "POST"]),
    Route(
        "/api_token/delete/{token_pk:uuid}/",
        api_token_delete,
        name="api_token_delete",
        methods=["GET", "POST"],
    ),
    Route("/change-log/{mntner:uuid}/", change_log_mntner, name="change_log_mntner"),
    Route("/change-log/entry/{entry:uuid}/", change_log_entry, name="change_log_entry"),
    Mount("/auth", name="auth", routes=AUTH_ROUTES),
]
