def flatten_mock_calls(mock):
    """
    Flatten the calls performed on a particular mock object,
    into a list of calls with arguments.
    """
    result = []
    for call in mock.mock_calls:
        call = list(call)
        call_name = call[0]
        if '.' in str(call_name):
            call_name = str(call_name).split('.')[-1]
        result.append([call_name] + call[1:])
    return result
