#!/usr/bin/env python
# flake8: noqa: E402
import argparse
import json
import sys
import textwrap
from typing import Iterator
from urllib import request
from urllib.error import HTTPError

"""
Read RPSL submissions from stdin, submit them to the
IRRD HTTP API and return a response on stdout.

This script is meant to be deployed on different hosts than
those that run IRRD, and therefore intentionally only has
no dependencies on other IRRD code or other dependencies.
This causes a bit of code duplication with other IRRD parts.
"""


def run(requests_text, url, debug=False, metadata=None):
    request_body = extract_request_body(requests_text)
    is_delete = request_body.get("delete_reason")
    if not request_body['objects']:
        print("ERROR: received empty input text", file=sys.stderr)
        return 2
    if is_delete and len(request_body['objects']) > 1:
        print("ERROR: deletions can not be mixed with other submissions", file=sys.stderr)
        return 2
    method = "DELETE" if is_delete else "POST"
    http_data = json.dumps(request_body).encode("utf-8")
    headers = {
        "User-Agent": "irr_rpsl_submit_v4",
    }
    if metadata:
        headers["X-irrd-metadata"] = json.dumps(metadata)
    http_request = request.Request(
        url,
        data=http_data,
        method=method,
        headers=headers,
    )
    if debug:
        print(
            f"Submitting to {url}; method {method}; headers {headers}; data {http_data}",
            file=sys.stderr,
        )
    try:
        http_response = request.urlopen(http_request, timeout=20)
        response = json.loads(http_response.read().decode("utf-8"))
    except HTTPError as err:
        message = err.read().decode("utf-8").replace("\n", ";")
        print(
            f"ERROR: response {err} from server: {message}",
            file=sys.stderr,
        )
        return 2

    if debug:
        print(f"response: {response}", file=sys.stderr)
    print(format_report(response))
    return 1 if response["summary"]["failed"] else 0


def extract_request_body(requests_text: str):
    """
    Parse change requests, a text of RPSL objects along with metadata like
    passwords or deletion requests.
    Returns a dict suitable as a JSON HTTP POST payload.
    """
    passwords = []
    overrides = []
    rpsl_texts = []
    delete_reason = ""

    requests_text = requests_text.replace("\r", "")
    for object_text in requests_text.split("\n\n"):
        object_text = object_text.strip()
        if not object_text:
            continue

        rpsl_text = ""

        # The attributes password/override/delete are meta attributes
        # and need to be extracted before parsing. Delete refers to a specific
        # object, password/override apply to all included objects.
        for line in object_text.strip("\n").split("\n"):
            if line.startswith("password:"):
                password = line.split(":", maxsplit=1)[1].strip()
                passwords.append(password)
            elif line.startswith("override:"):
                override = line.split(":", maxsplit=1)[1].strip()
                overrides.append(override)
            elif line.startswith("delete:"):
                delete_reason = line.split(":", maxsplit=1)[1].strip()
            else:
                rpsl_text += line + "\n"

        if rpsl_text:
            rpsl_texts.append(rpsl_text)

    result = {
        "objects": [{"object_text": rpsl_text} for rpsl_text in rpsl_texts],
        "passwords": passwords,
        "overrides": overrides,
        "delete_reason": delete_reason,
    }
    return result


def format_report(response):
    """Format an IRRD HTTP response into a human-friendly text."""
    s = response["summary"]
    user_report = textwrap.dedent(f"""
    SUMMARY OF UPDATE:

    Number of objects found:                  {s["objects_found"]:3}
    Number of objects processed successfully: {s["successful"]:3}
        Create:      {s["successful_create"]:3}
        Modify:      {s["successful_modify"]:3}
        Delete:      {s["successful_delete"]:3}
    Number of objects processed with errors:  {s["failed"]:3}
        Create:      {s["failed_create"]:3}
        Modify:      {s["failed_modify"]:3}
        Delete:      {s["failed_delete"]:3}

    DETAILED EXPLANATION:

    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """
    )
    for object_result in response["objects"]:
        user_report += "---\n"
        user_report += format_report_object(object_result)
        user_report += "\n"
    user_report += "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n"
    return user_report


def format_report_object(r):
    """Format an IRRD HTTP response for a specific object into a human-friendly text."""
    status = "succeeded" if r["successful"] else "FAILED"

    report = f'{r["type"]} {status}: [{r["object_class"]}] {r["rpsl_pk"]}\n'
    if r["info_messages"] or r["error_messages"]:
        if r["error_messages"]:
            report += "\n" + r["submitted_object_text"] + "\n"
        report += "".join([f"ERROR: {e}\n" for e in r["error_messages"]])
        report += "".join([f"INFO: {e}\n" for e in r["info_messages"]])
    return report


def main():  # pragma: no cover
    def metadata(input):
        try:
            return {item.split("=")[0]: item.split("=", 1)[1] for item in input.split(",")}
        except IndexError:
            raise ValueError()

    description = """
        Read RPSL submissions from stdin and return a response on stdout.
        Errors or debug info are printed to stderr.
        
        The input format must be plain RPSL objects, separated by double
        newlines, as used in emails documented on
        https://irrd.readthedocs.io/en/stable/users/database-changes/#submitting-over-e-mail .
        
        The exit code is 0 for complete success, 1 if the change was
        submitted but least some updates were rejected (e.g. invalid RPSL syntax),
        2 for an execution error.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-d",
        dest="debug",
        action="store_true",
        help=f"print additional debug output for admins to stderr",
    )
    parser.add_argument(
        "-m",
        dest="metadata",
        type=metadata,
        help=f"metadata sent in X-irrd-metadata header, in key=value format, separated by comma",
    )
    parser.add_argument(
        "-u",
        dest="url",
        type=str,
        required=True,
        help=f"IRRd submission API URL, e.g. https://rr.example.net/v1/submit/",
    )
    args = parser.parse_args()

    sys.exit(run(sys.stdin.read(), args.url, args.debug, args.metadata))


if __name__ == "__main__":  # pragma: no cover
    main()
