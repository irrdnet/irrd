import logging.config
import time

import yaml
from IPy import IP
from typing import Any, List
import os

from dotted.collection import DottedDict

PASSWORD_HASH_DUMMY_VALUE = 'DummyValue'


class ConfigurationError(ValueError):
    pass


overrides = None


class Configuration:
    def __init__(self):
        default_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'default_config.yaml')
        default_config_yaml = yaml.safe_load(open(default_config_path))
        self.default_config = DottedDict(default_config_yaml['irrd'])

        self.staging_reload()
        errors = self.check_staging_config()
        if errors:
            error_str = "\n - ".join(errors)
            raise ConfigurationError(f'Errors found in settings, unable to start:\n - {error_str}')
        self.commit_staging()

    def staging_reload(self):
        user_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'testing_config.yaml')
        user_config_yaml = yaml.safe_load(open(user_config_path))
        self.user_config_staging = DottedDict(user_config_yaml['irrd'])

    def commit_staging(self):
        self.user_config_live = self.user_config_staging

    def get_setting_live(self, setting_name: str, default: Any=None) -> Any:
        env_key = 'IRRD_' + setting_name.upper().replace('.', '_')
        if env_key in os.environ:
            return os.environ[env_key]
        if overrides:
            try:
                return overrides[setting_name]
            except KeyError:
                pass
        # try:
        #     return self.user_config_live[setting_name]
        # except KeyError:
        #     return self.default_config.get(setting_name, default)
        return self.default_config.get(setting_name, default)

    def check_staging_config(self) -> List[str]:
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
        if not self._check_is_str(config, 'email.footer', required=False):
            errors.append(f'Setting email.footer must be a string.')

        if not self._check_is_str(config, 'auth.gnupg_keyring'):
            errors.append(f'Setting auth.gnupg_keyring is required.')

        access_lists = set(config.get('access_lists', {}).keys())
        unresolved_access_lists = {x for x in expected_access_lists.difference(access_lists) if x}
        if unresolved_access_lists:
            errors.append(f'Access lists {", ".join(unresolved_access_lists)} referenced in settings, but not defined.')

        for name, access_list in config.get('access_lists', {}).items():
            for item in access_list:
                try:
                    IP(item)
                except ValueError as ve:
                    errors.append(f'Invalid item in access list {name}: {ve}.')

        known_sources = set(config.get('sources').keys())
        unknown_default_sources = set(config.get('sources_default')).difference(known_sources)
        if unknown_default_sources:
            errors.append(f'Setting sources_default contains unknown sources: {", ".join(unknown_default_sources)}')

        for name, details in config.get('sources').items():
            nrtm_mirror = details.get('nrtm_host') and details.get('nrtm_port') and details.get('import_serial_source')
            if details.get('keep_journal') and not (nrtm_mirror or details.get('authoritative')):
                errors.append(f'Setting keep_journal for source {name} can not be enabled unless either authoritative '
                              f'is enabled, or all three of nrtm_host, nrtm_port and import_serial_source.')

        return errors

    def _check_is_str(self, config, key, required=True):
        if required:
            return config.get(key) and isinstance(config.get(key), str)
        return config.get(key) is None or isinstance(config.get(key), str)


configuration = Configuration()


def get_setting(setting_name: str, default: Any=None) -> Any:
    return configuration.get_setting_live(setting_name, default)


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s irrd[%(process)d]: [%(name)s#%(levelname)s] %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(name)s: %(message)s'
        },
    },
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'logging.NullHandler',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'loggers': {
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
        'irrd.storage': {
            'level': 'INFO',
            'propagate': True,
        },
        '': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    }
}

logging.config.dictConfig(LOGGING)
logging.Formatter.converter = time.gmtime
