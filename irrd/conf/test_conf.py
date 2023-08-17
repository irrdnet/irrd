import os
import signal
import textwrap
from typing import Dict

import pytest
import yaml

from . import (
    ConfigurationError,
    config_init,
    get_configuration,
    get_setting,
    is_config_initialised,
)


@pytest.fixture()
def save_yaml_config(tmpdir, monkeypatch):
    def _save(config: Dict, run_init=True):
        tmp_file = tmpdir + "/config.yaml"
        with open(tmp_file, "w") as fh:
            fh.write(yaml.safe_dump(config))
        if run_init:
            config_init(str(tmp_file))

    return _save


class TestConfiguration:
    def test_file_not_existing(self, monkeypatch, tmpdir):
        with pytest.raises(ConfigurationError) as ce:
            config_init(str(tmpdir + "/doesnotexist.yaml"))
        assert "Error opening config file" in str(ce.value)

    def test_load_invalid_yaml(self, monkeypatch, tmpdir):
        tmp_file = tmpdir + "/config.yaml"
        fh = open(tmp_file, "w")
        fh.write("  >foo")
        fh.close()

        with pytest.raises(ConfigurationError) as ce:
            config_init(str(tmp_file))
        assert "Error parsing YAML file" in str(ce.value)

    def test_load_string_file(self, save_yaml_config):
        with pytest.raises(ConfigurationError) as ce:
            save_yaml_config("foo")
        assert 'Could not find root item "irrd" in config file' in str(ce.value)

    def test_load_empty_config(self, save_yaml_config):
        with pytest.raises(ConfigurationError) as ce:
            save_yaml_config({})
        assert 'Could not find root item "irrd" in config file' in str(ce.value)

    def test_load_valid_reload_valid_config(self, monkeypatch, save_yaml_config, tmpdir, caplog):
        logfile = str(tmpdir + "/logfile.txt")
        config = {
            "irrd": {
                "database_url": "db-url",
                "redis_url": "redis-url",
                "piddir": str(tmpdir),
                "server": {"http": {"url": "https://example.com/"}},
                "email": {"from": "example@example.com", "smtp": "192.0.2.1"},
                "route_object_preference": {
                    "update_timer": 10,
                },
                "rpki": {
                    "roa_source": None,
                },
                "scopefilter": {"prefixes": ["10/8"], "asns": ["23456", "10-20"]},
                "access_lists": {
                    "valid-list": {
                        "192/24",
                        "192.0.2.1",
                        "2001:db8::32",
                        "2001:db8::1",
                    }
                },
                "auth": {
                    "gnupg_keyring": str(tmpdir),
                    "authenticate_parents_route_creation": True,
                    "set_creation": {
                        "as-set": {
                            "prefix_required": True,
                            "autnum_authentication": "opportunistic",
                        },
                        "COMMON": {
                            "prefix_required": True,
                            "autnum_authentication": "required",
                        },
                    },
                    "password_hashers": {
                        "bcrypt-pw": "legacy",
                    },
                },
                "sources_default": ["TESTDB2", "TESTDB", "SOURCE-ALIAS"],
                "sources": {
                    "TESTDB": {
                        "authoritative": True,
                        "keep_journal": True,
                        "suspension_enabled": True,
                        "nrtm_query_serial_range_limit": 10,
                    },
                    "TESTDB2": {
                        "nrtm_host": "192.0.2.1",
                        "nrtm_port": 43,
                        "import_serial_source": "ftp://example.com/serial",
                        "keep_journal": True,
                        "route_object_preference": 200,
                    },
                    "TESTDB3": {
                        "export_destination_unfiltered": "/tmp",
                        "nrtm_access_list_unfiltered": "valid-list",
                    },
                    # RPKI source permitted, rpki.roa_source not set
                    "RPKI": {},
                },
                "source_aliases": {
                    "SOURCE-ALIAS": ["TESTDB", "TESTDB2"],
                },
                "log": {"level": "DEBUG", "logfile_path": logfile},
            }
        }
        save_yaml_config(config)
        assert is_config_initialised()

        config["irrd"]["sources_default"] = ["TESTDB2"]
        save_yaml_config(config, run_init=False)

        # Unchanged, no reload performed
        assert list(get_setting("sources_default")) == ["TESTDB2", "TESTDB", "SOURCE-ALIAS"]

        os.kill(os.getpid(), signal.SIGHUP)
        assert list(get_setting("sources_default")) == ["TESTDB2"]

        logfile_contents = open(logfile).read()
        assert "Configuration successfully (re)loaded from " in logfile_contents

    def test_load_custom_logging_config(self, monkeypatch, save_yaml_config, tmpdir, caplog):
        logfile = str(tmpdir + "/logfile.txt")
        logging_config_path = str(tmpdir + "/logging.py")
        with open(logging_config_path, "w") as fh:
            fh.write(
                textwrap.dedent(
                    """
                LOGGING = {
                    'version': 1,
                    'disable_existing_loggers': False,
                    'formatters': {
                        'verbose': {
                            'format': '%(asctime)s irrd[%(process)d]: [%(name)s#%(levelname)s] %(message)s'
                        },
                    },
                    'handlers': {
                        'file': {
                            'class': 'logging.handlers.WatchedFileHandler',
                            'filename': '"""
                    + logfile
                    + """',
                            'formatter': 'verbose',
                        },
                    },
                    'loggers': {
                        '': {
                            'handlers': ['file'],
                            'level': 'DEBUG',
                        },
                    }
                }
            """
                )
            )
        config = {
            "irrd": {
                "database_url": "db-url",
                "redis_url": "redis-url",
                "piddir": str(tmpdir),
                "server": {"http": {"url": "https://example.com/"}},
                "email": {"from": "example@example.com", "smtp": "192.0.2.1"},
                "rpki": {
                    "roa_source": None,
                },
                "auth": {"gnupg_keyring": str(tmpdir)},
                "log": {
                    "logging_config_path": logging_config_path,
                },
            }
        }
        save_yaml_config(config)
        assert is_config_initialised()
        assert get_configuration().logging_config["handlers"]["file"]["filename"] == logfile

    def test_load_valid_reload_invalid_config(self, save_yaml_config, tmpdir, caplog):
        save_yaml_config(
            {
                "irrd": {
                    "database_url": "db-url",
                    "redis_url": "redis-url",
                    "piddir": str(tmpdir),
                    "server": {"http": {"url": "https://example.com/"}},
                    "email": {"from": "example@example.com", "smtp": "192.0.2.1"},
                    "access_lists": {
                        "valid-list": {
                            "192/24",
                            "192.0.2.1",
                            "2001:db8::32",
                            "2001:db8::1",
                        }
                    },
                    "auth": {
                        "gnupg_keyring": str(tmpdir),
                    },
                    "rpki": {
                        "roa_source": "https://example.com/roa.json",
                        "notify_invalid_enabled": False,
                    },
                    "sources_default": ["TESTDB2", "TESTDB", "RPKI"],
                    "sources": {
                        "TESTDB": {
                            "authoritative": True,
                            "keep_journal": True,
                        },
                        "TESTDB2": {
                            "nrtm_host": "192.0.2.1",
                            "nrtm_port": 43,
                            "import_serial_source": "ftp://example.com/serial",
                            "keep_journal": True,
                            "import_timer": "1234",
                        },
                    },
                }
            }
        )

        save_yaml_config({}, run_init=False)
        os.kill(os.getpid(), signal.SIGHUP)
        assert list(get_setting("sources_default")) == ["TESTDB2", "TESTDB", "RPKI"]
        assert "Errors found in configuration, continuing with current settings" in caplog.text
        assert 'Could not find root item "irrd"' in caplog.text

    def test_load_invalid_config(self, save_yaml_config, tmpdir):
        config = {
            "irrd": {
                "readonly_standby": True,
                "piddir": str(tmpdir + "/does-not-exist"),
                "user": "a",
                "server": {
                    "whois": {
                        "access_list": "doesnotexist",
                    },
                    "http": {
                        "url": "💩",
                        "status_access_list": ["foo"],
                    },
                },
                "email": {
                    "footer": {"a": 1},
                    "recipient_override": "invalid-mail",
                },
                "access_lists": {
                    "bad-list": {"192.0.2.2.1"},
                },
                "auth": {
                    "irrd_internal_migration_enabled": "invalid",
                    "webui_auth_failure_rate_limit": "invalid",
                    "set_creation": {
                        "as-set": {
                            "prefix_required": "not-a-bool",
                            "autnum_authentication": "unknown-value",
                        },
                        "not-a-real-set": {
                            "prefix_required": True,
                        },
                    },
                    "password_hashers": {
                        "unknown-hasher": "legacy",
                        "crypt-pw": "invalid-setting",
                    },
                },
                "route_object_preference": {
                    "update_timer": "not-a-number",
                },
                "rpki": {
                    "roa_source": "https://example.com/roa.json",
                    "roa_import_timer": "foo",
                    "notify_invalid_subject": [],
                    "notify_invalid_header": [],
                },
                "scopefilter": {
                    "prefixes": ["invalid-prefix"],
                    "asns": ["invalid", "10-invalid"],
                },
                "sources_default": ["DOESNOTEXIST-DB"],
                "sources": {
                    "TESTDB": {
                        "keep_journal": True,
                        "import_timer": "foo",
                        "export_timer": "bar",
                        "nrtm_host": "192.0.2.1",
                        "unknown": True,
                        "suspension_enabled": True,
                        "nrtm_query_serial_range_limit": "not-a-number",
                    },
                    "TESTDB2": {
                        "authoritative": True,
                        "nrtm_host": "192.0.2.1",
                        "nrtm_port": "not a number",
                        "nrtm_access_list": "invalid-list",
                    },
                    "TESTDB3": {
                        "authoritative": True,
                        "import_source": "192.0.2.1",
                        "nrtm_access_list_unfiltered": "invalid-list",
                        "route_object_preference": "not-a-number",
                    },
                    # Not permitted, rpki.roa_source is set
                    "RPKI": {},
                    "lowercase": {},
                    "invalid char": {},
                },
                "source_aliases": {
                    "SOURCE-ALIAS": ["TESTDB-NOTEXIST"],
                    "TESTDB2": ["TESTDB"],
                    "invalid name": ["TESTDB"],
                },
                "log": {
                    "level": "INVALID",
                    "logging_config_path": "path",
                    "unknown": True,
                },
                "unknown_setting": False,
            }
        }

        with pytest.raises(ConfigurationError) as ce:
            save_yaml_config(config)

        assert "Setting database_url is required." in str(ce.value)
        assert "Setting redis_url is required." in str(ce.value)
        assert "Setting piddir is required and must point to an existing directory." in str(ce.value)
        assert "Setting email.from is required and must be an email address." in str(ce.value)
        assert "Setting email.smtp is required." in str(ce.value)
        assert "Setting email.footer must be a string, if defined." in str(ce.value)
        assert "Setting email.recipient_override must be an email address if set." in str(ce.value)
        assert "Settings user and group must both be defined, or neither." in str(ce.value)
        assert "Setting auth.gnupg_keyring is required." in str(ce.value)
        assert "Setting auth.irrd_internal_migration_enabled must be a bool." in str(ce.value)
        assert "Setting auth.webui_auth_failure_rate_limit is missing or invalid." in str(ce.value)
        assert "Unknown setting key: auth.set_creation.not-a-real-set.prefix_required" in str(ce.value)
        assert "Setting auth.set_creation.as-set.prefix_required must be a bool" in str(ce.value)
        assert "Setting auth.set_creation.as-set.autnum_authentication must be one of" in str(ce.value)
        assert "Unknown setting key: auth.password_hashers.unknown-hash" in str(ce.value)
        assert "Setting auth.password_hashers.crypt-pw must be one of" in str(ce.value)
        assert "Access lists doesnotexist, invalid-list referenced in settings, but not defined." in str(
            ce.value
        )
        assert "Setting server.http.url is missing or invalid." in str(ce.value)
        assert "Setting server.http.status_access_list must be a string, if defined." in str(ce.value)
        assert "Invalid item in access list bad-list: IPv4 Address with more than 4 bytes." in str(ce.value)
        assert "Invalid item in prefix scopefilter: invalid-prefix" in str(ce.value)
        assert "Invalid item in asn scopefilter: invalid." in str(ce.value)
        assert "Invalid item in asn scopefilter: 10-invalid." in str(ce.value)
        assert "Setting sources contains reserved source name: RPKI" in str(ce.value)
        assert (
            "Setting suspension_enabled for source TESTDB can not be enabled without enabling authoritative."
            in str(ce.value)
        )
        assert "Setting keep_journal for source TESTDB can not be enabled unless either " in str(ce.value)
        assert (
            "Setting nrtm_host for source TESTDB can not be enabled without setting import_serial_source."
            in str(ce.value)
        )
        assert (
            "Setting authoritative for source TESTDB2 can not be enabled when either nrtm_host or"
            " import_source are set."
            in str(ce.value)
        )
        assert (
            "Setting authoritative for source TESTDB3 can not be enabled when either nrtm_host or"
            " import_source are set."
            in str(ce.value)
        )
        assert (
            "Source TESTDB can not have authoritative, import_source or nrtm_host set when readonly_standby"
            " is enabled."
            in str(ce.value)
        )
        assert (
            "Source TESTDB3 can not have authoritative, import_source or nrtm_host set when readonly_standby"
            " is enabled."
            in str(ce.value)
        )
        assert "Setting nrtm_port for source TESTDB2 must be a number." in str(ce.value)
        assert "Setting rpki.roa_import_timer must be set to a number." in str(ce.value)
        assert "Setting rpki.notify_invalid_subject must be a string, if defined." in str(ce.value)
        assert "Setting rpki.notify_invalid_header must be a string, if defined." in str(ce.value)
        assert "Setting import_timer for source TESTDB must be a number." in str(ce.value)
        assert "Setting export_timer for source TESTDB must be a number." in str(ce.value)
        assert "Setting route_object_preference for source TESTDB3 must be a number." in str(ce.value)
        assert "Setting route_object_preference.update_timer must be a number." in str(ce.value)
        assert "Setting nrtm_query_serial_range_limit for source TESTDB must be a number." in str(ce.value)
        assert "Invalid source name: lowercase" in str(ce.value)
        assert "Invalid source name: invalid char" in str(ce.value)
        assert "but rpki.notify_invalid_enabled is not set" in str(ce.value)
        assert "Setting sources_default contains unknown sources: DOESNOTEXIST-DB" in str(ce.value)
        assert "Source alias SOURCE-ALIAS contains reference to unknown source TESTDB-NOTEXIST" in str(
            ce.value
        )
        assert "Source alias name TESTDB2 conflicts with an already configured real source" in str(ce.value)
        assert "Invalid source alias name: invalid name" in str(ce.value)
        assert "Invalid log.level: INVALID" in str(ce.value)
        assert "Setting log.logging_config_path can not be combined" in str(ce.value)
        assert "Unknown setting key: unknown_setting" in str(ce.value)
        assert "Unknown setting key: log.unknown" in str(ce.value)
        assert "Unknown key(s) under source TESTDB: unknown" in str(ce.value)


class TestGetSetting:
    setting_name = "server.whois.interface"
    env_name = "IRRD_SERVER_WHOIS_INTERFACE"

    def test_get_setting_default(self, monkeypatch):
        monkeypatch.delenv(self.env_name, raising=False)
        assert get_setting(self.setting_name) == "::0"

    def test_get_setting_env(self, monkeypatch):
        monkeypatch.setenv(self.env_name, "env_value")
        assert get_setting(self.setting_name) == "env_value"

    def test_get_setting_unknown(self, monkeypatch):
        with pytest.raises(ValueError):
            get_setting("unknown")
        with pytest.raises(ValueError):
            get_setting("log.unknown")
        with pytest.raises(ValueError):
            get_setting("sources.TEST.unknown")
