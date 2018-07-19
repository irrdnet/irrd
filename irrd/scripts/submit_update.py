#!/usr/bin/env python
import sys

from irrd.updates.handler import UpdateRequestHandler


def main():
    handler = UpdateRequestHandler()
    data = sys.stdin.read()
    report = handler.handle_object_texts(data)
    print(report)


if __name__ == "__main__":
    main()
