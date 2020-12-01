"""
Testing configuration, used by py.test.
Fixtures defined here are available to all tests.
"""
import os
import pytest
from typing import Dict, Any

from irrd import conf
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.utils.rpsl_samples import SAMPLE_KEY_CERT
from irrd.vendor.dotted.collection import DottedDict


@pytest.fixture()
def config_override(monkeypatch):
    """
    Fixture to override part of the configuration, by providing a dict
    with new config data.

    Note that subsequent calls override previous ones, so the entire
    override dict must be supplied every time.
    """
    def _override(override_data: Dict[Any, Any]):
        monkeypatch.setattr('irrd.conf.testing_overrides', DottedDict(override_data))
    return _override


@pytest.fixture()
def tmp_gpg_dir(tmpdir, monkeypatch):
    """
    Fixture to use a temporary separate gpg dir, to prevent it using your
    user's keyring.

    NOTE: if the gpg keyring name is very long, this introduces a 5 second
    delay in all gpg tests due to gpg incorrectly waiting to find a gpg-agent.
    Default tmpdirs on Mac OS X are affected, to prevent this run pytest with:
        --basetemp=.tmpdirs
    """
    os.environ['IRRD_AUTH_GNUPG_KEYRING'] = str(tmpdir) + "/gnupg"


@pytest.fixture()
def preload_gpg_key():
    """
    Fixture to load a known PGP key into the configured keychain.
    """
    # Simply parsing the key-cert will load it into the GPG keychain
    rpsl_text = SAMPLE_KEY_CERT
    rpsl_object_from_text(rpsl_text)


def pytest_configure(config):
    """
    This function is called by py.test, and will set a flag to
    indicate tests are running. This is used by the configuration
    checker to not require a full working config for most tests.
    Can be checked with:
        hasattr(sys, '_called_from_test')
    Note that this function is only called once, not for every test.
    """
    import sys
    sys._called_from_test = True


@pytest.fixture(autouse=True)
def reset_config():
    """
    This fixture is called for every test in the project,
    and resets the configuration to default.
    """
    conf.config_init(None)
    conf.testing_overrides = None
