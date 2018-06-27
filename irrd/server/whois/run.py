# This is a temporary running script for the twisted server

if __name__ == "__main__":
    from irrd.conf import get_setting  # noqa - hack to load logging config
    from twisted.internet import reactor
    from twisted.internet.endpoints import TCP4ServerEndpoint, TCP6ServerEndpoint

    from irrd.server.whois.protocol import WhoisQueryReceiverFactory

    endpoint = TCP4ServerEndpoint(reactor, 8007)
    endpoint.listen(WhoisQueryReceiverFactory())
    endpoint = TCP6ServerEndpoint(reactor, 8007)
    endpoint.listen(WhoisQueryReceiverFactory())
    reactor.run()
