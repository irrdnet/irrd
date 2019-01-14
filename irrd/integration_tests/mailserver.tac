# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# You can run this module directly with:
#    twistd -ny emailserver.tac

from __future__ import print_function

import os
import sys
from zope.interface import implementer

from twisted.internet import defer
from twisted.mail import smtp

from irrd.integration_tests.data import EMAIL_SEPARATOR, EMAIL_RETURN_MSGS_COMMAND, EMAIL_DISCARD_MSGS_COMMAND, \
    EMAIL_SMTP_PORT

IRRD_ROOT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
sys.path.append(IRRD_ROOT_PATH)

messages = []


class CustomESMTP(smtp.ESMTP):
    def lineReceived(self, line):
        print(f'Received line: {line}')
        global messages
        clean_line = line.strip().decode('utf-8')
        if clean_line == EMAIL_RETURN_MSGS_COMMAND:
            self.transport.write(EMAIL_SEPARATOR.join(messages).encode('utf-8') + b'\n')
        elif clean_line == EMAIL_DISCARD_MSGS_COMMAND:
            messages = []
            self.transport.write(b'OK\n')
        else:
            return super().lineReceived(line)


@implementer(smtp.IMessageDelivery)
class ConsoleMessageDelivery:
    def receivedHeader(self, helo, origin, recipients):
        return b'Received: ConsoleMessageDelivery'

    def validateFrom(self, helo, origin):
        return origin

    def validateTo(self, user):
        return lambda: ConsoleMessage()


@implementer(smtp.IMessage)
class ConsoleMessage:
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


class ConsoleSMTPFactory(smtp.SMTPFactory):
    protocol = CustomESMTP

    def __init__(self, *a, **kw):
        smtp.SMTPFactory.__init__(self, *a, **kw)
        self.delivery = ConsoleMessageDelivery()

    def buildProtocol(self, addr):
        p = smtp.SMTPFactory.buildProtocol(self, addr)
        p.delivery = self.delivery
        return p


def main():
    from twisted.application import internet
    from twisted.application import service

    a = service.Application('Mock SMTP Server')
    internet.TCPServer(EMAIL_SMTP_PORT, ConsoleSMTPFactory()).setServiceParent(a)

    return a


application = main()
