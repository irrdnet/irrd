import enum


class RPKIStatus(enum.Enum):
    valid = 'VALID'
    invalid = 'INVALID'
    unknown = 'UNKNOWN'
