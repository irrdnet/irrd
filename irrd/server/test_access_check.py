from twisted.internet.address import IPv4Address, UNIXAddress

from .access_check import is_client_permitted


class TestIsClientPermitted:
    peer = IPv4Address('TCP', '192.0.2.1', 99999)

    def test_no_access_list(self):
        assert is_client_permitted(self.peer, 'test.access_list', default_deny=False)
        assert not is_client_permitted(self.peer, 'test.access_list', default_deny=True)

    def test_access_list_permitted(self, config_override):
        config_override({
            'test': {
                'access_list': 'test-access-list',
            },
            'access_lists': {
                'test-access-list': ['192.0.2.0/25'],
            },
        })

        assert is_client_permitted(self.peer, 'test.access_list', default_deny=False)
        assert is_client_permitted(self.peer, 'test.access_list', default_deny=True)

    def test_access_list_denied(self, config_override):
        config_override({
            'test': {
                'access_list': 'test-access-list',
            },
            'access_lists': {
                'test-access-list': ['192.0.2.128/25'],
            },
        })

        assert not is_client_permitted(self.peer, 'test.access_list', default_deny=False)
        assert not is_client_permitted(self.peer, 'test.access_list', default_deny=True)

    def test_access_list_denied_unknown_client_address(self):
        unix_peer = UNIXAddress(b'not-supported')
        assert not is_client_permitted(unix_peer, 'test.access_list', default_deny=False)
        assert not is_client_permitted(unix_peer, 'test.access_list', default_deny=True)
