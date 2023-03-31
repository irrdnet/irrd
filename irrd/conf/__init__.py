import importlib.util
import logging.config
import os
import re
import signal
import sys
import time
from pathlib import Path
from typing import Any, List, Optional

import yaml
from IPy import IP

from irrd.vendor.dotted.collection import DottedDict

CONFIG_PATH_DEFAULT = "/etc/irrd.yaml"

logger = logging.getLogger(__name__)
PASSWORD_HASH_DUMMY_VALUE = "DummyValue"
SOURCE_NAME_RE = re.compile("^[A-Z][A-Z0-9-]*[A-Z0-9]$")
RPKI_IRR_PSEUDO_SOURCE = "RPKI"
ROUTEPREF_IMPORT_TIME = 3600
AUTH_SET_CREATION_COMMON_KEY = "COMMON"
SOCKET_DEFAULT_TIMEOUT = 30


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s irrd[%(process)d]: [%(name)s#%(levelname)s] %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "loggers": {
        # Tune down some very loud and not very useful loggers from libraries.
        "passlib.registry": {
            "level": "INFO",
        },
        "gnupg": {
            "level": "INFO",
        },
        # Must be specified explicitly to disable tracing middleware,
        # which adds substantial overhead
        "uvicorn.error": {
            "level": "INFO",
        },
        "sqlalchemy": {
            "level": "WARNING",
        },
        "": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}


logging.config.dictConfig(LOGGING)
logging.Formatter.converter = time.gmtime


class ConfigurationError(ValueError):
    pass


# testing_overrides can be set to a DottedDict, and is used
# to override settings while testing, using the config_override
# fixture.
testing_overrides: Any = None


class Configuration:
    """
    The Configuration class stores the current IRRD configuration,
    checks the validity of the settings, and offers graceful reloads.
    """

    user_config_staging: DottedDict
    user_config_live: DottedDict

    def __init__(self, user_config_path: Optional[str] = None, commit=True):
        """
        Load the default config and load and check the user provided config.
        If a logfile was specified, direct logs there.
        """
        from .known_keys import KNOWN_CONFIG_KEYS, KNOWN_SOURCES_KEYS

        self.known_config_keys = KNOWN_CONFIG_KEYS
        self.known_sources_keys = KNOWN_SOURCES_KEYS
        self.user_config_path = user_config_path if user_config_path else CONFIG_PATH_DEFAULT
        default_config_path = str(Path(__file__).resolve().parents[0] / "default_config.yaml")
        with open(default_config_path) as default_config:
            default_config_yaml = yaml.safe_load(default_config)
        self.default_config = DottedDict(default_config_yaml["irrd"])
        self.logging_config = LOGGING

        errors = self._staging_reload_check(log_success=False)
        if errors:
            raise ConfigurationError(f"Errors found in configuration, unable to start: {errors}")

        if commit:
            self._commit_staging()

            logging_config_path = self.get_setting_live("log.logging_config_path")
            logfile_path = self.get_setting_live("log.logfile_path")
            if logging_config_path:
                spec = importlib.util.spec_from_file_location("logging_config", logging_config_path)
                config_module = importlib.util.module_from_spec(spec)  # type: ignore
                spec.loader.exec_module(config_module)  # type: ignore
                self.logging_config = config_module.LOGGING  # type: ignore
                logging.config.dictConfig(self.logging_config)
            elif logfile_path:
                LOGGING["handlers"]["file"] = {  # type:ignore
                    "class": "logging.handlers.WatchedFileHandler",
                    "filename": logfile_path,
                    "formatter": "verbose",
                }
                # noinspection PyTypeChecker
                LOGGING["loggers"][""]["handlers"] = ["file"]  # type:ignore
                logging.config.dictConfig(LOGGING)

            # Re-commit to apply loglevel
            self._commit_staging()

    def get_setting_live(self, setting_name: str, default: Optional[Any] = None) -> Any:
        """
        Get a setting from the live config.
        In order, this will look in:
        - A env variable, uppercase and dots replaced by underscores, e.g.
          IRRD_SERVER_WHOIS_INTERFACE
        - The testing_overrides DottedDict
        - The live user config.
        - The default config.

        If it is not found in any, the value of the default paramater
        is returned, which is None by default.
        """
        if setting_name.startswith("sources"):
            components = setting_name.split(".")
            if len(components) == 3 and components[2] not in self.known_sources_keys:
                raise ValueError(f"Unknown setting {setting_name}")
        elif not setting_name.startswith("access_lists"):
            if self.known_config_keys.get(setting_name) is None:
                raise ValueError(f"Unknown setting {setting_name}")

        env_key = "IRRD_" + setting_name.upper().replace(".", "_")
        if env_key in os.environ:
            return os.environ[env_key]
        if testing_overrides:
            try:
                return testing_overrides[setting_name]
            except KeyError:
                pass
        try:
            return self.user_config_live[setting_name]
        except KeyError:
            return self.default_config.get(setting_name, default)

    def reload(self) -> bool:
        """
        Reload the configuration, if it passes the checks.
        """
        errors = self._staging_reload_check()
        if errors:
            logger.error(f"Errors found in configuration, continuing with current settings: {errors}")
            return False

        self._commit_staging()
        return True

    def _commit_staging(self) -> None:
        """
        Activate the current staging config as the live config.
        """
        self.user_config_live = self.user_config_staging
        logging.getLogger("").setLevel(self.get_setting_live("log.level", default="INFO"))
        if hasattr(sys, "_called_from_test"):
            logging.getLogger("").setLevel("DEBUG")

    def _staging_reload_check(self, log_success=True) -> List[str]:
        """
        Reload the staging configuration, and run the config checks on it.
        Returns a list of errors if any were found, or an empty list of the
        staging config is valid.
        """
        # While in testing, Configuration does not demand a valid config file
        # This simplifies test setup, as most tests do not need it.
        # If a non-default path is set during testing, it is still checked.
        if hasattr(sys, "_called_from_test") and self.user_config_path == CONFIG_PATH_DEFAULT:
            self.user_config_staging = DottedDict({})
            return []

        try:
            with open(self.user_config_path) as fh:
                user_config_yaml = yaml.safe_load(fh)
        except OSError as oe:
            return [f"Error opening config file {self.user_config_path}: {oe}"]
        except yaml.YAMLError as ye:
            return [f"Error parsing YAML file: {ye}"]

        if not isinstance(user_config_yaml, dict) or "irrd" not in user_config_yaml:
            return [f'Could not find root item "irrd" in config file {self.user_config_path}']
        self.user_config_staging = DottedDict(user_config_yaml["irrd"])

        errors = self._check_staging_config()
        if not errors and log_success:
            logger.info(
                f"Configuration successfully (re)loaded from {self.user_config_path} in PID {os.getpid()}"
            )
        return errors

    def _check_staging_config(self) -> List[str]:
        """
        Validate the current staging configuration.
        Returns a list of any errors, or an empty list for a valid config.
        """
        errors = []
        config = self.user_config_staging

        def _validate_subconfig(key, value):
            if isinstance(value, (DottedDict, dict)):
                for key2, value2 in value.items():
                    subkey = key + "." + key2
                    known_sub = self.known_config_keys.get(subkey)

                    if known_sub is None:
                        errors.append(f"Unknown setting key: {subkey}")
                    _validate_subconfig(subkey, value2)

        for key, value in config.items():
            if key in ["sources", "access_lists"]:
                continue
            if self.known_config_keys.get(key) is None:
                errors.append(f"Unknown setting key: {key}")
            _validate_subconfig(key, value)

        if not self._check_is_str(config, "database_url"):
            errors.append("Setting database_url is required.")

        if not self._check_is_str(config, "redis_url"):
            errors.append("Setting redis_url is required.")

        if not self._check_is_str(config, "piddir") or not os.path.isdir(config["piddir"]):
            errors.append("Setting piddir is required and must point to an existing directory.")

        if not str(config.get("route_object_preference.update_timer", "0")).isnumeric():
            errors.append("Setting route_object_preference.update_timer must be a number.")

        expected_access_lists = {
            config.get("server.whois.access_list"),
            config.get("server.http.status_access_list"),
        }

        if not self._check_is_str(config, "email.from") or "@" not in config.get("email.from", ""):
            errors.append("Setting email.from is required and must be an email address.")
        if not self._check_is_str(config, "email.smtp"):
            errors.append("Setting email.smtp is required.")
        if not self._check_is_str(
            config, "email.recipient_override", required=False
        ) or "@" not in config.get("email.recipient_override", "@"):
            errors.append("Setting email.recipient_override must be an email address if set.")

        string_not_required = [
            "email.footer",
            "server.whois.access_list",
            "server.http.status_access_list",
            "rpki.notify_invalid_subject",
            "rpki.notify_invalid_header",
            "rpki.slurm_source",
            "user",
            "group",
        ]
        for setting in string_not_required:
            if not self._check_is_str(config, setting, required=False):
                errors.append(f"Setting {setting} must be a string, if defined.")

        if bool(config.get("user")) != bool(config.get("group")):
            errors.append("Settings user and group must both be defined, or neither.")

        if not self._check_is_str(config, "auth.gnupg_keyring"):
            errors.append("Setting auth.gnupg_keyring is required.")

        from irrd.updates.parser_state import RPSLSetAutnumAuthenticationMode

        valid_auth = [mode.value for mode in RPSLSetAutnumAuthenticationMode]
        for set_name, params in config.get("auth.set_creation", {}).items():
            if not isinstance(params.get("prefix_required", False), bool):
                errors.append(f"Setting auth.set_creation.{set_name}.prefix_required must be a bool")
            if (
                params.get("autnum_authentication")
                and params["autnum_authentication"].lower() not in valid_auth
            ):
                errors.append(
                    f"Setting auth.set_creation.{set_name}.autnum_authentication must be one of"
                    f" {valid_auth} if set"
                )

        from irrd.rpsl.passwords import PasswordHasherAvailability

        valid_hasher_availability = [avl.value for avl in PasswordHasherAvailability]
        for hasher_name, setting in config.get("auth.password_hashers", {}).items():
            if setting.lower() not in valid_hasher_availability:
                errors.append(
                    f"Setting auth.password_hashers.{hasher_name} must be one of {valid_hasher_availability}"
                )

        for name, access_list in config.get("access_lists", {}).items():
            for item in access_list:
                try:
                    IP(item)
                except ValueError as ve:
                    errors.append(f"Invalid item in access list {name}: {ve}.")

        for prefix in config.get("scopefilter.prefixes", []):
            try:
                IP(prefix)
            except ValueError as ve:
                errors.append(f"Invalid item in prefix scopefilter: {prefix}: {ve}.")

        for asn in config.get("scopefilter.asns", []):
            try:
                if "-" in str(asn):
                    first, last = asn.split("-")
                    int(first)
                    int(last)
                else:
                    int(asn)
            except ValueError:
                errors.append(f"Invalid item in asn scopefilter: {asn}.")

        known_sources = set(config.get("sources", {}).keys())

        has_authoritative_sources = False
        for name, details in config.get("sources", {}).items():
            unknown_keys = set(details.keys()) - self.known_sources_keys
            if unknown_keys:
                errors.append(f'Unknown key(s) under source {name}: {", ".join(unknown_keys)}')
            if details.get("authoritative"):
                has_authoritative_sources = True
            if config.get("rpki.roa_source") and name == RPKI_IRR_PSEUDO_SOURCE:
                errors.append(f"Setting sources contains reserved source name: {RPKI_IRR_PSEUDO_SOURCE}")
            if not SOURCE_NAME_RE.match(name):
                errors.append(f"Invalid source name: {name}")

            if details.get("suspension_enabled") and not details.get("authoritative"):
                errors.append(
                    f"Setting suspension_enabled for source {name} can not be enabled without enabling "
                    "authoritative."
                )

            nrtm_mirror = details.get("nrtm_host") and details.get("import_serial_source")
            if details.get("keep_journal") and not (nrtm_mirror or details.get("authoritative")):
                errors.append(
                    f"Setting keep_journal for source {name} can not be enabled unless either authoritative "
                    "is enabled, or all three of nrtm_host, nrtm_port and import_serial_source."
                )
            if details.get("nrtm_host") and not details.get("import_serial_source"):
                errors.append(
                    f"Setting nrtm_host for source {name} can not be enabled without setting "
                    "import_serial_source."
                )

            if details.get("authoritative") and (details.get("nrtm_host") or details.get("import_source")):
                errors.append(
                    f"Setting authoritative for source {name} can not be enabled when either "
                    "nrtm_host or import_source are set."
                )

            if config.get("database_readonly") and (
                details.get("authoritative") or details.get("nrtm_host") or details.get("import_source")
            ):
                errors.append(
                    f"Source {name} can not have authoritative, import_source or nrtm_host set "
                    "when database_readonly is enabled."
                )

            number_fields = [
                "nrtm_port",
                "import_timer",
                "export_timer",
                "route_object_preference",
                "nrtm_query_serial_range_limit",
            ]
            for field_name in number_fields:
                if not str(details.get(field_name, 0)).isnumeric():
                    errors.append(f"Setting {field_name} for source {name} must be a number.")

            if details.get("nrtm_access_list"):
                expected_access_lists.add(details.get("nrtm_access_list"))
            if details.get("nrtm_access_list_unfiltered"):
                expected_access_lists.add(details.get("nrtm_access_list_unfiltered"))

        if config.get("rpki.roa_source", "https://rpki.gin.ntt.net/api/export.json"):
            known_sources.add(RPKI_IRR_PSEUDO_SOURCE)
            if has_authoritative_sources and config.get("rpki.notify_invalid_enabled") is None:
                errors.append(
                    "RPKI-aware mode is enabled and authoritative sources are configured, "
                    "but rpki.notify_invalid_enabled is not set. Set to true or false."
                    "DANGER: care is required with this setting in testing setups with "
                    "live data, as it may send bulk emails to real resource contacts "
                    "unless email.recipient_override is also set. "
                    "Read documentation carefully."
                )

        unknown_default_sources = set(config.get("sources_default", [])).difference(known_sources)
        if unknown_default_sources:
            errors.append(
                f'Setting sources_default contains unknown sources: {", ".join(unknown_default_sources)}'
            )

        if not str(config.get("rpki.roa_import_timer", "0")).isnumeric():
            errors.append("Setting rpki.roa_import_timer must be set to a number.")

        if config.get("log.level") and not config.get("log.level") in [
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ]:
            errors.append(
                f'Invalid log.level: {config.get("log.level")}. '
                "Valid settings for log.level are `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`."
            )
        if config.get("log.logging_config_path") and (
            config.get("log.logfile_path") or config.get("log.level")
        ):
            errors.append(
                "Setting log.logging_config_path can not be combined withlog.logfile_path or log.level"
            )

        access_lists = set(config.get("access_lists", {}).keys())
        unresolved_access_lists = [
            x for x in expected_access_lists.difference(access_lists) if x and isinstance(x, str)
        ]
        unresolved_access_lists.sort()
        if unresolved_access_lists:
            errors.append(
                f'Access lists {", ".join(unresolved_access_lists)} referenced in settings, but not defined.'
            )

        return errors

    def _check_is_str(self, config, key, required=True):
        if required:
            return config.get(key) and isinstance(config.get(key), str)
        return config.get(key) is None or isinstance(config.get(key), str)


configuration: Optional[Configuration] = None


def get_configuration() -> Optional[Configuration]:
    """
    Get the Configuration object, if initialised.
    """
    global configuration
    return configuration


def config_init(config_path, commit=True) -> None:
    """
    Initialise the configuration from a configuration path.
    If commit is False, only validates the configuration.
    """
    global configuration
    configuration = Configuration(config_path, commit)


def is_config_initialised() -> bool:
    """
    Returns whether the configuration is initialised,
    i.e. whether get_setting() can be called.
    """
    configuration = get_configuration()
    return configuration is not None


def get_setting(setting_name: str, default: Optional[Any] = None) -> Any:
    """
    Convenience wrapper to get the value of a setting.
    """
    configuration = get_configuration()
    if not configuration:  # pragma: no cover
        raise Exception("get_setting() called before configuration was initialised")
    return configuration.get_setting_live(setting_name, default)


def sighup_handler(signum, frame) -> None:
    """
    Reload the settings when a SIGHUP is received.
    Note that not all processes re-read their settings on every run,
    so not all settings can be changed while running.
    """
    configuration = get_configuration()
    if configuration:
        configuration.reload()


signal.signal(signal.SIGHUP, sighup_handler)
