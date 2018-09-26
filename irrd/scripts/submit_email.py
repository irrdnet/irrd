#!/usr/bin/env python
# flake8: noqa: E402
import os
import sys

from irrd.updates.email import handle_email_update

"""
Submit a raw e-mail message, i.e. with e-mail headers.
The message is always read from stdin.

A report on the results will be sent to the user by e-mail.
"""

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), '../'))


def main(data):
    handle_email_update(data)


if __name__ == "__main__":
    main(sys.stdin.read())
