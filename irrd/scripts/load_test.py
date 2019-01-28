#!/usr/bin/env python
# flake8: noqa: E402

"""
A simple load tester for IRRd.
Sends random !g queries.
"""
import time

import argparse
import random
import socket


def main(host, port, count):
    queries = [b'!!\n']
    for i in range(count):
        asn = random.randrange(1, 50000)
        query = f'!gAS{asn}\n'.encode('ascii')
        queries.append(query)
    queries.append(b'!q\n')

    s = socket.socket()
    s.settimeout(600)
    s.connect((host, port))

    queries_str = b''.join(queries)
    s.sendall(queries_str)

    start_time = time.perf_counter()
    while 1:
        data = s.recv(1024*1024)
        if not data:
            break

    elapsed = time.perf_counter() - start_time
    time_per_query = elapsed / count * 1000
    qps = int(count / elapsed)
    print(f'Ran {count} queries in {elapsed}s, time per query {time_per_query} ms, {qps} qps')


if __name__ == '__main__':  # pragma: no cover
    description = """A simple load tester for IRRd. Sends random !g queries."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--count', dest='count', type=int, default=5000,
                        help=f'number of queries to run (default: 5000)')
    parser.add_argument('host', type=str,
                        help='hostname of instance')
    parser.add_argument('port', type=int,
                        help='port of instance')
    args = parser.parse_args()

    main(args.host, args.port, args.count)
