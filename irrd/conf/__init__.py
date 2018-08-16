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
    # TODO: rename to sources
    'databases': {
        # 'AFRINIC': {
        #     'authoritative': False,
        #     'dump_source': 'http://ftp.afrinic.net/pub/dbase/afrinic.db.gz',
        #     'dump_serial_source': 'http://ftp.afrinic.net/pub/dbase/AFRINIC.CURRENTSERIAL',
        # },
        # ALTDB FTP is dead
        # APNIC only has split files
        'ARIN': {
            'authoritative': False,
            'keep_journal': True,
            'nrtm_host': 'rr.arin.net',
            'nrtm_port': 4444,
            'dump_source': 'ftp://ftp.arin.net/pub/rr/arin.db',
            'dump_serial_source': 'ftp://ftp.arin.net/pub/rr/ARIN.CURRENTSERIAL',
        },
        # ARIN-WHOIS source unknown
        'BBOI': {
            'authoritative': False,
            'nrtm_host': 'irr.bboi.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://irr.bboi.net/bboi.db.gz',
            'dump_serial_source': 'ftp://irr.bboi.net/BBOI.CURRENTSERIAL',
        },
        # BELL FTP is dead
        # INTERNAL source unknown
        # JPIRR FTP is dead
        'LEVEL3': {
            'authoritative': False,
            'keep_journal': True,
            'nrtm_host': 'rr.level3.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://rr.Level3.net/pub/rr/level3.db.gz',
            'dump_serial_source': 'ftp://rr.level3.net/pub/rr/LEVEL3.CURRENTSERIAL',
        },
        'NTTCOM': {
            'authoritative': True,
            'dump_source': 'ftp://rr1.ntt.net/nttcomRR/nttcom.db.gz',
            'dump_serial_source': 'ftp://rr1.ntt.net/nttcomRR/NTTCOM.CURRENTSERIAL',
            # export schedule
            # TODO: authoritative should block mirror downloads?
        },
        'RADB': {
            'authoritative': False,
            'nrtm_host': 'whois.radb.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://ftp.radb.net/radb/dbase/radb.db.gz',
            'dump_serial_source': 'ftp://ftp.radb.net/radb/dbase/RADB.CURRENTSERIAL',
            # filter for object types
        },
        # REGISTROBR source unknown
        'RGNET': {
            'authoritative': False,
            'nrtm_host': 'whois.rg.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://rg.net/rgnet/RGNET.db.gz',
            'dump_serial_source': 'ftp://rg.net/rgnet/RGNET.CURRENTSERIAL',
        },
        'RIPE': {
            'authoritative': False,
            'dump_source': 'ftp://ftp.ripe.net/ripe/dbase/ripe.db.gz',
            'dump_serial_source': 'ftp://ftp.ripe.net/ripe/dbase/RIPE.CURRENTSERIAL',
            'object_class_filter': 'aut-num,route,route6,as-set,filter-set,inet-rtr,peering-set,route-set,rtr-set',
        },
        # RPKI source unknown
        # TC FTP not reachable
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
        'sqlalchemy': {
            'level': 'WARNING',
            'propagate': True,
        },
        'irrd.storage.api': {
            'level': 'WARNING',
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
