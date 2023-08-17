from irrd.webui.helpers import secret_key_derive


def test_secret_key_derive(irrd_db):
    key1 = secret_key_derive("scope")
    assert key1 == secret_key_derive("scope")
    key2 = secret_key_derive("scope2")
    assert key1 != key2
