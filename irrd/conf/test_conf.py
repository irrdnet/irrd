from . import get_setting


class TestGetSetting:
    setting_name = 'server.whois.interface'
    env_name = 'IRRD_SERVER_WHOIS_INTERFACE'

    def test_get_setting_default(self, monkeypatch):
        monkeypatch.delenv(self.env_name, raising=False)
        assert get_setting(self.setting_name) == '::0'

    def test_get_setting_env(self, monkeypatch):
        monkeypatch.setenv(self.env_name, 'env_value')
        assert get_setting(self.setting_name) == 'env_value'
