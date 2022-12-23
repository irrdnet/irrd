import enum


@enum.unique
class RoutePreferenceStatus(enum.Enum):
    visible = "VISIBLE"
    suppressed = "SUPPRESSED"

    @classmethod
    def is_visible(cls, status: "RoutePreferenceStatus"):
        return status == cls.visible
