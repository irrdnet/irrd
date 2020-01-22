#!/usr/bin/env python
# flake8: noqa: E402

import sys

import argparse
import logging
from pathlib import Path

"""
Submit a raw e-mail message, i.e. with e-mail headers.
The message is always read from stdin.

A report on the results will be sent to the user by e-mail.
"""

logger = logging.getLogger(__name__)
sys.path.append(str(Path(__file__).resolve().parents[2]))

from irrd.conf import config_init, CONFIG_PATH_DEFAULT
from irrd.updates.email import handle_email_submission


def run(data):
    try:
        handle_email_submission(data)
    except Exception as exc:
        logger.critical(f'An exception occurred while attempting to process the following email: {data}', exc_info=exc)
        print('An internal error occurred while processing this email.')


def main():  # pragma: no cover
    description = """Process a raw email message with requested changes. Authentication is checked, message
                     is always read from stdin. A report is sent to the user by email, along with any
                     notifications to mntners and others."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    args = parser.parse_args()

    config_init(args.config_file_path)

    run(sys.stdin.read())


if __name__ == '__main__':  # pragma: no cover
    main()
