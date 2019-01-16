#!/usr/bin/env python
# flake8: noqa: E402

"""
Submit a raw update message, i.e. without email headers.
This supports password/override attributes, but is not
compatible with PGP signatures.

The message is always read from stdin.

Prints a report of the results, which would otherwise
be sent to a user by e-mail.
"""
import argparse
import sys

from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from irrd.conf import config_init, CONFIG_PATH_DEFAULT
from irrd.updates.handler import ChangeSubmissionHandler


def main(data):
    handler = ChangeSubmissionHandler(data)
    print(handler.submitter_report())


if __name__ == '__main__':  # pragma: no cover
    description = """Process a raw update message, i.e. without email headers. Authentication is still checked, 
                     but PGP is not supported. Message is always read from stdin, and a report is printed to stdout."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    args = parser.parse_args()

    config_init(args.config_file_path)

    main(sys.stdin.read())
