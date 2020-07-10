import enum


class ScopeFilterStatus(enum.Enum):
    in_scope = 'IN_SCOPE'
    out_scope_as = 'OUT_SCOPE_AS'
    out_scope_prefix = 'OUT_SCOPE_PREFIX'
