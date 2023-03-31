from graphql import GraphQLError
from starlette.requests import HTTPConnection

from ..extensions import QueryMetadataExtension, error_formatter


def test_query_metedata_extension(caplog):
    extension = QueryMetadataExtension()

    mock_request = HTTPConnection(
        {
            "type": "http",
            "client": ("127.0.0.1", "8000"),
        }
    )
    mock_request._json = {
        "operationName": "operation",
        "query": "graphql query",
    }
    context = {
        "sql_queries": ["sql query"],
        "request": mock_request,
    }
    extension.request_started(context)
    result = extension.format(context)
    assert "127.0.0.1 ran query in " in caplog.text
    assert ": {'operationName': 'operation', 'query': 'graphqlquery'}" in caplog.text
    assert result["execution"] < 3
    assert result["sql_query_count"] == 1
    assert result["sql_queries"] == ["sql query"]


def test_error_formatter():
    # Regular GraphQL error should always be passed
    error = GraphQLError(message="error")
    result = error_formatter(error)
    assert result["message"] == "error"

    # If original_error is something else, hide except when in debug mode
    error = GraphQLError(message="error", original_error=ValueError())
    result = error_formatter(error)
    assert result["message"] == "Internal server error"

    result = error_formatter(error, debug=True)
    assert result["message"] == "error"
    assert result["extensions"] == {"exception": None}
