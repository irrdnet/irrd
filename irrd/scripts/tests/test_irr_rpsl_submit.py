import json
import io
import os
import pytest
import re
from urllib import request
import subprocess
import sys
import unittest
from urllib.error import HTTPError

from .. import irr_rpsl_submit

IRRD_HOST = "fake.example.com"
IRRD_URL = f"http://{IRRD_HOST}"

UNRESOVABLE_HOST = "www137xyz.example.com"
UNRESOVABLE_URL = f"http://{UNRESOVABLE_HOST}/v1/submit/"

UNREACHABLE_HOST = "localhost:65123"  # just guessing
UNREACHABLE_URL = f"http://{UNREACHABLE_HOST}/v1/submit/"

# example.com is for examples, but it resolves and there's a website
# that doesn't return JSON. That's handy for testing!
BAD_RESPONSE_HOST = "www.example.com"
BAD_RESPONSE_URL = f"http://{BAD_RESPONSE_HOST}/v1/submit/"

ENV_EMPTY = None
ENV_URL = {"IRR_RPSL_SUBMIT_URL": IRRD_URL}
ENV_HOST = {"IRR_RPSL_SUBMIT_HOST": IRRD_HOST}

REGEX_NO_OBJECTS = re.compile("Empty input! Specify at least on RPSL object")
REGEX_TOO_MANY = re.compile("There was more than one RPSL object")
REGEX_ONE_OF = re.compile("one of the arguments -h -u is required")
REGEX_NO_H_WITH_U = re.compile("argument -h: not allowed with argument -u")
REGEX_UNRESOLVABLE = re.compile("Could not resolve")
REGEX_UNREACHABLE = re.compile("Connection refused|Cannot assign requested address")
REGEX_BAD_RESPONSE = re.compile("decoding JSON")
REGEX_NOT_FOUND = re.compile("Not found")

EXIT_SUCCESS = 0
EXIT_CHANGE_FAILED = 1
EXIT_ARGUMENT_ERROR = 2
EXIT_INPUT_ERROR = 4
EXIT_NETWORK_ERROR = 8
EXIT_RESPONSE_ERROR = 16
EXIT_OTHER_ERROR = 32

"""
irr_rpsl_submit does not RPSL checking. There are a few checks for
known invalid requests, but everything else is left to the server
to respond with an error. As such, these string need only look like
RPSL without conforming to the rules for particular objects.
"""
OVERRIDE = "asdffh"
DELETE_REASON = "some fine pig"
PASSWORD1 = "qwerty"
PASSWORD2 = "mnbvc"
RPSL_EMPTY = ""
RPSL_WHITESPACE = "\n\n\n    \t\t\n"
RPSL_MINIMAL = "route: 1.2.3.4\norigin: AS65414\n"
RPSL_EXTRA_WHITESPACE = "\n\nroute: 1.2.3.4\norigin: AS65414\n\n\n\nroute: 5.6.8.9\norigin: AS65414\n\n\n\n\n\n"
RPSL_DELETE = f"role: Badgers\ndelete: {DELETE_REASON}"
RPSL_DELETE_WITH_TWO_OBJECTS = f"person: Biff Badger\n\nrole: Badgers\ndelete: {DELETE_REASON}"
RPSL_WITH_OVERRIDE = f"mnter: Biff\noverride: {OVERRIDE}"
RPSL_WITH_TWO_DIFF_OVERRIDES = f"{RPSL_MINIMAL}override: {PASSWORD1}\n\n{RPSL_MINIMAL}override: {PASSWORD2}"
RPSL_WITH_ONE_PASSWORD = f"{RPSL_MINIMAL}password: {PASSWORD1}\n"
RPSL_WITH_TWO_PASSWORD = f"{RPSL_MINIMAL}password: {PASSWORD1}\n\n{RPSL_MINIMAL}password: {PASSWORD2}"

REQUEST_BODY_KEYS = ["delete_reason", "objects", "override", "passwords"]


class APIResultObject:
    """
    Create the dicts for objects list in the API response. Line up
    the things that you want and call .boj at the end:

        APIResultObject().create().succeed().obj
        APIResultObject('mntner', 'MNT_BY').modify().succeed().obj

    """

    def __init__(self, cls="roote", rpsl_pk="primary_key"):
        self.obj = {
            "object_class": cls,
            "rpsl_pk": rpsl_pk,
            "info_messages": [],
            "error_messages": [],
            "new_object_text": "[trimmed]",
            "submitted_object_text": "[trimmed]",
        }

    def create(self):
        self.obj["type"] = "create"
        return self

    def delete(self):
        self.obj["type"] = "delete"
        return self

    def modify(self):
        self.obj["type"] = "modify"
        return self

    def fail(self, message="some failure"):
        self.obj["successful"] = False
        self.obj["error_messages"] = [message]
        return self

    def succeed(self, message=None):
        self.obj["successful"] = True
        return self


class APIResult:
    """
    Form the API Response by adding the objects you want:

        result = APIResult([
            APIResultObject().create().succeed(),
            APIResultObject().modify().fail()
        ]).to_dict()

    Everything else is filled in for you based on those objects.

    This data structure should be the same thing that the live API
    response returns (once the JSON is decoded).
    """

    def __init__(self, objects=[]):
        self.result = {"objects": [o.obj for o in objects], "summary": {}, "request_meta": {}}

    def sum_of(self, operation, success):
        total = 0
        for obj in self.result["objects"]:
            if obj["successful"] is success and obj["type"] == operation:
                total += 1
        return total

    def summary(self):
        self.result["summary"]["objects_found"] = len(self.result["objects"])
        operations = ["create", "delete", "modify"]

        for value in ["successful", "failed"]:
            sense = value == "successful"
            for op in operations:
                self.result["summary"][f"{value}_{op}"] = self.sum_of(op, sense)
            self.result["summary"][value] = sum(
                self.result["summary"][key] for key in [f"{value}_{op}" for op in operations]
            )

    def to_dict(self):
        self.summary()
        return self.result

    def to_json(self):
        return json.dumps(self.to_dict()).encode("utf-8")

    def read(self):
        """Stand in for http.client.HTTPResponse.read()"""
        return self.to_json()


class APIBadResponse:
    def read(self):
        return "This is not JSON".encode("utf-8")


class Runner:
    """
    Handle the details of running the external program
    """

    @classmethod
    def program(cls):
        """
        Return the absolute path to the program so we can call it
        no matter what the actual working directory is.
        """
        repo_root = (
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
            )
            .stdout.decode(sys.stdout.encoding)
            .strip()
        )

        program_location = os.path.join(repo_root, "irrd/scripts/irr_rpsl_submit.py")
        return program_location

    @classmethod
    def program_args(cls, args):
        program = [sys.executable, cls.program()]
        program.extend(args)
        return program

    @classmethod
    def run(cls, args, env=None, rpsl=""):
        command = cls.program_args(args)
        raw_result = subprocess.run(
            command,
            capture_output=True,
            encoding="utf-8",
            env=env,
            input=rpsl,
        )

        return raw_result


class MyBase(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def capfd(self, capfd):
        self.capfd = capfd

    @classmethod
    def setUp(cls):
        sys.stdin = sys.__stdin__
        irr_env_names = ["IRR_RPSL_SUBMIT_DEBUG", "IRR_RPSL_SUBMIT_HOST", "IRR_RPSL_SUBMIT_URL"]
        for name in irr_env_names:
            os.unsetenv(name)

    @classmethod
    def tearDown(cls):
        pass


class Test100GetArguments(MyBase):
    def test_help_message(self):
        options = ["--help"]
        with pytest.raises(irr_rpsl_submit.XHelp) as error:
            irr_rpsl_submit.get_arguments(options)
        out, err = self.capfd.readouterr()
        self.assertEqual(error.type, irr_rpsl_submit.XHelp)
        self.assertRegex(out, re.compile("irrdv3"))

    def test_bad_option(self):
        options = ["-Z"]
        with pytest.raises(irr_rpsl_submit.XArgumentError) as pytest_wrapped_e:
            irr_rpsl_submit.get_arguments(options)
        self.assertEqual(pytest_wrapped_e.type, irr_rpsl_submit.XArgumentError)

    def test_metadata(self):
        options = ["-u", "http://example.com", "-m", "foo=bar"]
        args = irr_rpsl_submit.get_arguments(options)
        self.assertEqual(args.metadata, {"foo": "bar"})

    def test_metadata_without_value(self):
        options = ["-u", "http://example.com", "-m", "foo"]
        with pytest.raises(irr_rpsl_submit.XArgumentError) as pytest_wrapped_e:
            irr_rpsl_submit.get_arguments(options)
        self.assertEqual(pytest_wrapped_e.type, irr_rpsl_submit.XArgumentError)

    def test_debug(self):
        options = ["-u", "http://example.com", "-d"]
        args = irr_rpsl_submit.get_arguments(options)
        self.assertEqual(args.debug, True)

    def test_u_from_env(self):
        name = "IRR_RPSL_SUBMIT_URL"
        value = UNRESOVABLE_URL
        os.environ[name] = value
        args = irr_rpsl_submit.get_arguments([])
        self.assertEqual(args.url, UNRESOVABLE_URL)

    def test_h_from_env(self):
        name = "IRR_RPSL_SUBMIT_HOST"
        value = UNRESOVABLE_HOST
        os.environ[name] = value
        args = irr_rpsl_submit.get_arguments([])
        self.assertEqual(args.url, UNRESOVABLE_URL)

    def test_d_from_env(self):
        name = "IRR_RPSL_SUBMIT_DEBUG"
        value = "1"
        os.environ[name] = value
        args = irr_rpsl_submit.get_arguments(["-u", UNRESOVABLE_URL])
        self.assertEqual(args.debug, True)

    def test_choose_url(self):
        table = [
            {"expected": "http://localhost/v1/submit/", "args": ["-h", "localhost"]},
            {"expected": "http://localhost:8080/v1/submit/", "args": ["-h", "localhost", "-p", "8080"]},
            {"expected": "http://example.com:137/v1/submit/", "args": ["-h", "example.com", "-p", "137"]},
            {"expected": "http://example.com:137/v1/submit/", "args": ["-u", "http://example.com:137/v1/submit/"]},
            {"expected": "http://example.com/v1/submit/", "args": ["-u", "http://example.com/v1/submit/"]},
        ]

        for d in table:
            args = irr_rpsl_submit.get_arguments(d["args"].copy())
            # choose_url modifies args
            irr_rpsl_submit.choose_url(args)
            self.assertEqual(args.url, d["expected"], "choose_url sets args.url to the expected URL")


class Test110ChooseURL(MyBase):
    def test_choose_url_exception(self):
        options = []
        with pytest.raises(irr_rpsl_submit.XArgumentProcessing):
            options = ["-h", "localhost"]
            args = irr_rpsl_submit.get_arguments(options)
            args.host = None  # unset it to trigger next error
            args.url = None  # unset it to trigger next error
            irr_rpsl_submit.choose_url(args)


class Test200CreateRequestBody(MyBase):
    def test_create_request_body_minimal(self):
        request_body = irr_rpsl_submit.create_request_body(RPSL_MINIMAL)
        for key in REQUEST_BODY_KEYS:
            self.assertTrue(key in request_body)
        self.assertEqual(request_body["override"], None)
        self.assertEqual(request_body["passwords"], [])
        self.assertEqual(request_body["delete_reason"], "")

    def test_create_request_body_delete(self):
        request_body = irr_rpsl_submit.create_request_body(RPSL_DELETE)
        for key in REQUEST_BODY_KEYS:
            self.assertTrue(key in request_body)
        self.assertEqual(request_body["override"], None)
        self.assertEqual(request_body["passwords"], [])
        self.assertEqual(request_body["delete_reason"], DELETE_REASON)
        self.assertEqual(len(request_body["objects"]), 1)

    def test_create_request_body_override(self):
        request_body = irr_rpsl_submit.create_request_body(RPSL_WITH_OVERRIDE)
        for key in REQUEST_BODY_KEYS:
            self.assertTrue(key in request_body)
        self.assertEqual(request_body["override"], OVERRIDE)
        self.assertEqual(request_body["passwords"], [])
        self.assertEqual(request_body["delete_reason"], "")
        self.assertEqual(len(request_body["objects"]), 1)

    def test_create_request_body_password(self):
        request_body = irr_rpsl_submit.create_request_body(RPSL_WITH_ONE_PASSWORD)
        for key in REQUEST_BODY_KEYS:
            self.assertTrue(key in request_body)
        self.assertEqual(request_body["override"], None)
        self.assertEqual(request_body["passwords"], [PASSWORD1])
        self.assertEqual(request_body["delete_reason"], "")
        self.assertEqual(len(request_body["objects"]), 1)

    def test_create_request_body_two_passwords(self):
        request_body = irr_rpsl_submit.create_request_body(RPSL_WITH_TWO_PASSWORD)
        for key in REQUEST_BODY_KEYS:
            self.assertTrue(key in request_body)
        self.assertEqual(request_body["override"], None)
        self.assertEqual(request_body["passwords"], [PASSWORD1, PASSWORD2])
        self.assertEqual(request_body["delete_reason"], "")
        self.assertEqual(len(request_body["objects"]), 2)

    def test_create_request_body_two_objects_delete(self):
        request_body = irr_rpsl_submit.create_request_body(RPSL_DELETE_WITH_TWO_OBJECTS)
        for key in REQUEST_BODY_KEYS:
            self.assertTrue(key in request_body)
        self.assertEqual(request_body["override"], None)
        self.assertEqual(request_body["passwords"], [])
        self.assertEqual(request_body["delete_reason"], DELETE_REASON)
        self.assertEqual(len(request_body["objects"]), 2)

    def test_create_request_body_two_overrides(self):
        passed = False
        try:
            irr_rpsl_submit.create_request_body(RPSL_WITH_TWO_DIFF_OVERRIDES)
        except irr_rpsl_submit.XInput:
            passed = True

        self.assertTrue(passed)

    def test_create_request_extra_whitespace(self):
        """
        This test checks that we parse correctly when there are lots
        of extra newlines before, between, or after objects.
        """
        request_body = irr_rpsl_submit.create_request_body(RPSL_EXTRA_WHITESPACE)
        for key in REQUEST_BODY_KEYS:
            self.assertTrue(key in request_body)
        self.assertEqual(request_body["override"], None)
        self.assertEqual(request_body["passwords"], [])
        self.assertEqual(len(request_body["objects"]), 2)


class Test200CreateRequesty(MyBase):
    def test_create_http_request_metadata(self):
        args = irr_rpsl_submit.get_arguments(["-h", UNRESOVABLE_HOST, "-m", "Biff=Badger"])
        request = irr_rpsl_submit.create_http_request(RPSL_MINIMAL, args)
        self.assertEqual(request.headers["X-irrd-metadata"], '{"Biff": "Badger"}')

    def test_create_http_request_no_objects(self):
        args = irr_rpsl_submit.get_arguments(["-h", UNRESOVABLE_HOST, "-m", "Biff=Badger"])
        with pytest.raises(irr_rpsl_submit.XNoObjects) as pytest_wrapped_e:
            irr_rpsl_submit.create_http_request(RPSL_EMPTY, args)
        self.assertEqual(pytest_wrapped_e.type, irr_rpsl_submit.XNoObjects)


def my_raise(ex):
    # because lambdas are limited
    # https://stackoverflow.com/questions/8294618/define-a-lambda-expression-that-raises-an-exception
    raise ex


class Test300MakeRequest(MyBase):
    original = irr_rpsl_submit.__dict__["send_request"]

    @classmethod
    def tearDown(cls):
        super().tearDown()
        irr_rpsl_submit.send_request = cls.original

    def test_unresolvable_host_raises(self):
        args = irr_rpsl_submit.get_arguments(["-h", UNRESOVABLE_HOST])
        self.assertEqual(args.url, UNRESOVABLE_URL)

        self.assertRaises(irr_rpsl_submit.XNetwork, irr_rpsl_submit.make_request, RPSL_MINIMAL, args)

    def test_unreachable_host_raises(self):
        options = ["-u", UNREACHABLE_URL]
        args = irr_rpsl_submit.get_arguments(options)
        self.assertEqual(args.url, UNREACHABLE_URL)

        self.assertRaises(irr_rpsl_submit.XNetwork, irr_rpsl_submit.make_request, RPSL_MINIMAL, args)

        with pytest.raises(SystemExit) as error:
            irr_rpsl_submit.run(options)
        self.assertEqual(error.type, SystemExit)

    def test_http_error(self):
        options = ["-u", UNREACHABLE_URL]
        args = irr_rpsl_submit.get_arguments(options)
        self.assertEqual(args.url, UNREACHABLE_URL)

        irr_rpsl_submit.send_request = lambda rpsl, args: my_raise(
            HTTPError("http://fake.example.com", 500, "Internal Server Error", dict(), None)  # type: ignore
        )
        with pytest.raises(irr_rpsl_submit.XNetwork):
            irr_rpsl_submit.make_request(RPSL_MINIMAL, args)
        self.assertTrue(True)

    def test_bad_response(self):
        options = ["-u", UNREACHABLE_URL]
        args = irr_rpsl_submit.get_arguments(options)
        self.assertEqual(args.url, UNREACHABLE_URL)

        irr_rpsl_submit.send_request = lambda rpsl, args: json.loads("{")

        with pytest.raises(irr_rpsl_submit.XResponse):
            irr_rpsl_submit.make_request(RPSL_MINIMAL, args)

    def test_good_response(self):
        options = ["-u", UNREACHABLE_URL]
        args = irr_rpsl_submit.get_arguments(options)
        self.assertEqual(args.url, UNREACHABLE_URL)

        irr_rpsl_submit.send_request = lambda rpsl, args: APIResult([APIResultObject().create().succeed()]).to_dict()

        result = irr_rpsl_submit.make_request(RPSL_MINIMAL, args)
        self.assertTrue(result["objects"][0]["successful"])


class Test310HandleResult(MyBase):
    def test_result_rejected(self):
        options = ["-u", UNREACHABLE_URL, "-j"]
        args = irr_rpsl_submit.get_arguments(options)

        result = APIResult([APIResultObject().create().succeed()]).to_dict()
        self.assertFalse(irr_rpsl_submit.at_least_one_change_was_rejected(result))
        output = irr_rpsl_submit.handle_output(args, result)
        self.assertRegex(output, re.compile("^{"))

    def test_json(self):
        options = ["-u", UNREACHABLE_URL, "-j"]
        args = irr_rpsl_submit.get_arguments(options)
        self.assertTrue(args.output_json, "JSON output is set")
        self.assertFalse(args.output_text, "Text output is not set")

        result = APIResult([APIResultObject().create().succeed()]).to_dict()
        self.assertFalse(irr_rpsl_submit.at_least_one_change_was_rejected(result))
        output = irr_rpsl_submit.handle_output(args, result)
        self.assertRegex(output, re.compile("^{"))

    def test_text(self):
        options = ["-u", UNREACHABLE_URL, "-t"]
        args = irr_rpsl_submit.get_arguments(options)
        self.assertFalse(args.output_json, "JSON output is not set")
        self.assertTrue(args.output_text, "Text output is set")

        result = APIResult([APIResultObject().create().succeed()]).to_dict()
        self.assertFalse(irr_rpsl_submit.at_least_one_change_was_rejected(result))
        output = irr_rpsl_submit.handle_output(args, result)
        self.assertRegex(output, re.compile("SUMMARY OF UPDATE"))
        self.assertRegex(output, re.compile("successfully:\\s+1"))
        self.assertRegex(output, re.compile("with errors:\\s+0"))

        result = APIResult([APIResultObject().delete().fail()]).to_dict()
        self.assertTrue(irr_rpsl_submit.at_least_one_change_was_rejected(result))
        output = irr_rpsl_submit.handle_output(args, result)
        self.assertRegex(output, re.compile("SUMMARY OF UPDATE"))
        self.assertRegex(output, re.compile("successfully:\\s+0"))
        self.assertRegex(output, re.compile("with errors:\\s+1"))

    def test_default(self):
        options = ["-u", UNREACHABLE_URL]
        args = irr_rpsl_submit.get_arguments(options)
        self.assertFalse(args.output_json, "JSON output is set by default")
        self.assertFalse(args.output_text, "Text output is not set")
        result = APIResult([APIResultObject().create().succeed()]).to_dict()
        self.assertFalse(irr_rpsl_submit.at_least_one_change_was_rejected(result))
        output = irr_rpsl_submit.handle_output(args, result)
        self.assertRegex(output, re.compile("SUMMARY OF UPDATE"))


class Test400RunNoNetwork(MyBase):
    def test_help_message(self):
        options = ["--help"]
        with pytest.raises(SystemExit) as error:
            irr_rpsl_submit.run(options)
        out, err = self.capfd.readouterr()
        self.assertEqual(error.type, SystemExit)
        self.assertRegex(out, re.compile("irrdv3"))

    def test_u_and_h(self):
        options = ["-u", "http://example.com", "-h", "fake.example.com"]
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            irr_rpsl_submit.run(options)
        self.assertEqual(pytest_wrapped_e.type, SystemExit)
        self.assertEqual(pytest_wrapped_e.value.code, EXIT_ARGUMENT_ERROR)

    def test_no_objects(self):
        options = ["-u", "http://abc.xyz.example.com"]
        sys.stdin = io.StringIO("")
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            irr_rpsl_submit.run(options)
        self.assertEqual(pytest_wrapped_e.type, SystemExit)
        self.assertEqual(pytest_wrapped_e.value.code, EXIT_INPUT_ERROR)

    def test_delete_with_extra_objects(self):
        options = ["-u", "http://abc.xyz.example.com"]
        sys.stdin = io.StringIO(RPSL_DELETE_WITH_TWO_OBJECTS)
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            irr_rpsl_submit.run(options)
        self.assertEqual(pytest_wrapped_e.type, SystemExit)
        self.assertEqual(pytest_wrapped_e.value.code, EXIT_INPUT_ERROR)


class Test405RunMockResponse(MyBase):
    original = irr_rpsl_submit.__dict__["make_request"]

    @classmethod
    def tearDown(cls):
        super().tearDown()
        irr_rpsl_submit.make_request = cls.original

    def test_good_response(self):
        response = APIResult(
            [
                APIResultObject().create().succeed(),
                APIResultObject().modify().succeed(),
            ]
        ).to_dict()
        irr_rpsl_submit.make_request = lambda rpsl, args: response

        options = ["-u", "http://abc.xyz.example.com"]
        sys.stdin = io.StringIO(RPSL_MINIMAL)
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            irr_rpsl_submit.run(options)
        out, err = self.capfd.readouterr()
        self.assertEqual(pytest_wrapped_e.type, SystemExit)
        self.assertEqual(pytest_wrapped_e.value.code, EXIT_SUCCESS)

    def test_change_failed(self):
        response = APIResult(
            [
                APIResultObject().create().succeed(),
                APIResultObject().modify().fail(),
            ]
        ).to_dict()
        irr_rpsl_submit.make_request = lambda rpsl, args: response

        options = ["-u", "http://abc.xyz.example.com"]
        sys.stdin = io.StringIO(RPSL_MINIMAL)
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            irr_rpsl_submit.run(options)
        out, err = self.capfd.readouterr()
        self.assertEqual(pytest_wrapped_e.type, SystemExit)
        self.assertEqual(pytest_wrapped_e.value.code, EXIT_CHANGE_FAILED)


class Test405RunMockUrlopen(MyBase):
    original_urlopen = request.__dict__["urlopen"]

    @classmethod
    def tearDown(cls):
        super().tearDown()
        request.urlopen = cls.original_urlopen

    def test_all_objects_succeed(self):
        options = ["-u", "http://abc.xyz.example.com"]
        sys.stdin = io.StringIO(RPSL_MINIMAL)
        response = APIResult(
            [
                APIResultObject().create().succeed(),
                APIResultObject().modify().succeed(),
            ]
        )

        request.urlopen = lambda url, **kwargs: response

        with pytest.raises(SystemExit) as pytest_wrapped_e:
            irr_rpsl_submit.run(options)
        out, err = self.capfd.readouterr()
        self.assertEqual(pytest_wrapped_e.type, SystemExit)
        self.assertEqual(pytest_wrapped_e.value.code, EXIT_SUCCESS)

    def test_some_objects_fail(self):
        options = ["-u", "http://abc.xyz.example.com"]
        sys.stdin = io.StringIO(RPSL_MINIMAL)
        response = APIResult(
            [
                APIResultObject().create().succeed(),
                APIResultObject().modify().fail(),
            ]
        )

        request.urlopen = lambda url, **kwargs: response

        with pytest.raises(SystemExit) as pytest_wrapped_e:
            irr_rpsl_submit.run(options)
        out, err = self.capfd.readouterr()
        self.assertEqual(pytest_wrapped_e.type, SystemExit)
        self.assertEqual(pytest_wrapped_e.value.code, EXIT_CHANGE_FAILED)

    def test_bad_response(self):
        options = ["-u", "http://abc.xyz.example.com"]
        response = APIBadResponse()
        request.urlopen = lambda url, **kwargs: response
        sys.stdin = io.StringIO(RPSL_MINIMAL)
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            irr_rpsl_submit.run(options)
        out, err = self.capfd.readouterr()
        self.assertEqual(pytest_wrapped_e.type, SystemExit)
        self.assertEqual(pytest_wrapped_e.value.code, EXIT_RESPONSE_ERROR)

    def test_general_exception(self):
        options = ["-u", "http://abc.xyz.example.com"]
        sys.stdin = io.StringIO(RPSL_MINIMAL)

        request.urlopen = lambda url, **kwargs: my_raise(Exception("Random exception"))

        with pytest.raises(SystemExit) as pytest_wrapped_e:
            irr_rpsl_submit.run(options)
        out, err = self.capfd.readouterr()
        self.assertEqual(pytest_wrapped_e.type, SystemExit)
        self.assertEqual(pytest_wrapped_e.value.code, EXIT_OTHER_ERROR)


class Test410RunLiveNetwork(MyBase):
    def test_no_network(self):
        options = ["-u", "http://abc.xyz.example.com"]
        sys.stdin = io.StringIO("route: 1.2.3.4\n\n")
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            irr_rpsl_submit.run(options)
        self.assertEqual(pytest_wrapped_e.type, SystemExit)
        self.assertEqual(pytest_wrapped_e.value.code, EXIT_NETWORK_ERROR)

    def test_not_found(self):
        options = ["-u", BAD_RESPONSE_URL]
        sys.stdin = io.StringIO("route: 1.2.3.4\n\n")
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            irr_rpsl_submit.run(options)
        self.assertEqual(pytest_wrapped_e.type, SystemExit)
        self.assertEqual(pytest_wrapped_e.value.code, EXIT_NETWORK_ERROR)


class Test900Command(MyBase):
    """
    These tests run irr_rpsl_submit.py as a program. As such, none
    of these tests contribute to coverage since the work is done in
    a separate process.
    """

    def test_010_nonense_options(self):
        for s in ["-Z", "-X", "-9", "--not-there"]:
            result = Runner.run([s], ENV_EMPTY, RPSL_EMPTY)
            self.assertEqual(
                result.returncode, EXIT_ARGUMENT_ERROR, f"nonsense switch {s} exits with {EXIT_ARGUMENT_ERROR}"
            )
            self.assertRegex(result.stderr, REGEX_ONE_OF)

    def test_010_no_args(self):
        result = Runner.run([], ENV_EMPTY, RPSL_EMPTY)
        self.assertEqual(result.returncode, EXIT_ARGUMENT_ERROR, f"no arguments exits with {EXIT_ARGUMENT_ERROR}")
        self.assertRegex(result.stderr, REGEX_ONE_OF)

    def test_020_help(self):
        result = Runner.run(["--help"], ENV_EMPTY, RPSL_EMPTY)
        self.assertEqual(result.returncode, EXIT_SUCCESS, "--help exits successfully")
        self.assertRegex(result.stdout, re.compile("irrdv3"), "--help exits successfully")

    def test_020_u_and_h(self):
        result = Runner.run(["-u", IRRD_URL, "-h", "host"], ENV_EMPTY, RPSL_EMPTY)
        self.assertEqual(
            result.returncode, EXIT_ARGUMENT_ERROR, f"using both -u and -h exits with {EXIT_ARGUMENT_ERROR}"
        )
        self.assertRegex(result.stderr, REGEX_NO_H_WITH_U)

    def test_020_p_and_h_with_port(self):
        host = "fakehost"
        dash_p_port = "137"

        result = Runner.run(["-h", f"{host}:1234", "-p", dash_p_port], ENV_EMPTY, RPSL_MINIMAL)
        # Since the literal fakehost won't resolve, we will get a
        # network error exit, but that's not what we care about. We
        # merely want to error message to see what the url value
        # turned out to be:
        self.assertEqual(result.returncode, EXIT_NETWORK_ERROR, "-h with bad host is a network error")
        self.assertRegex(result.stderr, re.compile(f"{host}:{dash_p_port}"), "-h with port and -p prefers -p")

    def test_020_dash_o_noop(self):
        # -O in irrdv3 was used to note the original host making the request
        # If we get an error, it should be from the -h, not the -O
        result = Runner.run(["-h", UNREACHABLE_HOST, "-O", BAD_RESPONSE_HOST], ENV_EMPTY, RPSL_MINIMAL)
        self.assertEqual(
            result.returncode, EXIT_NETWORK_ERROR, "using both -h and -O exits with value appropriate to -h value"
        )
        self.assertRegex(result.stderr, REGEX_UNREACHABLE)

        result = Runner.run(["-h", BAD_RESPONSE_HOST, "-O", UNREACHABLE_HOST], ENV_EMPTY, RPSL_MINIMAL)
        self.assertEqual(
            result.returncode, EXIT_NETWORK_ERROR, "using both -h and -O exits with value appropriate to -h value"
        )
        self.assertRegex(result.stderr, REGEX_NOT_FOUND)

    def test_030_empty_input_option(self):
        result = Runner.run(["-u", IRRD_URL], ENV_EMPTY, RPSL_EMPTY)
        self.assertEqual(result.returncode, EXIT_INPUT_ERROR, f"empty input with -u exits with {EXIT_INPUT_ERROR}")
        self.assertRegex(result.stderr, REGEX_NO_OBJECTS)

    def test_030_empty_input_env(self):
        result = Runner.run([], ENV_URL, RPSL_EMPTY)
        self.assertEqual(
            result.returncode, EXIT_INPUT_ERROR, f"empty input with {ENV_URL} exits with {EXIT_INPUT_ERROR}"
        )
        result = Runner.run([], ENV_HOST, RPSL_EMPTY)
        self.assertEqual(
            result.returncode, EXIT_INPUT_ERROR, f"empty input with {ENV_HOST} exits with {EXIT_INPUT_ERROR}"
        )
        self.assertRegex(result.stderr, REGEX_NO_OBJECTS)

    def test_030_only_whitespace_input(self):
        result = Runner.run(["-u", IRRD_URL], ENV_EMPTY, RPSL_WHITESPACE)
        self.assertEqual(result.returncode, EXIT_INPUT_ERROR, f"whitespace only input exits with {EXIT_INPUT_ERROR}")
        self.assertRegex(result.stderr, REGEX_NO_OBJECTS)

    def test_030_multiple_object_delete(self):
        result = Runner.run(["-u", IRRD_URL], ENV_EMPTY, RPSL_DELETE_WITH_TWO_OBJECTS)
        self.assertEqual(
            result.returncode, EXIT_INPUT_ERROR, f"RPSL delete with multiple objects exits with {EXIT_INPUT_ERROR}"
        )
        self.assertRegex(result.stderr, REGEX_TOO_MANY)

    def test_040_unresovlable_host(self):
        table = [
            ["-u", UNRESOVABLE_URL],
            ["-h", UNRESOVABLE_HOST],
        ]

        for row in table:
            result = Runner.run(row, ENV_EMPTY, RPSL_MINIMAL)
            self.assertEqual(
                result.returncode, EXIT_NETWORK_ERROR, f"Unresolvable host in {row[1]} exits with {EXIT_NETWORK_ERROR}"
            )
            self.assertRegex(result.stderr, REGEX_UNRESOLVABLE)

    def test_040_unreachable_host(self):
        table = [
            ["-u", UNREACHABLE_URL],
            ["-h", UNREACHABLE_HOST],
        ]

        for row in table:
            result = Runner.run(row, ENV_EMPTY, RPSL_MINIMAL)
            self.assertEqual(
                result.returncode, EXIT_NETWORK_ERROR, f"Unreachable host in {row[1]} with {EXIT_NETWORK_ERROR}"
            )
            self.assertRegex(result.stderr, REGEX_UNREACHABLE)

    def test_050_non_json_response(self):
        table = [
            ["-u", "http://www.example.com"],
        ]
        for row in table:
            result = Runner.run(row, ENV_EMPTY, RPSL_MINIMAL)
            self.assertEqual(
                result.returncode, EXIT_RESPONSE_ERROR, f"Bad response URL {row[1]} exits with {EXIT_NETWORK_ERROR}"
            )
            self.assertRegex(result.stderr, REGEX_BAD_RESPONSE)


class Test990Command(unittest.TestCase):
    """
    These tests run irr_rpsl_submit.py as a program. As such, none
    of these tests contribute to coverage since the work is done in
    a separate process.
    """

    pass
