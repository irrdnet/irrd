#!/usr/bin/env python
# flake8: noqa: E402

"""
Submit a raw update message, i.e. without e-mail headers.
This supports password/override attributes, but is not
compatible with PGP signatures.

The message is always read from stdin.

Prints a report of the results, which would otherwise
be sent to a user by e-mail.
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), '../'))

from irrd.updates.handler import ChangeSubmissionHandler


def main(data):
    handler = ChangeSubmissionHandler(data)
    print(handler.submitter_report())


if __name__ == "__main__":
    main(sys.stdin.read())
