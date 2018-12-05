import os

import pytest


def flatten_mock_calls(mock):
    """
    Flatten the calls performed on a particular mock object,
    into a list of calls with arguments.
    """
    result = []
    for call in mock.mock_calls:
        call = list(call)
        call_name = call[0]
        if '.' in str(call_name):
            call_name = str(call_name).split('.')[-1]
        result.append([call_name] + call[1:])
    return result


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
