#!/usr/bin/env python
# flake8: noqa: E402
import os
import sys

from irrd.updates.email import handle_email_update

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), '../'))


def main(data):
    handler = handle_email_update(data)
    print(handler.user_report())


if __name__ == "__main__":
    main(sys.stdin.read())
