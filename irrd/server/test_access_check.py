from twisted.internet.address import IPv4Address, UNIXAddress, IPv6Address

from .access_check import is_client_permitted


class TestIsClientPermitted:
    peer4_1 = IPv4Address('TCP', '192.0.2.1', 99999)
    peer4_2 = IPv4Address('TCP', '198.51.100.1', 99999)
    peer4_mapped = IPv6Address('TCP', '::ffff:192.0.2.1', 99999)
    peer6 = IPv6Address('TCP', '2001:db8::1', 99999)

    def test_no_access_list(self):
        assert is_client_permitted(self.peer4_1, 'test.access_list', default_deny=False)
        assert not is_client_permitted(self.peer4_1, 'test.access_list', default_deny=True)
        assert is_client_permitted(self.peer4_2, 'test.access_list', default_deny=False)
        assert not is_client_permitted(self.peer4_2, 'test.access_list', default_deny=True)
        assert is_client_permitted(self.peer4_mapped, 'test.access_list', default_deny=False)
        assert not is_client_permitted(self.peer4_mapped, 'test.access_list', default_deny=True)
        assert is_client_permitted(self.peer6, 'test.access_list', default_deny=False)
        assert not is_client_permitted(self.peer6, 'test.access_list', default_deny=True)

    def test_access_list_permitted(self, config_override):
        config_override({
            'test': {
                'access_list': 'test-access-list',
            },
            'access_lists': {
                'test-access-list': ['192.0.2.0/25', '198.51.100.1', '2001:db8::/48'],
            },
        })

        assert is_client_permitted(self.peer4_1, 'test.access_list', default_deny=False)
        assert is_client_permitted(self.peer4_1, 'test.access_list', default_deny=True)
        assert is_client_permitted(self.peer4_2, 'test.access_list', default_deny=False)
        assert is_client_permitted(self.peer4_2, 'test.access_list', default_deny=True)
        assert is_client_permitted(self.peer4_mapped, 'test.access_list', default_deny=False)
        assert is_client_permitted(self.peer4_mapped, 'test.access_list', default_deny=True)
        assert is_client_permitted(self.peer6, 'test.access_list', default_deny=False)
        assert is_client_permitted(self.peer6, 'test.access_list', default_deny=True)

    def test_access_list_denied(self, config_override):
        config_override({
            'test': {
                'access_list': 'test-access-list',
            },
            'access_lists': {
                'test-access-list': ['192.0.2.128/25', '2001:db9::/48'],
            },
        })

        assert not is_client_permitted(self.peer4_1, 'test.access_list', default_deny=False)
        assert not is_client_permitted(self.peer4_1, 'test.access_list', default_deny=True)
        assert not is_client_permitted(self.peer4_2, 'test.access_list', default_deny=False)
        assert not is_client_permitted(self.peer4_2, 'test.access_list', default_deny=True)
        assert not is_client_permitted(self.peer4_mapped, 'test.access_list', default_deny=False)
        assert not is_client_permitted(self.peer4_mapped, 'test.access_list', default_deny=True)
        assert not is_client_permitted(self.peer6, 'test.access_list', default_deny=False)
        assert not is_client_permitted(self.peer6, 'test.access_list', default_deny=True)

    def test_access_list_denied_unknown_client_address(self):
        unix_peer = UNIXAddress(b'not-supported')
        assert not is_client_permitted(unix_peer, 'test.access_list', default_deny=False)
        assert not is_client_permitted(unix_peer, 'test.access_list', default_deny=True)
