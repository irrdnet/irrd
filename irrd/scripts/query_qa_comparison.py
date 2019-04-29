#!/usr/bin/env python
# flake8: noqa: E402
"""
This script will run a list of queries against two IRRD instances,
and report significant results.
"""

import argparse
import difflib
import sys

import re
from IPy import IP
from ordered_set import OrderedSet
from pathlib import Path
from typing import Optional


sys.path.append(str(Path(__file__).resolve().parents[2]))

from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.utils.text import splitline_unicodesafe, split_paragraphs_rpsl
from irrd.utils.whois_client import whois_query_irrd, whois_query, WhoisQueryError


SSP_QUERIES = ['!6', '!g', '!i']
ASDOT_RE = re.compile(r'as\d+\.\d*', flags=re.IGNORECASE)


class QueryComparison:
    queries_run = 0
    queries_different = 0
    queries_both_error = 0
    queries_invalid = 0
    queries_mirror = 0

    def __init__(self, input_file, host_reference, port_reference, host_tested, port_tested):
        self.host_reference = host_reference
        self.port_reference = port_reference
        self.host_tested = host_tested
        self.port_tested = port_tested

        if input_file == '-':
            f = sys.stdin
        else:
            f = open(input_file, encoding='utf-8', errors='backslashreplace')

        for query in f.readlines():
            query = query.strip() + '\n'
            if query == '!!\n':
                continue
            self.queries_run += 1
            error_reference = None
            error_tested = None
            response_reference = None
            response_tested = None

            # ignore version or singular source queries
            if query.lower().startswith('!v') or query.lower().startswith('!s'):
                continue

            if (query.startswith('-x') and not query.startswith('-x ')) or re.search(ASDOT_RE, query):
                self.queries_invalid += 1
                continue

            # ignore queries asking for NRTM data or mirror serial status
            if query.lower().startswith('-g ') or query.lower().startswith('!j'):
                self.queries_mirror += 1
                continue

            if query.startswith('!'):  # IRRD style query
                try:
                    response_reference = whois_query_irrd(self.host_reference, self.port_reference, query)
                except ConnectionError as ce:
                    error_reference = str(ce)
                except WhoisQueryError as wqe:
                    error_reference = str(wqe)
                except ValueError:
                    print(f'Query response to {query} invalid')
                    continue
                try:
                    response_tested = whois_query_irrd(self.host_tested, self.port_tested, query)
                except WhoisQueryError as wqe:
                    error_tested = str(wqe)
                except ValueError:
                    print(f'Query response to {query} invalid')
                    continue

            else:  # RIPE style query
                try:
                    response_reference = whois_query(self.host_reference, self.port_reference, query)
                except ConnectionError as ce:
                    error_reference = str(ce)
                response_tested = whois_query(self.host_tested, self.port_tested, query)

            # If both produce error messages, don't compare them
            both_error = error_reference and error_tested
            both_comment = (response_reference and response_tested and
                            response_reference.strip() and response_tested.strip() and
                            response_reference.strip()[0] == '%' and response_tested.strip()[0] == '%')
            if both_error or both_comment:
                self.queries_both_error += 1
                continue

            try:
                cleaned_reference = self.clean(query, response_reference)
            except ValueError as ve:
                print(f'Invalid reference response to query {query.strip()}: {response_reference}: {ve}')
                continue

            try:
                cleaned_tested = self.clean(query, response_tested)
            except ValueError as ve:
                print(f'Invalid tested response to query {query.strip()}: {response_tested}: {ve}')
                continue

            if cleaned_reference != cleaned_tested:
                self.queries_different += 1
                self.write_inconsistency_report(query, cleaned_reference, cleaned_tested)

        print(f'Ran {self.queries_run} objects, {self.queries_different} had different results, '
              f'{self.queries_both_error} produced errors on both instances, '
              f'{self.queries_invalid} invalid queries were skipped, '
              f'{self.queries_mirror} NRTM queries were skipped')

    def clean(self, query: str, response: Optional[str]) -> Optional[str]:
        """Clean the query response, so that the text can be compared."""
        if not response:
            return response
        irr_query = query[:2].lower()
        response = response.strip().lower()

        cleaned_result_list = None
        if irr_query in SSP_QUERIES or (irr_query == '!r' and query.lower().strip().endswith(',o')):
            cleaned_result_list = response.split(' ')
        if irr_query in ['!6', '!g'] and cleaned_result_list:
            cleaned_result_list = [str(IP(ip)) for ip in cleaned_result_list]
        if cleaned_result_list:
            return ' '.join(sorted(list(set(cleaned_result_list))))
        else:
            new_responses = []
            for paragraph in split_paragraphs_rpsl(response):
                rpsl_obj = rpsl_object_from_text(paragraph.strip(), strict_validation=False)
                new_responses.append(rpsl_obj)

            new_responses.sort(key=lambda i: i.parsed_data.get('source', '') + i.rpsl_object_class + i.pk())
            texts = [r.render_rpsl_text() for r in new_responses]
            return '\n'.join(OrderedSet(texts))

    def write_inconsistency_report(self, query, cleaned_reference, cleaned_tested):
        """Write a report to disk with details of the query response inconsistency."""
        report = open(f'qout/QR {query.strip().replace("/", "S")[:30]}', 'w')
        diff_str = self.render_diff(query, cleaned_reference, cleaned_tested)
        report.write(query.strip() + '\n')
        report.write('\n=================================================================\n')
        if diff_str:
            report.write(f'~~~~~~~~~[ diff clean ref->tst ]~~~~~~~~~\n')
            report.write(diff_str + '\n')
        report.write(f'~~~~~~~~~[ clean ref {self.host_reference}:{self.port_reference} ]~~~~~~~~~\n')
        report.write(str(cleaned_reference) + '\n')
        report.write(f'~~~~~~~~~[ clean tst {self.host_tested}:{self.port_tested} ]~~~~~~~~~\n')
        report.write(str(cleaned_tested) + '\n')
        report.write('\n=================================================================\n')
        report.close()

    def render_diff(self, query: str, cleaned_reference: str, cleaned_tested: str) -> Optional[str]:
        """Produce a diff between the results, either by line or with queries like !i, by element returned."""
        if not cleaned_reference or not cleaned_tested:
            return None

        irr_query = query[:2].lower()
        if irr_query in SSP_QUERIES or (irr_query == '!r' and query.lower().strip().endswith(',o')):
            diff_input_reference = list(cleaned_reference.split(' '))
            diff_input_tested = list(cleaned_tested.split(' '))
        else:
            diff_input_reference = list(splitline_unicodesafe(cleaned_reference))
            diff_input_tested = list(splitline_unicodesafe(cleaned_tested))
        diff = list(difflib.unified_diff(diff_input_reference, diff_input_tested, lineterm=''))
        diff_str = '\n'.join(diff[2:])  # skip the lines from the diff which would have filenames
        return diff_str


def main():  # pragma: no cover
    description = """Run a list of queries against two IRRD instances, and report significant results."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('input_file', type=str,
                        help='the name of a file to read containing queries, or - for stdin')
    parser.add_argument('host_reference', type=str,
                        help='host/IP of the reference IRRD server')
    parser.add_argument('port_reference', type=int,
                        help='port for the reference IRRD server')
    parser.add_argument('host_tested', type=str,
                        help='host/IP of the tested IRRD server')
    parser.add_argument('port_tested', type=int,
                        help='port for the tested IRRD server')
    args = parser.parse_args()

    QueryComparison(args.input_file, args.host_reference, args.port_reference, args.host_tested, args.port_tested)


if __name__ == '__main__':
    main()
