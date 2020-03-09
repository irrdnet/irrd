import enum


class RPKIStatus(enum.Enum):
    valid = 'VALID'
    invalid = 'INVALID'
    not_found = 'NOT_FOUND'
