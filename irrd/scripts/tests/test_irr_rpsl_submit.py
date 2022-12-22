import os
import pytest
import re
import subprocess
import sys
import unittest

from .. import irr_rpsl_submit

IRRD_HOST="fake.example.com"
IRRD_URL=f"http://{IRRD_HOST}"

UNRESOVABLE_HOST="www137xyz.example.com"
UNRESOVABLE_URL=f"http://{UNRESOVABLE_HOST}"

UNREACHABLE_HOST="localhost:65123" # just guessing
UNREACHABLE_URL=f"http://{UNREACHABLE_HOST}"

# example.com is for examples, but it resolves and there's a website
# that doesn't return JSON. That's handy for testing!
BAD_RESPONSE_HOST="www.example.com"
BAD_RESPONSE_URL=f"http://{BAD_RESPONSE_HOST}"

ENV_EMPTY = None
ENV_URL   = {"IRR_RPSL_SUBMIT_URL": IRRD_URL}
ENV_HOST  = {"IRR_RPSL_SUBMIT_HOST": IRRD_HOST}

REGEX_NO_OBJECTS    = re.compile("There were no RPSL objects in the input")
REGEX_TOO_MANY      = re.compile("There was more than one RPSL object")
REGEX_ONE_OF        = re.compile("one of the arguments -h -u is required")
REGEX_NO_H_WITH_U   = re.compile("argument -h: not allowed with argument -u")
REGEX_UNRESOLVABLE  = re.compile("Could not resolve")
REGEX_UNREACHABLE   = re.compile("Connection refused")
REGEX_BAD_RESPONSE  = re.compile("decoding JSON")
REGEX_NOT_FOUND     = re.compile("Not found")

EXIT_SUCCESS        =  0
EXIT_ARGUMENT_ERROR =  2
EXIT_INPUT_ERROR    =  4
EXIT_NETWORK_ERROR  =  8
EXIT_OTHER_ERROR    = 16

"""
irr_rpsl_submit does not RPSL checking. There are a few checks for
known invalid requests, but everything else is left to the server
to respond with an error. As such, these string need only look like
RPSL without conforming to the rules for particular objects.
"""
RPSL_EMPTY      = ""
RPSL_WHITESPACE = "\n\n\n    \t\t\n"
RPSL_MINIMAL    = "route: 1.2.3.4\norigin: AS65414\n"
RPSL_DELETE_WITH_TWO_OBJECTS = "person: Biff Badger\n\nrole: Badgers\ndelete: some reason"


class Runner():
    """
    Handle the details of running the external program
    """
    @classmethod
    def program(cls):
        return 'irrd/scripts/irr_rpsl_submit.py'

    @classmethod
    def program_args(cls, args):
        program = [ sys.executable, cls.program() ]
        program.extend(args)
        return program

    @classmethod
    def run(cls, args, env=None, rpsl=""):
        command = cls.program_args(args)
        print( "command:" )
        print( command )
        raw_result = subprocess.run(
            command,
            capture_output=True,
            encoding='utf-8',
            env=env,
            input=rpsl,
        )

        return raw_result

class ArgsParseMock(object):
    """
    Turns a dictionary into a class
    """

    def __init__(self, dictionary):
        for key in dictionary:
            setattr(self, key, dictionary[key])

class Test_100_Units(unittest.TestCase):
    def setUp(self):
        irr_env_names = [ 'IRR_RPSL_SUBMIT_DEBUG', 'IRR_RPSL_SUBMIT_HOST', 'IRR_RPSL_SUBMIT_URL' ]
        for name in irr_env_names:
            os.unsetenv(name)

    def tearDown(self):
        pass

    def test_choose_url(self):
        table = [
            { "expected": "http://localhost/v1/submit/",        "args": { "host": "localhost",   "port": None, "url": None } },
            { "expected": "http://localhost:8080/v1/submit/",   "args": { "host": "localhost",   "port": 8080, "url": None } },
            { "expected": "http://example.com:137/v1/submit/",  "args": { "host": "example.com", "port": 137,  "url": None } },

            { "expected": "http://example.com:137/v1/submit/",  "args": { "host": None, "port": None, "url": "http://example.com:137/v1/submit/" } },
            { "expected": "http://example.com/v1/submit/",      "args": { "host": None, "port": None, "url": "http://example.com/v1/submit/" } }
        ];


        for d in table:
            args = ArgsParseMock(d["args"].copy())
            # choose_url modifies args
            irr_rpsl_submit.choose_url(args)
            self.assertEqual( args.url, d["expected"], f"choose_url sets args.url to the expected URL" )

    def test_choose_url_exception(self):
        args_dict = { "host": None, "port": None, "url": None }
        args = ArgsParseMock(args_dict.copy())
        with pytest.raises(irr_rpsl_submit.XArgumentProcessing) as e:
            irr_rpsl_submit.choose_url(args)

class Test_900_Command(unittest.TestCase):
    def setUp(self):
        irr_env_names = [ 'IRR_RPSL_SUBMIT_DEBUG', 'IRR_RPSL_SUBMIT_HOST', 'IRR_RPSL_SUBMIT_URL' ]
        for name in irr_env_names:
            os.unsetenv(name)

    def tearDown(self):
        pass

    def test_010_nonense_options(self):
        for s in ['-Z', '-X', '-9', '--not-there' ]:
            result = Runner.run( [s], ENV_EMPTY, RPSL_EMPTY )
            self.assertEqual( result.returncode, EXIT_ARGUMENT_ERROR, f"nonsense switch {s} exits with {EXIT_ARGUMENT_ERROR}" )
            self.assertRegex( result.stderr, REGEX_ONE_OF )

    def test_010_no_args(self):
        result = Runner.run( [], ENV_EMPTY, RPSL_EMPTY )
        self.assertEqual( result.returncode, EXIT_ARGUMENT_ERROR, f"no arguments exits with {EXIT_ARGUMENT_ERROR}" )
        self.assertRegex( result.stderr, REGEX_ONE_OF )

    def test_020_help(self):
        result = Runner.run( ['--help'], ENV_EMPTY, RPSL_EMPTY )
        self.assertEqual( result.returncode, EXIT_SUCCESS, '--help exits successfully' )

    def test_020_u_and_h(self):
        result = Runner.run( ['-u', IRRD_URL, '-h', 'host'], ENV_EMPTY, RPSL_EMPTY )
        self.assertEqual( result.returncode, EXIT_ARGUMENT_ERROR, f"using both -u and -h exits with {EXIT_ARGUMENT_ERROR}" )
        self.assertRegex( result.stderr, REGEX_NO_H_WITH_U )

    def test_020_p_and_h_with_port(self):
        host = "fakehost"
        dash_p_port = "137"

        result = Runner.run( ['-h', f"{host}:1234", '-p', dash_p_port], ENV_EMPTY, RPSL_MINIMAL )
        # Since the literal fakehost won't resolve, we will get a
        # network error exit, but that's not what we care about. We
        # merely want to error message to see what the url value
        # turned out to be:
        self.assertEqual( result.returncode, EXIT_NETWORK_ERROR, f"-h with bad host is a network error" )
        self.assertRegex( result.stderr, re.compile( f"{host}:{dash_p_port}" ), f"-h with port and -p prefers -p" )

    def test_020_dash_o_noop(self):
        # If we get an error, it should be from the -h, not the -O
        result = Runner.run( ['-h', UNREACHABLE_HOST, '-O', BAD_RESPONSE_HOST], ENV_EMPTY, RPSL_MINIMAL )
        self.assertEqual( result.returncode, EXIT_NETWORK_ERROR, f"using both -h and -O exits with value appropriate to -h value" )
        self.assertRegex( result.stderr, REGEX_UNREACHABLE )

        result = Runner.run( ['-h', BAD_RESPONSE_HOST, '-O', UNREACHABLE_HOST], ENV_EMPTY, RPSL_MINIMAL )
        self.assertEqual( result.returncode, EXIT_NETWORK_ERROR, f"using both -h and -O exits with value appropriate to -h value" )
        self.assertRegex( result.stderr, REGEX_NOT_FOUND )

    def test_030_empty_input_option(self):
        result = Runner.run( ['-u', IRRD_URL], ENV_EMPTY, RPSL_EMPTY )
        self.assertEqual( result.returncode, EXIT_INPUT_ERROR, f"empty input with -u exits with {EXIT_INPUT_ERROR}" )
        self.assertRegex( result.stderr, REGEX_NO_OBJECTS )

    def test_030_empty_input_env(self):
        result = Runner.run( [], ENV_URL, RPSL_EMPTY )
        self.assertEqual( result.returncode, EXIT_INPUT_ERROR, f"empty input with {ENV_URL} exits with {EXIT_INPUT_ERROR}" )
        result = Runner.run( [], ENV_HOST, RPSL_EMPTY )
        self.assertEqual( result.returncode, EXIT_INPUT_ERROR, f"empty input with {ENV_HOST} exits with {EXIT_INPUT_ERROR}" )
        self.assertRegex( result.stderr, REGEX_NO_OBJECTS )

    def test_030_only_whitespace_input(self):
        result = Runner.run( ['-u', IRRD_URL], ENV_EMPTY, RPSL_WHITESPACE )
        self.assertEqual( result.returncode, EXIT_INPUT_ERROR, f"whitespace only input exits with {EXIT_INPUT_ERROR}" )
        self.assertRegex( result.stderr, REGEX_NO_OBJECTS )

    def test_030_multiple_object_delete(self):
        result = Runner.run( ['-u', IRRD_URL], ENV_EMPTY, RPSL_DELETE_WITH_TWO_OBJECTS )
        self.assertEqual( result.returncode, EXIT_INPUT_ERROR, f"RPSL delete with multiple objects exits with {EXIT_INPUT_ERROR}" )
        self.assertRegex( result.stderr, REGEX_TOO_MANY )

    def test_040_unresovlable_host(self):
        table = [
            [ '-u', UNRESOVABLE_URL  ],
            [ '-h', UNRESOVABLE_HOST ],
        ];

        for row in table:
            result = Runner.run( row, ENV_EMPTY, RPSL_MINIMAL )
            self.assertEqual( result.returncode, EXIT_NETWORK_ERROR, f"Unresolvable host in {row[1]} exits with {EXIT_NETWORK_ERROR}" )
            self.assertRegex( result.stderr, REGEX_UNRESOLVABLE )

    def test_040_unreachable_host(self):
        table = [
            [ '-u', UNREACHABLE_URL  ],
            [ '-h', UNREACHABLE_HOST ],
        ];

        for row in table:
            result = Runner.run( row, ENV_EMPTY, RPSL_MINIMAL )
            self.assertEqual( result.returncode, EXIT_NETWORK_ERROR, f"Unreachable host in {row[1]} with {EXIT_NETWORK_ERROR}" )
            self.assertRegex( result.stderr, REGEX_UNREACHABLE )

    def test_050_non_json_response(self):
        table = [
            [ '-u', BAD_RESPONSE_URL  ],
            # [ '-h', BAD_RESPONSE_HOST ], # turns into the right path, which ends up as not found
        ];
        for row in table:
            result = Runner.run( row, ENV_EMPTY, RPSL_MINIMAL )
            self.assertEqual( result.returncode, EXIT_NETWORK_ERROR, f"Bad response URL {row[1]} exits with {EXIT_NETWORK_ERROR}" )
            self.assertRegex( result.stderr, REGEX_BAD_RESPONSE )

