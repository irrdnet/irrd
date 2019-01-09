#!/usr/bin/env python
# flake8: noqa: E402
import argparse
import os
import sys

"""
Submit a raw e-mail message, i.e. with e-mail headers.
The message is always read from stdin.

A report on the results will be sent to the user by e-mail.
"""

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))))

from irrd.conf import config_init, CONFIG_PATH_DEFAULT
from irrd.updates.email import handle_email_submission


def run(data):
    handle_email_submission(data)


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
