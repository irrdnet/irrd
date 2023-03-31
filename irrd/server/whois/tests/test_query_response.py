from _pytest.python_api import raises

from irrd.conf import PASSWORD_HASH_DUMMY_VALUE
from irrd.utils.rpsl_samples import SAMPLE_MNTNER

from ..query_response import (
    WhoisQueryResponse,
    WhoisQueryResponseMode,
    WhoisQueryResponseType,
)


class TestWhoisQueryResponse:
    def test_response(self):
        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.IRRD, response_type=WhoisQueryResponseType.SUCCESS, result="test"
        ).generate_response()
        assert response == "A5\ntest\nC\n"
        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.IRRD, response_type=WhoisQueryResponseType.SUCCESS, result=""
        ).generate_response()
        assert response == "C\n"
        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.IRRD,
            response_type=WhoisQueryResponseType.KEY_NOT_FOUND,
            result="test",
        ).generate_response()
        assert response == "D\n"
        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.IRRD, response_type=WhoisQueryResponseType.NO_RESPONSE, result="test"
        ).generate_response()
        assert response == ""
        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.IRRD,
            response_type=WhoisQueryResponseType.ERROR_INTERNAL,
            result="test",
        ).generate_response()
        assert response == "F test\n"
        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.IRRD, response_type=WhoisQueryResponseType.ERROR_USER, result="test"
        ).generate_response()
        assert response == "F test\n"
        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.RIPE, response_type=WhoisQueryResponseType.SUCCESS, result="test"
        ).generate_response()
        assert response == "test\n\n\n"
        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.RIPE, response_type=WhoisQueryResponseType.SUCCESS, result=""
        ).generate_response()
        assert response == "%  No entries found for the selected source(s).\n\n\n"
        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.RIPE,
            response_type=WhoisQueryResponseType.KEY_NOT_FOUND,
            result="test",
        ).generate_response()
        assert response == "%  No entries found for the selected source(s).\n\n\n"
        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.RIPE,
            response_type=WhoisQueryResponseType.ERROR_INTERNAL,
            result="test",
        ).generate_response()
        assert response == "%% ERROR: test\n\n\n"
        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.RIPE, response_type=WhoisQueryResponseType.ERROR_USER, result="test"
        ).generate_response()
        assert response == "%% ERROR: test\n\n\n"

        with raises(RuntimeError) as ve:
            # noinspection PyTypeChecker
            WhoisQueryResponse(
                mode="bar", response_type=WhoisQueryResponseType.ERROR_USER, result="foo"
            ).generate_response()  # type:ignore
        assert "foo" in str(ve.value)

        with raises(RuntimeError) as ve:
            # noinspection PyTypeChecker
            WhoisQueryResponse(
                mode=WhoisQueryResponseMode.IRRD, response_type="foo", result="foo"
            ).generate_response()  # type:ignore
        assert "foo" in str(ve.value)

        with raises(RuntimeError) as ve:
            # noinspection PyTypeChecker
            WhoisQueryResponse(
                mode=WhoisQueryResponseMode.RIPE, response_type="foo", result="foo"
            ).generate_response()  # type:ignore
        assert "foo" in str(ve.value)

    def test_auth_hash_removal(self):
        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.RIPE,
            response_type=WhoisQueryResponseType.ERROR_USER,
            result=SAMPLE_MNTNER,
        ).generate_response()
        assert "bcrypt-pw " + PASSWORD_HASH_DUMMY_VALUE in response
        assert "CRYPT-Pw " + PASSWORD_HASH_DUMMY_VALUE in response
        assert "CRYPT-Pw LEuuhsBJNFV0Q" not in response
        assert "MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM." not in response

        response = WhoisQueryResponse(
            mode=WhoisQueryResponseMode.RIPE,
            response_type=WhoisQueryResponseType.ERROR_USER,
            result=SAMPLE_MNTNER,
            remove_auth_hashes=False,
        ).generate_response()
        assert "CRYPT-Pw LEuuhsBJNFV0Q" in response
        assert "MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM." in response
