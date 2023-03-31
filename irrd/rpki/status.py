import enum


@enum.unique
class RPKIStatus(enum.Enum):
    valid = "VALID"
    invalid = "INVALID"
    not_found = "NOT_FOUND"

    @classmethod
    def is_visible(cls, status: "RPKIStatus"):
        return status in (cls.valid, cls.not_found)
