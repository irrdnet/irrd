# You can run this .tac file directly with:
#    twistd -ny twistd.tac

# flake8: noqa: E402

import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'irrd/'))

from twisted.application import service, internet
from twisted.application.internet import TimerService
from twisted.python.log import ILogObserver, PythonLoggingObserver

from irrd.conf import get_setting
from irrd.mirroring.scheduler import MirrorScheduler
from irrd.server.whois.protocol import WhoisQueryReceiverFactory

application = service.Application("IRRD")
application.setComponent(ILogObserver, PythonLoggingObserver().emit)

server = internet.TCPServer(
    get_setting('server.whois.port'),
    WhoisQueryReceiverFactory(),
    interface=get_setting('server.whois.interface')
)
server.setServiceParent(application)

TimerService(600, MirrorScheduler().run).setServiceParent(application)
