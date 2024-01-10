from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from irrd.utils.crypto import (
    ed25519_private_key_as_str,
    ed25519_private_key_from_config,
    ed25519_private_key_from_str,
    ed25519_public_key_as_str,
    ed25519_public_key_from_str,
)


def test_crypto_ed25519(config_override):
    private_key = Ed25519PrivateKey.generate()
    config_override(
        {"sources": {"TEST": {"nrtm4_server_private_key": ed25519_private_key_as_str(private_key)}}}
    )
    assert (
        ed25519_private_key_from_config("sources.TEST.nrtm4_server_private_key").private_bytes_raw()
        == private_key.private_bytes_raw()
    )
    assert (
        ed25519_public_key_from_str(
            ed25519_public_key_as_str(
                ed25519_private_key_from_str(ed25519_private_key_as_str(private_key)).public_key()
            )
        ).public_bytes_raw()
        == private_key.public_key().public_bytes_raw()
    )
    assert (
        ed25519_private_key_from_config("sources.OTHER.nrtm4_server_private_key", permit_empty=True) is None
    )
