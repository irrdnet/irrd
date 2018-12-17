# You can run this .tac file directly with:
#    twistd -ny twistd.tac

# flake8: noqa: E402

import os
import sys

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

from twisted.application import service, internet
from twisted.application.internet import TimerService
from twisted.python.log import ILogObserver, PythonLoggingObserver

from irrd.conf import get_setting
from irrd.mirroring.scheduler import MirrorScheduler
from irrd.server.http.http_resources import http_site
from irrd.server.whois.protocol import WhoisQueryReceiverFactory

application = service.Application("IRRD")
application.setComponent(ILogObserver, PythonLoggingObserver().emit)

internet.TCPServer(
    get_setting('server.whois.port'),
    WhoisQueryReceiverFactory(),
    interface=get_setting('server.whois.interface')
).setServiceParent(application)

internet.TCPServer(
    get_setting('server.http.port'),
    http_site,
    interface=get_setting('server.http.interface')
).setServiceParent(application)

TimerService(15, MirrorScheduler().run).setServiceParent(application)
