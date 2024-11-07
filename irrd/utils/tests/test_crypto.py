import pytest
from joserfc.rfc7518.ec_key import ECKey

from irrd.utils.crypto import (
    eckey_from_config,
    eckey_from_str,
    eckey_private_key_as_str,
    eckey_public_key_as_str,
    jws_deserialize,
    jws_serialize,
)


def test_crypto_eckey(config_override):
    private_key = ECKey.generate_key()
    config_override(
        {
            "sources": {"TEST": {"nrtm4_server_private_key": eckey_private_key_as_str(private_key)}},
            "invalid": "invalid",
        }
    )
    assert eckey_from_config("sources.TEST.nrtm4_server_private_key").as_pem() == private_key.as_pem()
    assert eckey_from_str(
        eckey_public_key_as_str(eckey_from_str(eckey_private_key_as_str(private_key)))
    ).as_pem() == private_key.as_pem(private=False)
    assert eckey_from_config("sources.OTHER.nrtm4_server_private_key", permit_empty=True) is None

    with pytest.raises(ValueError):
        eckey_from_config("invalid")

    eckey_from_str(eckey_public_key_as_str(private_key), require_private=False)
    with pytest.raises(ValueError):
        eckey_from_str(eckey_public_key_as_str(private_key), require_private=True)
    with pytest.raises(ValueError):
        eckey_from_str(eckey_public_key_as_str(private_key)[:20])

    payload = b"test"
    assert (
        jws_deserialize(
            jws_serialize(payload, private_key), eckey_from_str(eckey_public_key_as_str(private_key))
        ).payload
        == payload
    )
    with pytest.raises(ValueError):
        jws_deserialize(jws_serialize(payload, private_key), ECKey.generate_key())

    with pytest.raises(ValueError):
        jws_serialize(payload, "invalid")
