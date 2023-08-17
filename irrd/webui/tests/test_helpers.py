import pytest

from irrd.webui.helpers import secret_key_derive


def test_secret_key_derive(irrd_db):
    with pytest.raises(ValueError):
        secret_key_derive("scope")
    key1 = secret_key_derive("scope", thread_safe=False)
    assert key1 == secret_key_derive("scope")
    key2 = secret_key_derive("scope2")
    assert key1 != key2
