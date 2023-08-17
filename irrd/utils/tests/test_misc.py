from ..misc import chunked_iterable


def test_chunked_iterable():
    inp = range(10)
    assert list(chunked_iterable(inp, 3)) == [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9,)]
