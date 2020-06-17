from .access_check import is_client_permitted


class TestIsClientPermitted:
    client_ip = '192.0.2.1'

    def test_no_access_list(self):
        assert is_client_permitted(self.client_ip, 'test.access_list', default_deny=False)
        assert not is_client_permitted(self.client_ip, 'test.access_list', default_deny=True)

    def test_access_list_permitted(self, config_override):
        config_override({
            'test': {
                'access_list': 'test-access-list',
            },
            'access_lists': {
                'test-access-list': ['192.0.2.0/25', '2001:db8::/32'],
            },
        })

        assert is_client_permitted(self.client_ip, 'test.access_list', default_deny=False)
        assert is_client_permitted(self.client_ip, 'test.access_list', default_deny=True)
        assert is_client_permitted(f'::ffff:{self.client_ip}', 'test.access_list', default_deny=True)
        assert is_client_permitted('2001:db8::1', 'test.access_list', default_deny=True)

    def test_access_list_denied(self, config_override):
        config_override({
            'test': {
                'access_list': 'test-access-list',
            },
            'access_lists': {
                'test-access-list': ['192.0.2.128/25', '2001:db8::/32'],
            },
        })

        assert not is_client_permitted(self.client_ip, 'test.access_list', default_deny=False)
        assert not is_client_permitted(f'::ffff:{self.client_ip}', 'test.access_list', default_deny=False)
        assert not is_client_permitted(self.client_ip, 'test.access_list', default_deny=True)

    def test_access_list_denied_invalid_ip(self):
        assert not is_client_permitted('invalid', 'test.access_list', default_deny=False)
        assert not is_client_permitted('invalid', 'test.access_list', default_deny=True)
