from unittest.mock import Mock

from irrd.utils.test_utils import flatten_mock_calls

from ..mirror_force_reload import set_force_reload


def test_set_force_reload(capsys, monkeypatch, config_override):
    mock_dh = Mock()
    monkeypatch.setattr("irrd.scripts.mirror_force_reload.DatabaseHandler", lambda: mock_dh)

    config_override({"sources": {"TEST": {"nrtm_host": "host"}}})
    set_force_reload("TEST")
    assert flatten_mock_calls(mock_dh) == [
        ["set_force_reload", ("TEST",), {}],
        ["commit", (), {}],
        ["close", (), {}],
    ]
    assert not capsys.readouterr().out

    config_override(
        {
            "sources": {
                "TEST": {
                    "nrtm4_client_notification_file_url": "url",
                    "nrtm4_client_initial_public_key": "key",
                }
            }
        }
    )
    set_force_reload("TEST")
    assert "existing NRTMv4 client key" in capsys.readouterr().out

    mock_dh.reset_mock()
    config_override({"sources": {"TEST": {}}})
    set_force_reload("TEST")
    assert "can only set the" in capsys.readouterr().out
    assert not mock_dh.mock_calls
