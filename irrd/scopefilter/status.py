import enum


@enum.unique
class ScopeFilterStatus(enum.Enum):
    in_scope = "IN_SCOPE"
    out_scope_as = "OUT_SCOPE_AS"
    out_scope_prefix = "OUT_SCOPE_PREFIX"

    @classmethod
    def is_visible(cls, status: "ScopeFilterStatus"):
        return status == cls.in_scope
