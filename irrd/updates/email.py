# flake8: noqa: W293
import logging
import textwrap
from typing import Optional

from irrd.utils import email
from .handler import ChangeSubmissionHandler

logger = logging.getLogger(__name__)


def handle_email_submission(email_txt: str) -> Optional[ChangeSubmissionHandler]:
    handler = None
    try:
        msg = email.EmailParser(email_txt)
        request_meta = {
            'Message-ID': msg.message_id,
            'From': msg.message_from,
            'Date': msg.message_date,
            'Subject': msg.message_subject,
        }
    except Exception as exc:
        logger.critical(f'An exception occurred while attempting to parse the following update e-mail: {email_txt}\n'
                        f'--- traceback for {exc} follows:', exc_info=exc)
        return None

    if not msg.message_from:
        logger.critical(f'No from address was found while attempting to parse the following update e-mail - '
                        f'update not processed: {email_txt}\n')
        return None

    try:
        if not msg.body:
            logger.warning(f'Unable to extract message body from e-mail {msg.message_id} from {msg.message_from}')
            subject = f'FAILED: {msg.message_subject}'
            reply_content = textwrap.dedent(f"""
            Unfortunately, your message with ID {msg.message_id}
            could not be processed, as no text/plain part could be found.
            
            Please try to resend your message as plain text email.
            """)
        else:
            handler = ChangeSubmissionHandler().load_text_blob(msg.body, msg.pgp_fingerprint, request_meta)
            logger.info(f'Processed e-mail {msg.message_id} from {msg.message_from}: {handler.status()}')
            logger.debug(f'Report for e-mail {msg.message_id} from {msg.message_from}: {handler.submitter_report_human()}')

            subject = f'{handler.status()}: {msg.message_subject}'
            reply_content = handler.submitter_report_human()

    except Exception as exc:
        logger.critical(f'An exception occurred while attempting to process the following update: {email_txt}\n'
                        f'--- traceback for {exc} follows:', exc_info=exc)
        subject = f'ERROR: {msg.message_subject}'
        reply_content = textwrap.dedent(f"""
        Unfortunately, your message with ID {msg.message_id}
        could not be processed, due to an internal error.
        """)

    try:
        email.send_email(msg.message_from, subject, reply_content)
        if handler:
            handler.send_notification_target_reports()
    except Exception as exc:
        logger.critical(f'An exception occurred while attempting to send a reply to an update: '
                        f'{subject}\n{reply_content}\n --- traceback for {exc} follows:', exc_info=exc)

    return handler


