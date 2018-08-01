import logging.config
import time
from typing import Any
import os

DEFAULT_SETTINGS = {
    'database_url': 'postgresql:///irrd',
    'server.whois.interface': '::0',
    'server.whois.port': 8043,
    'server.whois.max_connections': 50,
    'gnupg.homedir': os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), '../gnupg/'),
    'email.from': 'example@example.com',
    'email.footer': '',
    'email.smtp': 'localhost',
}


def get_setting(setting_name: str) -> Any:
    default = DEFAULT_SETTINGS.get(setting_name)
    env_key = 'IRRD_' + setting_name.upper().replace('.', '_')
    if env_key in os.environ:
        return os.environ[env_key]
    return default


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
        '': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    }
}

logging.config.dictConfig(LOGGING)
logging.Formatter.converter = time.gmtime
