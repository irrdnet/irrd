# flake8: noqa: W293
import textwrap
from unittest.mock import Mock

import pytest

from irrd.storage.database_handler import DatabaseHandler
from irrd.updates.email import handle_email_submission


@pytest.fixture()
def mock_email_dh(monkeypatch):
    mock_email = Mock()
    monkeypatch.setattr("irrd.utils.email.send_email", mock_email)

    mock_dh = Mock(spec=DatabaseHandler)
    monkeypatch.setattr("irrd.updates.handler.DatabaseHandler", mock_dh)

    yield mock_email, mock_dh


class TestHandleEmailSubmission:
    default_email = textwrap.dedent(
        """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        Subject: not my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: text/plain; charset=us-ascii
        X-Mailer: Python 3.7
        Content-Transfer-Encoding: 7bit
        Mime-Version: 1.0

        aut-num: AS12345
        """
    ).strip()

    def test_valid_plain(self, mock_email_dh, tmp_gpg_dir):
        mock_email, mock_dh = mock_email_dh
        handler = handle_email_submission(self.default_email)
        assert handler.request_meta["Message-ID"] == "<1325754288.4989.6.camel@hostname>"
        assert len(handler.results) == 1
        assert len(handler.results[0].error_messages)
        assert mock_email.mock_calls[0][0] == ""
        assert mock_email.mock_calls[0][1][0] == "Sasha <sasha@example.com>"
        assert mock_email.mock_calls[0][1][1] == "FAILED: my subject"
        assert "DETAILED EXPLANATION" in mock_email.mock_calls[0][1][2]

    def test_invalid_no_text_plain(self, mock_email_dh, tmp_gpg_dir):
        mock_email, mock_dh = mock_email_dh

        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: multipart/alternative;
         boundary="Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F"
        Mime-Version: 1.0 (Mac OS X Mail 10.3 
        To: sasha@localhost
        X-Mailer: Apple Mail (2.3273)

        --Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F
        Content-Transfer-Encoding: 7bit
        Content-Type: text/html;
            charset=us-ascii

        <html><head><meta http-equiv="Content-Type" content="text/html charset=us-ascii"></head><body style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;" class=""><b class="">test 1 2 3</b><div class=""><br class=""></div></body></html>
        --Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F--
        """
        ).strip()
        assert handle_email_submission(email) is None

        assert mock_email.mock_calls[0][0] == ""
        assert mock_email.mock_calls[0][1][0] == "Sasha <sasha@example.com>"
        assert mock_email.mock_calls[0][1][1] == "FAILED: my subject"
        assert "no text/plain" in mock_email.mock_calls[0][1][2]

    def test_handles_exception_email_parser(self, monkeypatch, caplog, tmp_gpg_dir):
        mock_email = Mock()
        monkeypatch.setattr("irrd.utils.email.send_email", mock_email)

        mock_parser = Mock(side_effect=Exception("test-error"))
        monkeypatch.setattr("irrd.utils.email.EmailParser", mock_parser)

        handle_email_submission(self.default_email)
        assert not mock_email.mock_calls
        assert "An exception occurred while attempting to send a reply to an submission: FAILED"
        assert "traceback for test-error follows" in caplog.text
        assert "test-error" in caplog.text

    def test_handles_exception_submission_request_handler(self, monkeypatch, caplog, tmp_gpg_dir):
        mock_email = Mock()
        monkeypatch.setattr("irrd.utils.email.send_email", mock_email)

        mock_handler = Mock(side_effect=Exception("test-error"))
        monkeypatch.setattr("irrd.updates.email.ChangeSubmissionHandler", mock_handler)

        handle_email_submission(self.default_email)

        assert mock_email.mock_calls[0][0] == ""
        assert mock_email.mock_calls[0][1][0] == "Sasha <sasha@example.com>"
        assert mock_email.mock_calls[0][1][1] == "ERROR: my subject"
        assert "internal error" in mock_email.mock_calls[0][1][2]

        assert "An exception occurred while attempting to send a reply to an submission: FAILED"
        assert "traceback for test-error follows" in caplog.text
        assert "test-error" in caplog.text

    def test_handles_exception_smtp(self, mock_email_dh, caplog, tmp_gpg_dir):
        mock_email, mock_dh = mock_email_dh
        mock_email.side_effect = Exception("test-error")

        handle_email_submission(self.default_email)

        assert mock_email.mock_calls[0][0] == ""
        assert mock_email.mock_calls[0][1][0] == "Sasha <sasha@example.com>"
        assert mock_email.mock_calls[0][1][1] == "FAILED: my subject"
        assert "DETAILED EXPLANATION" in mock_email.mock_calls[0][1][2]

        assert "An exception occurred while attempting to send a reply to an submission: FAILED"
        assert "traceback for test-error follows" in caplog.text
        assert "test-error" in caplog.text

    def test_invalid_no_from(self, mock_email_dh, caplog, tmp_gpg_dir):
        mock_email, mock_dh = mock_email_dh

        assert handle_email_submission("") is None
        assert not len(mock_email.mock_calls)
        assert "No from address was found" in caplog.text
