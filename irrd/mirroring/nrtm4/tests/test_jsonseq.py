import io

from ..jsonseq import jsonseq_decode, jsonseq_encode


def test_jsonseq_decode():
    expected = ["foo", "bar", {"dict": 42}]
    stream = io.BytesIO(b'\x1e"foo"\x1e"bar"\n\x1e{"dict":42}\n')
    assert list(jsonseq_decode(stream)) == expected


def test_jsonseq_encode():
    data = ["foo", {"dict": 42}]
    expected = b'\x1e"foo"\n\x1e{"dict":42}\n'

    stream = io.BytesIO()
    jsonseq_encode(data, stream)
    assert stream.getvalue() == expected

    stream = io.BytesIO()
    jsonseq_encode(iter(data), stream)
    assert stream.getvalue() == expected
