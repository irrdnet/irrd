import datetime
from pathlib import Path

from starlette.templating import Jinja2Templates

import irrd

UI_DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M"
RATE_LIMIT_POST_200_NAMESPACE = "irrd-http-post-200-response"
MFA_COMPLETE_SESSION_KEY = "auth-mfa-complete"
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def datetime_format(value: datetime.datetime, format=UI_DEFAULT_DATETIME_FORMAT):
    return value.astimezone(datetime.timezone.utc).strftime(format)


templates.env.globals["irrd_version"] = irrd.__version__
templates.env.filters["datetime_format"] = datetime_format
