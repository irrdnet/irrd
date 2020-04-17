# Based on an original example by Twisted Matrix Laboratories
# under the following license:
# https://github.com/twisted/twisted/blob/trunk/LICENSE

"""
This runs a small SMTP server under twisted. All mails are stored in memory,
and two special commands can be used to retrieve them or empty the local
memory store. This is used to simulate actual SMTP interaction in the
integration test.
"""

import os
import sys
from zope.interface import implementer

from twisted.internet import defer
from twisted.mail import smtp

from irrd.integration_tests.constants import (EMAIL_SEPARATOR, EMAIL_RETURN_MSGS_COMMAND, EMAIL_DISCARD_MSGS_COMMAND,
                                              EMAIL_SMTP_PORT, EMAIL_END)

IRRD_ROOT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
sys.path.append(IRRD_ROOT_PATH)

messages = []


class CustomESMTP(smtp.ESMTP):
    def lineReceived(self, line):
        global messages
        clean_line = line.strip().decode('utf-8')
        if clean_line == EMAIL_RETURN_MSGS_COMMAND:
            self.transport.write(EMAIL_SEPARATOR.join(messages).encode('utf-8') + b'\n')
            self.transport.write(EMAIL_END)
        elif clean_line == EMAIL_DISCARD_MSGS_COMMAND:
            messages = []
            self.transport.write(b'OK\n')
        else:
            return super().lineReceived(line)


@implementer(smtp.IMessageDelivery)
class MemoryMessageDelivery:
    def receivedHeader(self, helo, origin, recipients):
        return b'Received: MemoryMessageDelivery'

    def validateFrom(self, helo, origin):
        return origin

    def validateTo(self, user):
        return lambda: MemoryMessage()


@implementer(smtp.IMessage)
class MemoryMessage:
    def __init__(self):
        self.lines = []

    def lineReceived(self, line):
        self.lines.append(line.decode('utf-8'))

    def eomReceived(self):
        global messages
        messages.append('\n'.join(self.lines))
        self.lines = None
        return defer.succeed(None)

    def connectionLost(self):
        self.lines = None


class MemorySMTPFactory(smtp.SMTPFactory):
    protocol = CustomESMTP

    def __init__(self, *a, **kw):
        smtp.SMTPFactory.__init__(self, *a, **kw)
        self.delivery = MemoryMessageDelivery()

    def buildProtocol(self, addr):
        p = smtp.SMTPFactory.buildProtocol(self, addr)
        p.delivery = self.delivery
        return p


def main():
    from twisted.application import internet
    from twisted.application import service

    a = service.Application('Mock SMTP Server')
    internet.TCPServer(EMAIL_SMTP_PORT, MemorySMTPFactory()).setServiceParent(a)

    return a


application = main()
