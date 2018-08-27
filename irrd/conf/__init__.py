import logging.config
import time
from typing import Any
import os

from dotted.collection import DottedDict

PASSWORD_HASH_DUMMY_VALUE = 'DummyValue'

DEFAULT_SETTINGS = DottedDict({
    'database_url': 'postgresql://localhost:5432/irrd',
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
    'sources': {
        # TODO: validate that source names are upper case
        'AFRINIC': {
            'authoritative': False,
            'keep_journal': True,
            'nrtm_host': 'rr.ntt.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://ftp.afrinic.net/pub/dbase/afrinic.db.gz',
            'dump_serial_source': 'ftp://ftp.afrinic.net/pub/dbase/AFRINIC.CURRENTSERIAL',
            'object_class_filter': 'as-block,as-set,autnum,filter-set,inet-rtr,peering-set,role,route-set,route,route6,rtr-set',
        },
        'ALTDB': {
            'nrtm_host': 'rr.ntt.net',
            'keep_journal': True,
            'nrtm_port': 43,
            'dump_source': 'ftp://ftp.radb.net/radb/dbase/altdb.db.gz',
            'dump_serial_source': 'ftp://ftp.radb.net/radb/dbase/ALTDB.CURRENTSERIAL',
        },
        'APNIC': {
            'authoritative': False,
            'keep_journal': True,
            'nrtm_host': 'rr.ntt.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://ftp.apnic.net/pub/apnic/whois/apnic.db.as-block.gz,'
                           'ftp://ftp.apnic.net/pub/apnic/whois/apnic.db.as-set.gz,'
                           'ftp://ftp.apnic.net/pub/apnic/whois/apnic.db.aut-num.gz,'
                           'ftp://ftp.apnic.net/pub/apnic/whois/apnic.db.filter-set.gz,'
                           'ftp://ftp.apnic.net/pub/apnic/whois/apnic.db.inet-rtr.gz,'
                           'ftp://ftp.apnic.net/pub/apnic/whois/apnic.db.peering-set.gz,'
                           'ftp://ftp.apnic.net/pub/apnic/whois/apnic.db.route-set.gz,'
                           'ftp://ftp.apnic.net/pub/apnic/whois/apnic.db.route.gz,'
                           'ftp://ftp.apnic.net/pub/apnic/whois/apnic.db.route6.gz,'
                           'ftp://ftp.apnic.net/pub/apnic/whois/apnic.db.rtr-set.gz',
            'dump_serial_source': 'ftp://ftp.arin.net/pub/rr/ARIN.CURRENTSERIAL',
        },
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
            'keep_journal': True,
            'nrtm_host': 'irr.bboi.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://irr.bboi.net/bboi.db.gz',
            'dump_serial_source': 'ftp://irr.bboi.net/BBOI.CURRENTSERIAL',
        },
        'BELL': {
            'keep_journal': True,
            'nrtm_host': 'rr.ntt.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://ftp.radb.net/radb/dbase/bell.db.gz',
            'dump_serial_source': 'ftp://ftp.radb.net/radb/dbase/BELL.CURRENTSERIAL',
        },
        # INTERNAL source unknown
        'JPIRR': {
            'keep_journal': True,
            'nrtm_host': 'rr.ntt.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://ftp.radb.net/radb/dbase/jpirr.db.gz',
            'dump_serial_source': 'ftp://ftp.radb.net/radb/dbase/JPIRR.CURRENTSERIAL',
        },
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
            'keep_journal': True,
            'nrtm_host': 'rr.ntt.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://rr1.ntt.net/nttcomRR/nttcom.db.gz',
            'dump_serial_source': 'ftp://rr1.ntt.net/nttcomRR/NTTCOM.CURRENTSERIAL',
            # export schedule
            # TODO: authoritative should block mirror downloads?
        },
        'RADB': {
            'authoritative': False,
            'keep_journal': True,
            'nrtm_host': 'whois.radb.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://ftp.radb.net/radb/dbase/radb.db.gz',
            'dump_serial_source': 'ftp://ftp.radb.net/radb/dbase/RADB.CURRENTSERIAL',
        },
        # REGISTROBR source unknown
        'RGNET': {
            'authoritative': False,
            'keep_journal': True,
            'nrtm_host': 'whois.rg.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://rg.net/rgnet/RGNET.db.gz',
            'dump_serial_source': 'ftp://rg.net/rgnet/RGNET.CURRENTSERIAL',
        },
        'RIPE': {
            'authoritative': False,
            'keep_journal': True,
            'nrtm_host': '193.0.6.145',
            'nrtm_port': 4444,
            'dump_source': 'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe.db.as-block.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe.db.as-set.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe.db.aut-num.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe.db.filter-set.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe.db.inet-rtr.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe.db.organisation.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe.db.peering-set.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe.db.role.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe.db.route.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe.db.route6.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe.db.route-set.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe.db.rtr-set.gz',
            'dump_serial_source': 'ftp://ftp.ripe.net/ripe/dbase/rc/RIPE.CURRENTSERIAL',
        },
        'RIPE-NONAUTH': {
            'authoritative': False,
            'keep_journal': True,
            'nrtm_host': '193.0.6.145',
            'nrtm_port': 4444,
            'dump_source': 'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe-nonauth.db.as-block.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe-nonauth.db.as-set.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe-nonauth.db.aut-num.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe-nonauth.db.filter-set.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe-nonauth.db.inet-rtr.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe-nonauth.db.organisation.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe-nonauth.db.peering-set.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe-nonauth.db.role.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe-nonauth.db.route.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe-nonauth.db.route6.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe-nonauth.db.route-set.gz,'
                           'ftp://ftp.ripe.net/ripe/dbase/rc/split/ripe-nonauth.db.rtr-set.gz',
            'dump_serial_source': 'ftp://ftp.ripe.net/ripe/dbase/rc/RIPE-NONAUTH.CURRENTSERIAL',
        },
        # RPKI source unknown
        'TC': {
            'keep_journal': True,
            'nrtm_host': 'rr.ntt.net',
            'nrtm_port': 43,
            'dump_source': 'ftp://ftp.radb.net/radb/dbase/tc.db.gz',
            'dump_serial_source': 'ftp://ftp.radb.net/radb/dbase/TC.CURRENTSERIAL',
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
