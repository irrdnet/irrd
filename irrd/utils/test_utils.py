def flatten_mock_calls(mock, flatten_objects=False):
    """
    Flatten the calls performed on a particular mock object,
    into a list of calls with arguments.

    If flatten_objects is set to True, objects of classes not in
    retained_classes are converted to strings.
    """
    result = []
    retained_classes = (int, list, tuple, set, bytes, bytearray)

    for call in mock.mock_calls:
        call = list(call)
        call_name = call[0]
        if '.' in str(call_name):
            call_name = str(call_name).split('.')[-1]
        if flatten_objects:
            args = tuple([str(a) if not isinstance(a, retained_classes) else a for a in call[1]])
        else:
            args = call[1]
        kwargs = call[2]
        result.append([call_name, args, kwargs])
    return result
