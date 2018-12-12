from unittest.mock import Mock

from ..submit_changes import main


def test_submit_changes(capsys, monkeypatch):
    mock_update_handler = Mock()
    monkeypatch.setattr("irrd.scripts.submit_changes.ChangeSubmissionHandler", lambda data: mock_update_handler)
    mock_update_handler.submitter_report = lambda: 'output'

    main('test input')
    captured = capsys.readouterr().out
    assert captured == 'output\n'
