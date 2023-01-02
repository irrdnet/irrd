#!/usr/bin/env python
# flake8: noqa: E402
"""
Read RPSL submissions from stdin, submit them to the
IRRD HTTP API and return a response on stdout.

This script is meant to be deployed on different hosts than
those that run IRRD, and therefore intentionally only has
no dependencies on other IRRD code or other dependencies.
This causes a bit of code duplication with other IRRD parts.

This code was contributed by MERIT (https://www.merit.edu) for
use with RADb.
"""

import argparse
import json
import logging
import os
import re
import socket
import sys
import textwrap
from json import JSONDecodeError
from urllib import request
from urllib.error import HTTPError, URLError

logging.basicConfig(
    level=logging.INFO,
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    format="{asctime} {levelname} {filename}:{lineno}: {message}",
)
logger = logging.getLogger(__name__)
logger.disabled = True


class BlankLinesHelpFormatter(argparse.HelpFormatter):
    """
    A formatter to allow argparse to respect blank lines
    """

    # textwrap doesn't understand multiple paragraphs, so
    # we split on paras then wrap each individually
    def _fill_text(self, text, width, indent):
        paras = text.split("\n\n")

        for i, para in enumerate(paras):
            if re.match(r"\s", para):
                continue
            paras[i] = textwrap.fill(para, width, initial_indent=indent, subsequent_indent=indent)

        return "\n\n".join(paras)


class SysExitValues:
    """
    A set of exit values for sys.exit
    """

    # pylint: disable=C0103,C0116,C0321,E0211
    @classmethod
    def Success(cls):
        return 0

    @classmethod
    def ChangeRejected(cls):
        return 1

    @classmethod
    def ArgumentMisuse(cls):
        return 2

    @classmethod
    def InputError(cls):
        return 4

    @classmethod
    def NetworkError(cls):
        return 8

    @classmethod
    def ResponseError(cls):
        return 16

    @classmethod
    def GeneralError(cls):
        return 32


class XBasic(Exception):
    def __init__(self, message=""):
        self.message = message

    def exit_value(self):  # pragma: no cover
        """
        Returns the exit value for a general error. This usually means
        that a derived class did not specify an exit value.
        """
        logger.debug("Calling XBasic.exit_value because {self.__class__.__name__} did not define its own")
        SysExitValues.GeneralError()

    def log(self):
        """
        Handle logging. Derived classes can decide how to log if
        they want to do something different or not log at all.
        """
        logger.critical(self.message)

    def report(self):
        """
        Handle user reporting on standard error. Derived classes can
        decide how to report if they want to do something different or
        not report at all.
        """
        sys.stderr.write(f"{self.message}\n")

    def warn_and_exit(self):
        """
        Output an error message the exit the program with the
        right exit value.
        """
        self.log()
        self.report()
        sys.exit(self.exit_value())


class XArgumentError(XBasic):
    """
    Stand in for the various exceptions raised in argparser.

    Mostly to lump in SystemExit with ArgumentError because we
    might be on a version earlier than Python 3.9 where we can
    turn off argparse's exit_on_error
    """

    def exit_value(self):
        """
        Return the exit value for this type of error.
        """
        return SysExitValues.ArgumentMisuse()


class XArgumentProcessing(XBasic):
    """
    Used for errors related to the semantic meaning of arguments after
    they have been parsed
    """

    pass


class XHelp(XBasic):
    """
    Raised for argparse's help, which uses a non-zero exit. If we
    asked for a help message and got one, that's successful.
    """

    def exit_value(self):
        """
        Return the exit value for this type of error.
        """
        return SysExitValues.Success()

    def log(self):
        pass

    def report(self):
        pass


class XInput(XBasic):
    """
    General exception type for problems related to the RPSL input.
    """

    def exit_value(self):
        """
        Return the exit value for this type of error.
        """
        return SysExitValues.InputError()


class XNetwork(XBasic):
    """
    General exception type for network problems.
    """

    def __init__(self, message, extra=""):
        self.message = f"{self.prefix()}: {message}"
        self.extra = extra

    def exit_value(self):
        """
        Return the exit value for this type of error.
        """
        return SysExitValues.NetworkError()

    def prefix(self):
        """
        Returns the prefix to attach to the start of each logged message.
        """
        return "Network error"


# Don't alphabetize these classes because the base class has to
# appear before any class that uses it. Done that twice already
# forgetting that.
class XHTTPConnectionFailed(XNetwork):
    """
    Raised when urllib cannot connect to the URL.

    This is a refinement of HTTPError, which is not granular enough
    to provide useful information to consumers.
    """

    def prefix(self):
        """
        Returns the prefix to attach to the start of each logged message.
        """
        return "Connection refused"  # pragma: no cover


class XHTTPNotFound(XNetwork):
    """
    Raised when the response returns 404.

    This is a refinement of HTTPError, which is not granular enough
    to provide useful information to consumers.
    """

    def prefix(self):
        """
        Returns the prefix to attach to the start of each logged message.
        """
        return "Not found"


class XNameResolutionFailed(XNetwork):
    """
    Raised when urllib cannot resolve the URL host.

    This is a refinement of HTTPError, which is not granular enough
    to provide useful information to consumers.
    """

    def prefix(self):
        """
        Returns the prefix to attach to the start of each logged message.
        """
        return "Could not resolve host"


class XNoObjects(XInput):
    """
    Raised when there are no RPSL objects. There must be at least
    one object in the input.
    """

    pass


class XResponse(XBasic):
    def __init__(self, message, extra):
        self.message = f"{self.prefix()}: {message}"
        self.extra = extra

    def exit_value(self):
        """
        Return the exit value for this type of error.
        """
        return SysExitValues.ResponseError()

    def prefix(self):
        """
        Returns the prefix to attach to the start of each logged message.
        """
        return "Response error"


class XTooManyObjects(XInput):
    """
    Raised when there a delete operation gets more than one RPSL object.
    IRRdv4 requires that any delete operation have exactly one object
    in the request.
    """

    def __init__(self):
        super().__init__("There was more than one RPSL object. " + "A delete must have exactly one object.")


def run(options):
    """
    The entry point for irr_rpsl_submit. It takes the command line
    options for the program and reads the RPSL input. It makes the
    request and translates the result to the right output and exit
    status.
    """

    try:
        args = get_arguments(options)
        rpsl = get_rpsl()
        result = make_request(rpsl, args)
        output = handle_output(args, result)
        print(output)
    except XBasic as error:
        error.warn_and_exit()
    except Exception as error:
        sys.stderr.write(f"Some other error: {type(error).__name__} • {error}\n")
        logger.fatal("Some other error with input (%s): %s", type(error).__name__, error)
        sys.exit(SysExitValues.GeneralError())

    exit_code = SysExitValues.Success()
    if at_least_one_change_was_rejected(result):
        exit_code = SysExitValues.ChangeRejected()
    sys.exit(exit_code)


def get_arguments(options):
    """
    Process the program options and return them.
    """
    args = process_args(options)
    logger.debug("Args are: %s", args)
    return args


def get_rpsl():
    """
    Get the RPSL.
    """
    rpsl = get_input()
    logger.debug("Input: ===\n%s\n===\n", rpsl)
    return rpsl


def make_request(rpsl, args):
    """
    Talk to the server.
    """
    try:
        result = send_request(rpsl, args)
    except (HTTPError, URLError) as error:
        logger.debug("HTTP problem: %s = %s", args.url, error.reason)
        reason = re.sub(r"^.*?\]\s*", "", f"{error.reason}")
        message = f"{args.url} = {reason}"
        raise XNetwork(message, [rpsl, args]) from error
    except json.decoder.JSONDecodeError as error:
        # turns out testing with www.example.com returns a real response
        # that's not the JSON we were expecting.
        message = f"HTTP response error decoding JSON: {error}"
        raise XResponse(message, [rpsl, args]) from error

    return result


def handle_output(args, result):
    """
    Turn the server's response to user output.
    """
    if args.output_json:
        formatted_output = format_as_json(result)
    elif args.output_text:
        formatted_output = format_as_text(result)
    else:
        formatted_output = format_as_default(result)

    return formatted_output


def add_irrdv3_options(parser):
    """
    Add the legacy options for irrdv3 so argparse can process them.
    Some options will be ignored, and others will be translated to
    the right values the requests need.
    """
    prefix = "(IRRdv3 no-op)"

    irr3_legacy_group = parser.add_argument_group(
        "irrdv3 compatibility", "these arguments are ignored and exist only to accept legacy calls"
    )
    irr3_legacy_group.add_argument(
        "-c",
        dest="crypt_password",
        metavar="CRYPT_PASSWD",
        type=str,
        help=f"{prefix} <crypted password> (default 'foo')",
    )
    irr3_legacy_group.add_argument(
        "-D",
        dest="inetd_mode",
        action="store_true",
        help=f"{prefix} Inetd mode, read/write to STDIN/STDOUT",
    )
    irr3_legacy_group.add_argument(
        "-E",
        dest="db_admin_email",
        metavar="DB_ADMIN_EMAIL",
        type=str,
        help=f"{prefix} DB admin address for new maintainer requests",
    )
    irr3_legacy_group.add_argument(
        "-f",
        dest="config_file",
        metavar="PATH",
        type=str,
        help=f"{prefix} IRRd config file location",
    )
    irr3_legacy_group.add_argument(
        "-F",
        dest="footer",
        metavar="FOOTER",
        type=str,
        help=f'{prefix} " enclosed response footer string',
    )
    irr3_legacy_group.add_argument(
        "-l",
        dest="log_directory",
        metavar="DIR",
        type=str,
        help=f"{prefix} log directory",
    )
    irr3_legacy_group.add_argument(
        "-M",
        dest="mail_auth",
        action="store_true",
        help=f"{prefix} allow MAIL-FROM auth",
    )
    irr3_legacy_group.add_argument(
        "-N",
        dest="permit_inetnum",
        action="store_true",
        help=f"{prefix} permit inetnum/domain objects",
    )
    irr3_legacy_group.add_argument(
        "-O",
        dest="forwarding_host",
        metavar="STR",
        type=str,
        help=f'{prefix} " enclosed host/IP web origin string',
    )
    irr3_legacy_group.add_argument(
        "-p",
        dest="port",
        metavar="PORT",
        type=str,
        help="IRRd port",
    )
    irr3_legacy_group.add_argument(
        "-r",
        dest="pgp_dir",
        metavar="PGP_DIR",
        type=str,
        help=f"{prefix} pgp directory",
    )
    irr3_legacy_group.add_argument(
        "-R",
        dest="{prefix} rps_mode",
        action="store_true",
        help=f"{prefix} RPS Dist mode",
    )
    irr3_legacy_group.add_argument(
        "-s",
        dest="source",
        metavar="SOURCE",
        type=str,
        help=f"{prefix} <DB source> source is authoritative",
    )
    irr3_legacy_group.add_argument(
        "-x",
        dest="disable_notifications",
        action="store_true",
        help=f"{prefix} do not send notifications",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-j",
        default=False,
        dest="output_json",
        action="store_true",
        help="output JSON summary of operation (default)",
    )
    group.add_argument(
        "-t",
        default=False,
        dest="output_text",
        action="store_true",
        help="output a text summary of operation (default off)",
    )


def adjust_args(args):
    """
    Adjust the argument list after processing, for special circumstances
    """
    # can't do this in argparse because debug is not a string type
    if args.debug:
        logger.disabled = False
        logger.setLevel("DEBUG")  # Python 3.2 accepts strings

    choose_url(args)

    logger.debug("URL is %s", args.url)

    return args


def at_least_one_change_was_rejected(result):
    """
    Return True if at least one RPSL object was rejected, and False otherwise.
    """
    return result["summary"]["failed"] > 0


def choose_url(args):
    """
    Set the args.url value to the appropriate value for the combination
    of -h, -p, and -u.  This converts legacy irrdv3 calls to the IRRdv4
    API endpoint.

    argparse takes care of allowing only -u or -h. At least one of those
    should already be present.
    """

    if args.host:
        scheme = "http"
        hostport = args.host

        if args.port:
            # we don't validate hosts, so there might already be a
            # port attached to it. That's fine, but if -p is specified,
            # prefer that one.
            hostport = re.sub(r":.*", "", hostport)
            hostport += f":{args.port}"

        args.url = f"{scheme}://{hostport}/v1/submit/"
    elif not args.url:
        raise XArgumentProcessing("choose_url did not get a host or url in the command-line arguments")


def create_http_request(requests_text, args):
    metadata = args.metadata
    url = args.url

    logger.debug("url: %s", url)
    request_body = create_request_body(requests_text)
    is_delete = request_body.get("delete_reason")

    if not request_body["objects"]:
        raise XNoObjects("No RPSL objects were found after processing input.")
    if is_delete and len(request_body["objects"]) > 1:
        raise XTooManyObjects()

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
    logger.debug("Submitting to %s; method %s}; headers %s; data %s", url, method, headers, http_data)

    return http_request


def create_request_body(rpsl: str):
    """
    Parse change requests, a text of RPSL objects along with metadata like
    passwords or deletion requests.

    Returns a dict suitable as a JSON HTTP POST payload.
    """
    passwords = []
    override = None
    rpsl_texts = []
    delete_reason = ""

    rpsl = rpsl.replace("\r", "")
    for object_text in rpsl.split("\n\n"):
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
                password = line.split(":", maxsplit=1)[1].strip()
                logger.debug("override password is %s", password)
                if override is not None and password != override:
                    raise XInput("override encountered twice with different values")
                override = password
            elif line.startswith("delete:"):
                delete_reason = line.split(":", maxsplit=1)[1].strip()
            else:
                rpsl_text += line + "\n"

        if rpsl_text:
            rpsl_texts.append(rpsl_text)

    result = {
        "objects": [{"object_text": rpsl_text} for rpsl_text in rpsl_texts],
        "passwords": passwords,
        "override": override,
        "delete_reason": delete_reason,
    }
    return result


def format_as_default(response):
    """
    Format that raw response as whatever we decide the default is.
    """
    return format_as_text(response)


def format_as_json(response):
    """
    Format that raw response as JSON. This is basically no formatting
    since it passes through the data structure that the IRRd returned.
    """
    return json.dumps(response)


def format_as_text(response):
    """
    Format an IRRd HTTP response into a human-friendly text.
    """
    summary = response["summary"]
    user_report = textwrap.dedent(
        f"""
    SUMMARY OF UPDATE:

    Number of objects found:                  {summary["objects_found"]:3}
    Number of objects processed successfully: {summary["successful"]:3}
        Create:      {summary["successful_create"]:3}
        Modify:      {summary["successful_modify"]:3}
        Delete:      {summary["successful_delete"]:3}
    Number of objects processed with errors:  {summary["failed"]:3}
        Create:      {summary["failed_create"]:3}
        Modify:      {summary["failed_modify"]:3}
        Delete:      {summary["failed_delete"]:3}

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


def format_report_object(report):
    """
    Format an IRRD HTTP response for a specific object into a human-friendly text.
    """
    status = "succeeded" if report["successful"] else "FAILED"

    formatted_report = f'{report["type"]} {status}: ""[{report["object_class"]}] {report["rpsl_pk"]}\n'
    if report["info_messages"] or report["error_messages"]:
        if report["error_messages"]:
            formatted_report += "\n" + report["submitted_object_text"] + "\n"
        formatted_report += "".join([f"ERROR: {e}\n" for e in report["error_messages"]])
        formatted_report += "".join([f"INFO: {e}\n" for e in report["info_messages"]])
    return formatted_report


def get_input():
    """
    Read the RPSL input
    """
    rpsl = sys.stdin.read().strip()
    if not rpsl:
        raise XNoObjects("Empty input! Specify at least on RPSL object.")
    return rpsl


def preprocess_args(options):
    """
    Fix up the command-line options before argparse gets in there.
    Some environment variables push values onto the options at this
    point.
    """
    has_u_or_h = "-u" in options or "-h" in options
    if os.getenv("IRR_RPSL_SUBMIT_URL") and not has_u_or_h:
        options.extend(["-u", os.getenv("IRR_RPSL_SUBMIT_URL")])
    elif os.getenv("IRR_RPSL_SUBMIT_HOST") and not has_u_or_h:
        options.extend(["-h", os.getenv("IRR_RPSL_SUBMIT_HOST")])

    if os.getenv("IRR_RPSL_SUBMIT_DEBUG") and not "-d" in options:
        options.extend(["-d"])

    return options


def process_args(options):
    """
    Perform the command-line argument processing.
    """
    try:
        options = preprocess_args(options)
        args = setup_argparse().parse_args(options)
    except (argparse.ArgumentError, SystemExit) as error:
        # Python 3.9 allows us to turn off exit_on_error, but
        # we're not there everywhere. And, the --help feature
        # wants to exit with an error, so stop that. We don't
        # need a message for XHelp because argparse has already
        # output something.
        if "--help" in options:
            raise XHelp("") from error
        raise XArgumentError("Error processing command-line arguments: {error.message}") from error

    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("enabled debug level for logging")

    logger.debug("raw args: %s", options)
    args = adjust_args(args)
    logger.debug("adjusted args: %s", args)
    return args


def send_request(requests_text, args):
    """
    Send the RPSL payload to the IRRdv4 server.
    """
    http_request = create_http_request(requests_text, args)

    try:
        http_response = request.urlopen(http_request, timeout=20)  # pylint: disable=consider-using-with
    except URLError as error:
        reason = error.reason
        if isinstance(reason, socket.gaierror):
            raise XNameResolutionFailed(args.url, reason) from error
        if isinstance(reason, (socket.timeout, ConnectionRefusedError)):
            raise XHTTPConnectionFailed(args.url, http_request) from error  # pragma: no cover
        if reason == "Not Found":
            raise XHTTPNotFound(args.url, http_request) from error
        raise error
    except Exception as error:
        raise error

    response_body = http_response.read().decode("utf-8")
    logger.debug("====START RESPONSE BODY====:\n%s\n====ENE RESPONSE BODY====\n", response_body)
    response = json.loads(response_body)
    return response


def setup_argparse():
    """
    Define the command-line arguments. This sets up the default set
    for IRRdv4 and adds some legacy options for IRRdv3 compatibility.
    """

    def metadata(metadata_values):
        try:
            return {item.split("=")[0]: item.split("=", 1)[1] for item in metadata_values.split(",")}
        except IndexError as error:
            raise ValueError() from error

    description = textwrap.dedent(
        """\
        Read RPSL submissions from stdin and return a response on stdout.
        Errors or debug info are printed to stderr. This program accepts
        the arguments for irrdv3's version of irr_rpsl_submit but ignores
        most of them.

        You can also set three environment variables:

            IRR_RPSL_SUBMIT_DEBUG - turn on debugging
            IRR_RPSL_SUBMIT_URL   - used if both -u and -h are unspecified
            IRR_RPSL_SUBMIT_HOST  - used if both -u and -h are unspecified
                                    and IRR_RPSL_SUBMIT_URL is not set

        The input format must be plain RPSL objects, separated by double
        newlines, as used in emails documented on
        https://irrd.readthedocs.io/en/stable/users/database-changes/#submitting-over-e-mail .

        The exit code is tells you what happened:

             0 - complete success
             1 - at least one change was rejected
             2 - usage error
             4 - input error
             8 - network error
            16 - unexpected response
            32 - an unidentified error

    """
    )

    parser = argparse.ArgumentParser(
        add_help=False,
        description=description,
        # exit_on_error=False,  # Python 3.9 feature
        formatter_class=BlankLinesHelpFormatter,
    )
    parser.add_argument(
        "-d",
        "-v",
        default=False,
        dest="debug",
        action="store_true",
        help="set logging level to DEBUG (also set by IRR_RPSL_SUBMIT_DEBUG)",
    )
    parser.add_argument(
        "--help",
        action="help",
        help="show this help message and exit",
    )
    parser.add_argument(
        "-m",
        dest="metadata",
        type=metadata,
        help="metadata sent in X-irrd-metadata header, in key=value format, separated by comma",
    )

    url_or_host = parser.add_mutually_exclusive_group(required=True)
    url_or_host.add_argument(
        "-h",
        dest="host",
        metavar="HOST",
        type=str,
        help="IRRd host",
    )
    url_or_host.add_argument(
        "-u",
        dest="url",
        type=str,
        help="IRRd submission API URL, e.g. https://rr.example.net/v1/submit/ (also set by IRR_RPSL_SUBMIT_URL)",  # pylint: disable=C0301
    )

    add_irrdv3_options(parser)

    return parser


if __name__ == "__main__":  # pragma: no cover
    run(sys.argv[1:])
