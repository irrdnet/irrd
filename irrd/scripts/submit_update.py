#!/usr/bin/env python
# flake8: noqa: E402
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), '../'))

from irrd.updates.handler import UpdateRequestHandler


def main(data):
    handler = UpdateRequestHandler(data)
    print(handler.user_report())


if __name__ == "__main__":
    main(sys.stdin.read())
