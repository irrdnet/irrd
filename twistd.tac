# You can run this .tac file directly with:
#    twistd -ny twistd.tac

from twisted.application import service, internet
from twisted.application.internet import TimerService
from twisted.python.log import ILogObserver, PythonLoggingObserver

from irrd.conf import get_setting
from irrd.nrtm.scheduler import NRTMScheduler
from irrd.server.whois.protocol import WhoisQueryReceiverFactory

application = service.Application("IRRDv4")
application.setComponent(ILogObserver, PythonLoggingObserver().emit)

server = internet.TCPServer(
    get_setting('server.whois.port'),
    WhoisQueryReceiverFactory(),
    interface=get_setting('server.whois.interface')
)
server.setServiceParent(application)

TimerService(60, NRTMScheduler().run).setServiceParent(application)
