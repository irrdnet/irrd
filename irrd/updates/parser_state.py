from enum import unique, Enum


@unique
class UpdateRequestType(Enum):
    CREATE = 'create'
    MODIFY = 'modify'
    DELETE = 'delete'


@unique
class UpdateRequestStatus(Enum):
    SAVED = 'saved'
    PROCESSING = 'processing'
    ERROR_UNKNOWN_CLASS = 'error: unknown RPSL class'
    ERROR_PARSING = 'errors encountered during object parsing'
    ERROR_AUTH = 'error: update not authorised'
    ERROR_REFERENCE = 'error: reference to object that does not exist'
    ERROR_ROA = 'error: conflict with existing ROA'
    ERROR_SCOPEFILTER = 'error: not in scope'
    ERROR_NON_AUTHORITIVE = 'error: attempt to update object in non-authoritive database'
