import io
import json
import textwrap
from unittest.mock import Mock
from urllib.error import HTTPError

from ..irr_rpsl_submit import run

URL = "https://rr.example.net/v1/submit/"


def test_call_success(capsys, monkeypatch):
    mock_urlopen = Mock()
    monkeypatch.setattr("irrd.scripts.irr_rpsl_submit.request.urlopen", mock_urlopen)
    success_return = {
        "request_meta": {
            "HTTP-client-IP": "127.0.0.1",
        },
        "summary": {
            "objects_found": 2,
            "successful": 1,
            "successful_create": 0,
            "successful_modify": 1,
            "successful_delete": 0,
            "failed": 1,
            "failed_create": 1,
            "failed_modify": 0,
            "failed_delete": 0,
        },
        "objects": [
            {
                "successful": True,
                "type": "modify",
                "object_class": "mntner",
                "rpsl_pk": "TEST-MNT",
                "info_messages": [],
                "error_messages": [],
                "new_object_text": "[trimmed]",
                "submitted_object_text": "[trimmed]",
            },
            {
                "successful": False,
                "type": "create",
                "object_class": "person",
                "rpsl_pk": "PERSON-TEST",
                "info_messages": [],
                "error_messages": ['Mandatory attribute "address" on object person is missing'],
                "new_object_text": None,
                "submitted_object_text": "[trimmed]",
            },
        ],
    }
    mock_urlopen.return_value = io.BytesIO(json.dumps(success_return).encode("utf-8"))

    request = textwrap.dedent("""
        mntner: MNT-EXAMPLE
        delete: delete
        password: password
        override: override
    """).strip()

    return_value = run(
        requests_text=request,
        url=URL,
        debug=True,
        metadata={"x": 2},
    )
    assert return_value == 1
    request_obj = mock_urlopen.call_args[0][0]
    assert request_obj.full_url == URL
    assert request_obj.headers["X-irrd-metadata"] == '{"x": 2}'
    assert request_obj.data == json.dumps({
        "objects": [{"object_text": "mntner: MNT-EXAMPLE\n"}],
        "passwords": ["password"],
        "overrides": ["override"],
        "delete_reason": "delete",
    }).encode("utf-8")

    captured = capsys.readouterr()
    assert captured.out.strip() == textwrap.dedent("""
        SUMMARY OF UPDATE:

        Number of objects found:                    2
        Number of objects processed successfully:   1
            Create:        0
            Modify:        1
            Delete:        0
        Number of objects processed with errors:    1
            Create:        1
            Modify:        0
            Delete:        0

        DETAILED EXPLANATION:

        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ---
        modify succeeded: [mntner] TEST-MNT

        ---
        create FAILED: [person] PERSON-TEST

        [trimmed]
        ERROR: Mandatory attribute "address" on object person is missing

        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """).strip()
    assert "Submitting to " + URL in captured.err


def test_call_failed(capsys, monkeypatch):
    mock_urlopen = Mock()
    monkeypatch.setattr("irrd.scripts.irr_rpsl_submit.request.urlopen", mock_urlopen)

    response = io.BytesIO(b'server response')
    mock_urlopen.side_effect = HTTPError(URL, 400, 'message', {}, response)

    return_value = run(
        requests_text="request",
        url=URL,
        debug=False,
    )
    assert return_value == 2
    request_obj = mock_urlopen.call_args[0][0]
    assert "X-irrd-metadata" not in request_obj.headers

    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err.strip() == "ERROR: response HTTP Error 400: message from server: server response"


def test_no_input(capsys, monkeypatch):
    mock_urlopen = Mock()
    monkeypatch.setattr("irrd.scripts.irr_rpsl_submit.request.urlopen", mock_urlopen)
    mock_urlopen.side_effect = Exception('should not be called')

    return_value = run(
        requests_text='',
        url=URL,
    )
    assert return_value == 3
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err.strip() == "ERROR: received empty input text"
