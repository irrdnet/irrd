import functools
import logging
from typing import Any, Dict, Optional

import limits
from starlette.requests import Request
from starlette.responses import Response

from irrd.conf import get_setting
from irrd.storage.models import AuthUser, RPSLDatabaseObject
from irrd.utils.email import send_email
from irrd.utils.text import remove_auth_hashes
from irrd.webui import RATE_LIMIT_POST_200_NAMESPACE, templates

logger = logging.getLogger(__name__)


def rate_limit_post(_func=None, any_response_code=False):
    """
    Rate limiting decorator for POST to HTTP endpoints.

    Hits are counted for any POST request, when the response is 200
    (typical for failed form submissions) or when any_response_code
    is set. If the limit is exceeded, further POST requests are rejected.
    Typical use is any form that requires a user's current password.
    As this is a broad hit filter, do not set too strict.

    No impact on GET requests.
    All endpoints share the same rate limiter.
    """

    def decorator_wrapper(func):
        @functools.wraps(func)
        async def endpoint_wrapper(*args, **kwargs):
            rate_limit = limits.parse(get_setting("auth.webui_auth_failure_rate_limit"))
            request = next(
                (arg for arg in list(args) + list(kwargs.values()) if isinstance(arg, Request)), None
            )

            if request and request.method == "POST":
                limiter = request.app.state.rate_limiter
                permitted = await limiter.test(rate_limit, RATE_LIMIT_POST_200_NAMESPACE, request.client.host)
                if not permitted:
                    logger.info(f"{client_ip(request)}rejecting request due to rate limiting")
                    return Response("Request denied due to rate limiting", status_code=403)

                response = await func(*args, **kwargs)

                if any_response_code or response.status_code == 200:
                    await limiter.hit(rate_limit, RATE_LIMIT_POST_200_NAMESPACE, request.client.host)
            else:
                response = await func(*args, **kwargs)

            return response

        return endpoint_wrapper

    if _func is None:
        return decorator_wrapper
    else:
        return decorator_wrapper(_func)


# From https://github.com/accent-starlette/starlette-core/
def message(request: Request, message: Any, category: str = "success") -> None:
    """
    Save a message on the request, to be rendered in the next template render.
    """
    if category not in ["info", "success", "danger", "warning"]:
        raise ValueError(f"Unknown category: {category}")  # pragma: no cover
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": message, "category": category})


# From https://github.com/accent-starlette/starlette-core/
def get_messages(request: Request):
    return request.session.pop("_messages") if "_messages" in request.session else []


def send_template_email(
    recipient: str, template_key: str, request: Optional[Request], template_kwargs: Dict[str, Any]
) -> None:
    """
    Send an email rendered from a template.
    Expects {key}_mail_subject.txt and {key}_mail.txt as templates.
    """
    subject = templates.get_template(f"{template_key}_mail_subject.txt").render(
        request=request, **template_kwargs
    )
    body = templates.get_template(f"{template_key}_mail.txt").render(request=request, **template_kwargs)
    send_email(recipient, subject, body)
    logger.info(f"{client_ip(request)}email sent to {recipient}: {subject}")


def send_authentication_change_mail(
    user: AuthUser, request: Optional[Request], msg: str, recipient_override: Optional[str] = None
) -> None:
    """
    Email a user that authentication data has changed.
    Used for password changes, 2FA changes, etc.
    """
    recipient = recipient_override if recipient_override else user.email
    send_template_email(
        recipient,
        "authentication_change",
        request,
        {"url": get_setting("server.http.url"), "user": user, "msg": msg},
    )


def filter_auth_hash_non_mntner(user: Optional[AuthUser], rpsl_object: RPSLDatabaseObject) -> str:
    """
    Filter the auth hashes from rpsl_object unless user is a user_management mntner for it.
    Returns the modified text, and sets hashes_hidden on the object.
    """
    if user and user.get_id():
        user_mntners = [
            (mntner.rpsl_mntner_pk, mntner.rpsl_mntner_source) for mntner in user.mntners_user_management
        ]

        if rpsl_object.object_class != "mntner" or (rpsl_object.rpsl_pk, rpsl_object.source) in user_mntners:
            rpsl_object.hashes_hidden = False
            return rpsl_object.object_text

    rpsl_object.hashes_hidden = True
    return remove_auth_hashes(rpsl_object.object_text)


def client_ip(request: Optional[Request]) -> str:
    """Small wrapper to get the client IP from a request."""
    if request and request.client:
        return f"{request.client.host}: "
    return ""  # pragma: no cover
