from irrd.conf import AUTH_SET_CREATION_COMMON_KEY
from irrd.rpsl.passwords import PASSWORD_HASHERS_ALL
from irrd.rpsl.rpsl_objects import OBJECT_CLASS_MAPPING, RPSLSet
from irrd.vendor.dotted.collection import DottedDict

# Note that sources are checked separately,
# and 'access_lists' is always permitted
KNOWN_CONFIG_KEYS = DottedDict(
    {
        "database_url": {},
        "database_readonly": {},
        "redis_url": {},
        "piddir": {},
        "user": {},
        "group": {},
        "server": {
            "http": {
                "interface": {},
                "port": {},
                "status_access_list": {},
                "event_stream_access_list": {},
                "workers": {},
                "forwarded_allowed_ips": {},
            },
            "whois": {
                "interface": {},
                "port": {},
                "access_list": {},
                "max_connections": {},
            },
        },
        "route_object_preference": {"update_timer": {}},
        "email": {
            "from": {},
            "footer": {},
            "smtp": {},
            "recipient_override": {},
            "notification_header": {},
        },
        "auth": {
            "override_password": {},
            "authenticate_parents_route_creation": {},
            "gnupg_keyring": {},
            "set_creation": {
                rpsl_object_class: {"prefix_required": {}, "autnum_authentication": {}}
                for rpsl_object_class in [
                    set_object.rpsl_object_class
                    for set_object in OBJECT_CLASS_MAPPING.values()
                    if issubclass(set_object, RPSLSet)
                ]
                + [AUTH_SET_CREATION_COMMON_KEY]
            },
            "password_hashers": {hasher_name.lower(): {} for hasher_name in PASSWORD_HASHERS_ALL.keys()},
        },
        "rpki": {
            "roa_source": {},
            "roa_import_timer": {},
            "slurm_source": {},
            "pseudo_irr_remarks": {},
            "notify_invalid_enabled": {},
            "notify_invalid_subject": {},
            "notify_invalid_header": {},
        },
        "scopefilter": {
            "prefixes": {},
            "asns": {},
        },
        "log": {
            "logfile_path": {},
            "level": {},
            "logging_config_path": {},
        },
        "sources_default": {},
        "compatibility": {
            "inetnum_search_disabled": {},
            "ipv4_only_route_set_members": {},
        },
    }
)

KNOWN_SOURCES_KEYS = {
    "authoritative",
    "keep_journal",
    "nrtm_host",
    "nrtm_port",
    "import_source",
    "import_serial_source",
    "import_timer",
    "object_class_filter",
    "export_destination",
    "export_destination_unfiltered",
    "export_timer",
    "nrtm_access_list",
    "nrtm_access_list_unfiltered",
    "nrtm_query_serial_range_limit",
    "strict_import_keycert_objects",
    "rpki_excluded",
    "scopefilter_excluded",
    "suspension_enabled",
    "route_object_preference",
}
