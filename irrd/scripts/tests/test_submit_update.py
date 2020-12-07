from unittest.mock import Mock

from ..submit_changes import main
from ...updates.handler import ChangeSubmissionHandler


def test_submit_changes(capsys, monkeypatch):
    mock_update_handler = Mock(spec=ChangeSubmissionHandler)
    monkeypatch.setattr('irrd.scripts.submit_changes.ChangeSubmissionHandler', lambda: mock_update_handler)
    mock_update_handler.load_text_blob = lambda data: mock_update_handler
    mock_update_handler.submitter_report_human = lambda: 'output'

    main('test input')
    captured = capsys.readouterr().out
    assert captured == 'output\n'
