from enum import Enum, unique

from irrd.conf import AUTH_SET_CREATION_COMMON_KEY, get_setting


@unique
class UpdateRequestType(Enum):
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


class SuspensionRequestType(Enum):
    SUSPEND = "suspend"
    REACTIVATE = "reactivate"


@unique
class UpdateRequestStatus(Enum):
    SAVED = "saved"
    PROCESSING = "processing"
    ERROR_UNKNOWN_CLASS = "error: unknown RPSL class"
    ERROR_PARSING = "errors encountered during object parsing"
    ERROR_AUTH = "error: update not authorised"
    ERROR_RULES = "error: other rules not met"
    ERROR_REFERENCE = "error: reference to object that does not exist"
    ERROR_ROA = "error: conflict with existing ROA"
    ERROR_SCOPEFILTER = "error: not in scope"
    ERROR_NON_AUTHORITIVE = "error: attempt to update object in non-authoritive database"


@unique
class RPSLSetAutnumAuthenticationMode(Enum):
    DISABLED = "disabled"
    OPPORTUNISTIC = "opportunistic"
    REQUIRED = "required"

    @staticmethod
    def for_set_name(set_name: str):
        setting = get_setting(f"auth.set_creation.{set_name}.autnum_authentication")
        if not setting:
            setting = get_setting(f"auth.set_creation.{AUTH_SET_CREATION_COMMON_KEY}.autnum_authentication")
        return getattr(RPSLSetAutnumAuthenticationMode, setting.upper())
