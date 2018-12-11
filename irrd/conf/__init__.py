import sys

import logging.config
import time

import signal
import yaml
from IPy import IP
from typing import Any, List
import os

from dotted.collection import DottedDict

IRRD_CONFIG_PATH_ENV = 'IRRD_CONFIG_PATH'
IRRD_CONFIG_CHECK_FORCE_ENV = 'IRRD_CONFIG_CHECK_FORCE'

logger = logging.getLogger(__name__)
PASSWORD_HASH_DUMMY_VALUE = 'DummyValue'


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s irrd[%(process)d]: [%(name)s#%(levelname)s] %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'loggers': {
        # Tune down some very loud and not very useful loggers from libraries.
        'passlib.registry': {
            'level': 'INFO',
            'propagate': True,
        },
        'gnupg': {
            'level': 'INFO',
            'propagate': True,
        },
        'sqlalchemy': {
            'level': 'WARNING',
            'propagate': True,
        },
        '': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    }
}


logging.config.dictConfig(LOGGING)
logging.Formatter.converter = time.gmtime


class ConfigurationError(ValueError):
    pass


# testing_overrides can be set to a DottedDict, and is used
# to override settings while testing, using the config_override
# fixture.
testing_overrides = None


class Configuration:
    """
    The Configuration class stores the current IRRD configuration,
    checks the validity of the settings, and offers graceful reloads.
    """
    user_config_staging: DottedDict
    user_config_live: DottedDict

    def __init__(self):
        """
        Load the default config and load and check the user provided config.
        If a logfile was specified, direct logs there.
        """
        default_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'default_config.yaml')
        default_config_yaml = yaml.safe_load(open(default_config_path))
        self.default_config = DottedDict(default_config_yaml['irrd'])

        errors = self._staging_reload_check()
        if errors:
            raise ConfigurationError(f'Errors found in configuration, unable to start: {errors}')
        self._commit_staging()

        logfile_path = self.get_setting_live('log.logfile_path')
        if logfile_path:
            LOGGING['handlers']['file'] = {
                'class': 'logging.handlers.WatchedFileHandler',
                'filename': logfile_path,
                'formatter': 'verbose',
            }
            # noinspection PyTypeChecker
            LOGGING['loggers']['']['handlers'] = ['file']
            logging.config.dictConfig(LOGGING)

    def get_setting_live(self, setting_name: str, default: Any=None) -> Any:
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
        env_key = 'IRRD_' + setting_name.upper().replace('.', '_')
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
            logger.error(f'Errors found in configuration, continuing with current settings: {errors}')
            return False

        self._commit_staging()
        return True

    def _commit_staging(self):
        """
        Activate the current staging config as the live config.
        """
        self.user_config_live = self.user_config_staging
        logging.getLogger('').setLevel(self.get_setting_live('log.level', default='INFO'))

    def _staging_reload_check(self) -> List[str]:
        """
        Reload the staging configuration, and run the config checks on it.
        Returns a list of errors if any were found, or an empty list of the
        staging config is valid.
        """
        # While in testing, Configuration does not demand a valid config file
        # in IRRD_CONFIG_PATH_ENV. This simplifies test setup, as most tests
        # do not need it. If IRRD_CONFIG_PATH_ENV is set, it is checked,
        # and the check is forced with IRRD_CONFIG_CHECK_FORCE_ENV (to test
        # the error message for the empty environment variable).
        if all([
            hasattr(sys, '_called_from_test'),
            IRRD_CONFIG_PATH_ENV not in os.environ,
            IRRD_CONFIG_CHECK_FORCE_ENV not in os.environ
        ]):
            self.user_config_staging = DottedDict({})
            return []

        try:
            user_config_path = os.environ[IRRD_CONFIG_PATH_ENV]
        except KeyError:
            return [f'Environment variable {IRRD_CONFIG_PATH_ENV} not set.']

        try:
            user_config_yaml = yaml.safe_load(open(user_config_path))
        except OSError as oe:
            return [f'Error opening config file {user_config_path}: {oe}']
        except yaml.YAMLError as ye:
            return [f'Error parsing YAML file: {ye}']

        if not isinstance(user_config_yaml, dict) or 'irrd' not in user_config_yaml:
            return [f'Could not find root item "irrd" in config file {user_config_path}']
        self.user_config_staging = DottedDict(user_config_yaml['irrd'])

        errors = self._check_staging_config()
        if not errors:
            logger.info(f'Configuration successfully (re)loaded from {user_config_path}')
        return errors

    def _check_staging_config(self) -> List[str]:
        """
        Validate the current staging configuration.
        Returns a list of any errors, or an empty list for a valid config.
        """
        errors = []

        config = self.user_config_staging

        if not self._check_is_str(config, 'database_url'):
            errors.append(f'Setting database_url is required.')

        expected_access_lists = {
            config.get('server.whois.access_list'),
            config.get('server.http.access_list'),
        }

        if not self._check_is_str(config, 'email.from') or '@' not in config.get('email.from'):
            errors.append(f'Setting email.from is required and must be an email address.')
        if not self._check_is_str(config, 'email.smtp'):
            errors.append(f'Setting email.smtp is required.')

        string_not_required = ['email.footer', 'server.whois.access_list', 'server.http.access_list']
        for setting in string_not_required:
            if not self._check_is_str(config, setting, required=False):
                errors.append(f'Setting {setting} must be a string, if defined.')

        if not self._check_is_str(config, 'auth.gnupg_keyring'):
            errors.append(f'Setting auth.gnupg_keyring is required.')

        access_lists = set(config.get('access_lists', {}).keys())
        unresolved_access_lists = {x for x in expected_access_lists.difference(access_lists) if x and isinstance(x, str)}
        if unresolved_access_lists:
            errors.append(f'Access lists {", ".join(unresolved_access_lists)} referenced in settings, but not defined.')

        for name, access_list in config.get('access_lists', {}).items():
            for item in access_list:
                try:
                    IP(item)
                except ValueError as ve:
                    errors.append(f'Invalid item in access list {name}: {ve}.')

        known_sources = set(config.get('sources', {}).keys())
        unknown_default_sources = set(config.get('sources_default', [])).difference(known_sources)
        if unknown_default_sources:
            errors.append(f'Setting sources_default contains unknown sources: {", ".join(unknown_default_sources)}')

        for name, details in config.get('sources', {}).items():
            nrtm_mirror = details.get('nrtm_host') and details.get('nrtm_port') and details.get('import_serial_source')
            if details.get('keep_journal') and not (nrtm_mirror or details.get('authoritative')):
                errors.append(f'Setting keep_journal for source {name} can not be enabled unless either authoritative '
                              f'is enabled, or all three of nrtm_host, nrtm_port and import_serial_source.')

        if config.get('log.level') and not config.get('log.level') in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            errors.append(f'Invalid log.level: {config.get("log.level")}. '
                          f'Valid settings for log.level are `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.')

        return errors

    def _check_is_str(self, config, key, required=True):
        if required:
            return config.get(key) and isinstance(config.get(key), str)
        return config.get(key) is None or isinstance(config.get(key), str)


configuration = None


def get_setting(setting_name: str, default: Any=None) -> Any:
    """
    Convenience wrapper to get the value of a setting.
    Creates a Configuration object if none exists, and
    retrieves the live setting from that object.
    """
    global configuration
    if not configuration:
        configuration = Configuration()
    return configuration.get_setting_live(setting_name, default)


def sighup_handler(signum, frame):
    """
    Reload the settings when a SIGHUP is received.
    Note that not all processes re-read their settings on every run,
    so not all settings can be changed while running.
    """
    global configuration
    if not configuration:  # pragma: no cover
        configuration = Configuration()
    configuration.reload()


signal.signal(signal.SIGHUP, sighup_handler)
