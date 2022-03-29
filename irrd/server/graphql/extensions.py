import logging
import time

from ariadne import format_error
from ariadne.types import Extension
from graphql import GraphQLError

logger = logging.getLogger(__name__)


class QueryMetadataExtension(Extension):
    """
    Ariadne extension to add query metadata.
    - Returns the execution time
    - Returns SQL queries if SQL trace was enabled
    - Logs the query and execution time
    """
    def __init__(self):
        self.start_timestamp = None
        self.end_timestamp = None

    def request_started(self, context):
        self.start_timestamp = time.perf_counter()

    def format(self, context):
        data = {}
        if self.start_timestamp:
            data['execution'] = time.perf_counter() - self.start_timestamp
        if 'sql_queries' in context:
            data['sql_query_count'] = len(context['sql_queries'])
            data['sql_queries'] = context['sql_queries']

        query = context['request']._json
        if context['request']._json.get('operationName') != 'IntrospectionQuery':
            # Reformat the query to make it fit neatly on a single log line
            query['query'] = query['query'].replace(' ', '').replace('\n', ' ').replace('\t', '')
            client = context['request'].client.host
            logger.info(f'{client} ran query in {data.get("execution")}s: {query}')
        return data


def error_formatter(error: GraphQLError, debug: bool=False):
    """
    Custom Ariadne error formatter. A generic text is used if the
    server is not in debug mode and the original error is a
    different error (as in, a different kind of exception raised
    during processing).
    """
    if debug or not error.original_error or isinstance(error.original_error, GraphQLError):
        return format_error(error, debug)

    formatted = error.formatted
    formatted["message"] = "Internal server error"
    return formatted
