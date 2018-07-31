from unittest.mock import Mock

from ..submit_update import main


def test_submit_update(capsys, monkeypatch):
    mock_update_handler = Mock()
    monkeypatch.setattr("irrd.scripts.submit_update.UpdateRequestHandler", lambda data: mock_update_handler)
    mock_update_handler.user_report = lambda: 'output'

    main('test input')
    captured = capsys.readouterr().out
    assert captured == 'output\n'
