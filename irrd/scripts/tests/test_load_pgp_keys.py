from unittest.mock import Mock

import pytest

from irrd.utils.rpsl_samples import SAMPLE_KEY_CERT
from irrd.utils.test_utils import flatten_mock_calls

from ..load_pgp_keys import load_pgp_keys


@pytest.mark.usefixtures("tmp_gpg_dir")
def test_load_pgp_keys(capsys, monkeypatch):
    mock_dh = Mock()
    mock_dq = Mock()
    monkeypatch.setattr("irrd.scripts.load_pgp_keys.DatabaseHandler", lambda: mock_dh)
    monkeypatch.setattr("irrd.scripts.load_pgp_keys.RPSLDatabaseQuery", lambda column_names: mock_dq)

    mock_dh.execute_query = lambda q,: [
        {
            "rpsl_pk": "PGPKEY-80F238C6",
            "object_text": SAMPLE_KEY_CERT,
        },
        {
            "rpsl_pk": "PGPKEY-BAD",
            "object_text": SAMPLE_KEY_CERT.replace("rpYI", "a"),
        },
    ]

    load_pgp_keys("TEST")
    assert flatten_mock_calls(mock_dh) == [
        ["close", (), {}],
    ]
    assert flatten_mock_calls(mock_dq) == [
        ["sources", (["TEST"],), {}],
        ["object_classes", (["key-cert"],), {}],
    ]
    output = capsys.readouterr().out
    assert "Loading key-cert PGPKEY-80F238C6" in output
    assert "Loading key-cert PGPKEY-BAD" in output
    assert "Unable to read public PGP key" in output
