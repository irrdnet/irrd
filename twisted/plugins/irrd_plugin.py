# flake8: noqa: E402
import sys

import os
from pathlib import Path
from twisted.application import internet, service
from twisted.application.service import IServiceMaker
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.log import PythonLoggingObserver, ILogObserver
from zope.interface import implementer

sys.path.append(str(Path(__file__).resolve().parents[1]))

from irrd.conf import config_init, get_setting, CONFIG_PATH_DEFAULT
from irrd.mirroring.scheduler import MirrorScheduler
from irrd.server.http.http_resources import http_site
from irrd.server.whois.protocol import WhoisQueryReceiverFactory


class Options(usage.Options):
    optParameters = [['config', 'c', CONFIG_PATH_DEFAULT, 'Path to the IRRd config file.']]


class PythonLoggingMultiService(service.MultiService):
    def setServiceParent(self, parent):
        service.MultiService.setServiceParent(self, parent)
        parent.setComponent(ILogObserver, PythonLoggingObserver().emit)


@implementer(IServiceMaker, IPlugin)
class ServiceMaker(object):
    tapname = 'irrd'
    description = 'Internet Routing Registry daemon'
    options = Options

    def makeService(self, options):
        config_init(options['config'])

        ms = PythonLoggingMultiService()

        internet.TCPServer(
            get_setting('server.whois.port'),
            WhoisQueryReceiverFactory(),
            interface=get_setting('server.whois.interface')
        ).setServiceParent(ms)

        internet.TCPServer(
            get_setting('server.http.port'),
            http_site,
            interface=get_setting('server.http.interface')
        ).setServiceParent(ms)

        mirror_frequency = int(os.environ.get('IRRD_SCHEDULER_TIMER_OVERRIDE', 15))
        internet.TimerService(mirror_frequency, MirrorScheduler().run).setServiceParent(ms)

        return ms


serviceMaker = ServiceMaker()
