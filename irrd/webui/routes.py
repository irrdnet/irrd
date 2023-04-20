from starlette.routing import Mount, Route

from irrd.webui.auth.routes import AUTH_ROUTES
from irrd.webui.endpoints import (
    index,
    maintained_objects,
    rpsl_detail,
    rpsl_update,
    user_permissions,
)
from irrd.webui.endpoints_mntners import (
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
        "/migrate-mntner/",
        mntner_migrate_initiate,
        name="mntner_migrate_initiate",
        methods=["GET", "POST"],
    ),
    Route(
        "/migrate-mntner/complete/{pk:uuid}/{token}/",
        mntner_migrate_complete,
        name="mntner_migrate_complete",
        methods=["GET", "POST"],
    ),
    Route("/user/", user_permissions, name="user_permissions"),
    Route(
        "/permission/add/{mntner:uuid}/",
        permission_add,
        name="permission_add",
        methods=["GET", "POST"],
    ),
    Route(
        "/permission/delete/{permission:uuid}/",
        permission_delete,
        name="permission_delete",
        methods=["GET", "POST"],
    ),
    Mount("/auth", name="auth", routes=AUTH_ROUTES),
]
