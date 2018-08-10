import logging.config
import time
from typing import Any
import os

from dotted.collection import DottedDict

PASSWORD_HASH_DUMMY_VALUE = 'DummyValue'

DEFAULT_SETTINGS = DottedDict({
    'database_url': 'postgresql:///irrd',
    'server': {
        'whois': {
            'interface': '::0',
            'port': 8043,
            'max_connections': 50,
        }
    },
    'email': {
        'from': 'example@example.com',
        'footer': '',
        'smtp': 'localhost',
    },
    'gnupg': {
        'homedir': os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), '../gnupg/'),
    },
    'databases': {
        'NTTCOM': {
            'authoritative': True,
            # export schedule
        },
        'RADB': {
            'authoritative': False,
            'nrtm_host': 'whois.radb.net:43',
            'dump_source': 'ftp://ftp.radb.net/radb/dbase/radb.db.gz',
            'dump_serial_source': 'ftp://ftp.radb.net/radb/dbase/RADB.CURRENTSERIAL',
            # filter
        },
    }
})


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
        'passlib.registry': {
            'level': 'INFO',
            'propagate': True,
        },
        'gnupg': {
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
