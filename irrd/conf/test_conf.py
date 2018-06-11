from . import get_setting


class TestGetSetting:
    setting_name = 'database_url'
    env_name = 'IRRD_DATABASE_URL'

    def test_get_setting_default(self, monkeypatch):
        monkeypatch.delenv(self.env_name, raising=False)
        assert get_setting(self.setting_name) == 'postgresql:///irrd'

    def test_get_setting_env(self, monkeypatch):
        monkeypatch.setenv(self.env_name, 'env_value')
        assert get_setting(self.setting_name) == 'env_value'
