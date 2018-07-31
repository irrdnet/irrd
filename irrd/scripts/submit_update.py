#!/usr/bin/env python
import sys

from irrd.updates.handler import UpdateRequestHandler


def main(data):
    handler = UpdateRequestHandler(data)
    print(handler.user_report())


if __name__ == "__main__":
    main(sys.stdin.read())
