import os

import pytest
import signal
import yaml
from typing import Dict

from . import get_setting, ConfigurationError, config_init, is_config_initialised


@pytest.fixture()
def save_yaml_config(tmpdir, monkeypatch):
    def _save(config: Dict, run_init=True):
        tmp_file = tmpdir + '/config.yaml'
        with open(tmp_file, 'w') as fh:
            fh.write(yaml.safe_dump(config))
        if run_init:
            config_init(str(tmp_file))
    return _save


class TestConfiguration:
    def test_file_not_existing(self, monkeypatch, tmpdir):
        with pytest.raises(ConfigurationError) as ce:
            config_init(str(tmpdir + '/doesnotexist.yaml'))
        assert 'Error opening config file' in str(ce)

    def test_load_invalid_yaml(self, monkeypatch, tmpdir):
        tmp_file = tmpdir + '/config.yaml'
        fh = open(tmp_file, 'w')
        fh.write('  >foo')
        fh.close()

        with pytest.raises(ConfigurationError) as ce:
            config_init(str(tmp_file))
        assert 'Error parsing YAML file' in str(ce)

    def test_load_string_file(self, save_yaml_config):
        with pytest.raises(ConfigurationError) as ce:
            save_yaml_config('foo')
        assert 'Could not find root item "irrd" in config file' in str(ce)

    def test_load_empty_config(self, save_yaml_config):
        with pytest.raises(ConfigurationError) as ce:
            save_yaml_config({})
        assert 'Could not find root item "irrd" in config file' in str(ce)

    def test_load_valid_reload_valid_config(self, monkeypatch, save_yaml_config, tmpdir, caplog):
        logfile = str(tmpdir + '/logfile.txt')
        config = {
            'irrd': {
                'database_url': 'invalid-url',
                'email': {
                    'from': 'example@example.com',
                    'smtp': '192.0.2.1'
                },
                'access-lists': {
                    'valid-list': {
                        '192/24',
                        '192.0.2.1',
                        '2001:db8::32',
                        '2001:db8::1',
                    }
                },
                'auth': {
                    'gnupg_keyring': str(tmpdir)
                },
                'sources_default': ['TESTDB2', 'TESTDB'],
                'sources': {
                    'TESTDB': {
                        'authoritative': True,
                        'keep_journal': True,
                    },
                    'TESTDB2': {
                        'nrtm_host': '192.0.2.1',
                        'nrtm_port': 43,
                        'import_serial_source': 'ftp://example.com/serial',
                        'keep_journal': True,
                    },
                },
                'log': {
                    'level': 'DEBUG',
                    'logfile_path': logfile
                },

            }
        }
        save_yaml_config(config)
        assert list(get_setting('sources_default')) == ['TESTDB2', 'TESTDB']
        assert is_config_initialised()

        config['irrd']['sources_default'] = ['TESTDB2']
        save_yaml_config(config, run_init=False)

        # Unchanged, no reload performed
        assert list(get_setting('sources_default')) == ['TESTDB2', 'TESTDB']

        os.kill(os.getpid(), signal.SIGHUP)
        assert list(get_setting('sources_default')) == ['TESTDB2']

        logfile_contents = open(logfile).read()
        assert 'Configuration successfully (re)loaded from ' in logfile_contents

    def test_load_valid_reload_invalid_config(self, save_yaml_config, tmpdir, caplog):
        save_yaml_config({
            'irrd': {
                'database_url': 'invalid-url',
                'email': {
                    'from': 'example@example.com',
                    'smtp': '192.0.2.1'
                },
                'access-lists': {
                    'valid-list': {
                        '192/24',
                        '192.0.2.1',
                        '2001:db8::32',
                        '2001:db8::1',
                    }
                },
                'auth': {
                    'gnupg_keyring': str(tmpdir)
                },
                'sources_default': ['TESTDB2', 'TESTDB'],
                'sources': {
                    'TESTDB': {
                        'authoritative': True,
                        'keep_journal': True,
                    },
                    'TESTDB2': {
                        'nrtm_host': '192.0.2.1',
                        'nrtm_port': 43,
                        'import_serial_source': 'ftp://example.com/serial',
                        'keep_journal': True,
                        'import_timer': '1234',
                    },
                },

            }
        })

        save_yaml_config({}, run_init=False)
        os.kill(os.getpid(), signal.SIGHUP)
        assert list(get_setting('sources_default')) == ['TESTDB2', 'TESTDB']
        assert 'Errors found in configuration, continuing with current settings' in caplog.text
        assert 'Could not find root item "irrd"' in caplog.text

    def test_load_invalid_config(self, save_yaml_config, tmpdir):
        config = {
            'irrd': {
                'server': {
                    'whois': {
                        'access_list': 'doesnotexist',
                    },
                    'http': {
                        'access_list': ['foo'],
                    },
                },
                'email': {
                    'footer': {'a': 1},
                },
                'access_lists': {
                    'bad-list': {
                        '192.0.2.2.1'
                    },
                },
                'sources_default': ['DOESNOTEXIST-DB'],
                'sources': {
                    'TESTDB': {
                        'keep_journal': True,
                        'import_timer': 'foo',
                        'export_timer': 'bar',
                        'nrtm_host': '192.0.2.1',
                    },
                    'TESTDB2': {
                        'authoritative': True,
                        'nrtm_host': '192.0.2.1',
                        'nrtm_port': 'not a number',
                    },
                    'TESTDB3': {
                        'authoritative': True,
                        'import_source': '192.0.2.1',
                    },
                    'lowercase': {},
                    'invalid char': {},
                },
                'log': {
                    'level': 'INVALID',
                }
            }
        }

        with pytest.raises(ConfigurationError) as ce:
            save_yaml_config(config)

        assert 'Setting database_url is required.' in str(ce)
        assert 'Setting email.from is required and must be an email address.' in str(ce)
        assert 'Setting email.smtp is required.' in str(ce)
        assert 'Setting email.footer must be a string, if defined.' in str(ce)
        assert 'Setting auth.gnupg_keyring is required.' in str(ce)
        assert 'Access lists doesnotexist referenced in settings, but not defined.' in str(ce)
        assert 'Setting server.http.access_list must be a string, if defined.' in str(ce)
        assert 'Invalid item in access list bad-list: IPv4 Address with more than 4 bytes.' in str(ce)
        assert 'Setting sources_default contains unknown sources: DOESNOTEXIST-DB' in str(ce)
        assert 'Setting keep_journal for source TESTDB can not be enabled unless either ' in str(ce)
        assert 'Setting nrtm_host for source TESTDB can not be enabled without setting import_serial_source.' in str(ce)
        assert 'Setting authoritative for source TESTDB2 can not be enabled when either nrtm_host or import_source are set.' in str(ce)
        assert 'Setting authoritative for source TESTDB3 can not be enabled when either nrtm_host or import_source are set.' in str(ce)
        assert 'Setting nrtm_port for source TESTDB2 must be a number.' in str(ce)
        assert 'Setting import_timer for source TESTDB must be a number.' in str(ce)
        assert 'Setting export_timer for source TESTDB must be a number.' in str(ce)
        assert 'Invalid source name: lowercase' in str(ce)
        assert 'Invalid source name: invalid char' in str(ce)
        assert 'Invalid log.level: INVALID' in str(ce)


class TestGetSetting:
    setting_name = 'server.whois.interface'
    env_name = 'IRRD_SERVER_WHOIS_INTERFACE'

    def test_get_setting_default(self, monkeypatch):
        monkeypatch.delenv(self.env_name, raising=False)
        assert get_setting(self.setting_name) == '::0'

    def test_get_setting_env(self, monkeypatch):
        monkeypatch.setenv(self.env_name, 'env_value')
        assert get_setting(self.setting_name) == 'env_value'
