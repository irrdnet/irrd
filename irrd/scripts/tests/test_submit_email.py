from unittest.mock import Mock

from ..submit_email import run


def test_submit_email_success(capsys, monkeypatch):
    mock_handle_email = Mock()
    monkeypatch.setattr("irrd.scripts.submit_email.handle_email_submission", lambda data: mock_handle_email)
    mock_handle_email.user_report = lambda: "output"

    run("test input")


def test_submit_email_fail(capsys, monkeypatch, caplog):
    mock_handle_email = Mock(side_effect=Exception("expected-test-error"))
    monkeypatch.setattr("irrd.scripts.submit_email.handle_email_submission", mock_handle_email)

    run("test input")

    assert "expected-test-error" in caplog.text
    stdout = capsys.readouterr().out
    assert "An internal error occurred" in stdout
    assert "expected-test-error" not in stdout
