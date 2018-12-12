from unittest.mock import Mock

from ..submit_email import main


def test_submit_email(capsys, monkeypatch):
    mock_update_handler = Mock()
    monkeypatch.setattr("irrd.scripts.submit_email.handle_email_submission", lambda data: mock_update_handler)
    mock_update_handler.user_report = lambda: 'output'

    main('test input')
