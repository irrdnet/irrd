from ..misc import chunked_iterable, secret_key_derive


def test_chunked_iterable():
    inp = range(10)
    assert list(chunked_iterable(inp, 3)) == [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9,)]


def test_secret_key_derive(config_override):
    config_override({"secret_key": "secret"})
    assert secret_key_derive("scope").startswith("eeae975812")
