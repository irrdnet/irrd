import logging.config
import time

import yaml
from typing import Any
import os

from dotted.collection import DottedDict

PASSWORD_HASH_DUMMY_VALUE = 'DummyValue'

default_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'default_config.yaml')
default_config_yaml = yaml.safe_load(open(default_config_path))
default_config = DottedDict(default_config_yaml['irrd'])

user_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'testing_config.yaml')
user_config_yaml = yaml.safe_load(open(user_config_path))
user_config = DottedDict(user_config_yaml['irrd'])


def get_setting(setting_name: str, default: Any=None) -> Any:
    env_key = 'IRRD_' + setting_name.upper().replace('.', '_')
    if env_key in os.environ:
        return os.environ[env_key]
    # try:
    #     return user_config[setting_name]
    # except KeyError:
    #     return default_config.get(setting_name, default)
    return default_config.get(setting_name, default)


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
