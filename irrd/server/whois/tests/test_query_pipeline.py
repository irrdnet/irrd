from unittest.mock import Mock

from ..query_pipeline import QueryPipelineThread
from ..query_response import WhoisQueryResponse, WhoisQueryResponseMode, WhoisQueryResponseType


class TestQueryPipeLineThread:

    def test_query_flow(self):
        response = b''
        lose_connection_called = False

        def response_callback(local_response: bytes):
            nonlocal response
            response = local_response

        def lose_connection_callback():
            nonlocal lose_connection_called
            lose_connection_called = True

        mock_query_parser = Mock()
        mock_query_parser.handle_query = lambda q: WhoisQueryResponse(mode=WhoisQueryResponseMode.IRRD, response_type=WhoisQueryResponseType.SUCCESS, result=q)

        qpt = QueryPipelineThread(
            peer_str='[127.0.0.1]:99999',
            query_parser=mock_query_parser,
            response_callback=response_callback,
            lose_connection_callback=lose_connection_callback,
        )

        sample_query = 'query 🌈'.encode('utf-8')
        sample_output = b'A8\n' + sample_query + b'\nC\n'

        assert not qpt.is_processing_queries()
        qpt.add_query(sample_query)
        assert qpt.is_processing_queries()
        qpt._fetch_process_query()
        assert not qpt.is_processing_queries()
        assert response == sample_output

        response = None
        qpt.add_query(b'')
        qpt._fetch_process_query()
        assert not response

        qpt.ready_for_next_result()
        qpt.ready_for_next_result()

        # This call should time out after two seconds
        response = None
        qpt._fetch_process_query()
        assert not response

        # As ready_for_next_result() was called, this should return
        # another result to response_callback.
        response = None
        sample_query = 'query 🌈'.encode('utf-8')
        qpt.add_query(sample_query)
        qpt._fetch_process_query()
        assert response == sample_output

        response = None
        qpt.add_query(b'!q\n')
        qpt._fetch_process_query()
        assert not response
        assert lose_connection_called
        assert qpt.cancelled
