import os

import pytest
import yaml
from dotted.collection import DottedDict
from typing import Dict, Any

from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.utils.rpsl_samples import SAMPLE_KEY_CERT


@pytest.fixture()
def config_override(monkeypatch):
    """
    Fixture to override part of the configuration, by providing a dict
    with new config data.

    Note that subsequent calls override previous ones, so the entire
    override dict must be supplied every time.
    """
    def _override(override_data: Dict[Any, Any]):
        monkeypatch.setattr('irrd.conf.overrides', DottedDict(override_data))
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
    import sys
    sys._called_from_test = True
