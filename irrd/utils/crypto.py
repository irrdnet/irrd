from joserfc import jws
from joserfc.errors import JoseError
from joserfc.jwk import ECKey
from joserfc.jws import CompactSignature, JWSRegistry

from irrd.conf import get_setting

"""
Convenience functions for handling ECKey private keys,
and decode/encode them for (at this time) NRTMv4 usage.
"""

jws_registry = JWSRegistry()
jws_registry.max_payload_length = 10 * 1024 * 1024


def eckey_from_config(setting: str, permit_empty=False) -> ECKey | None:
    value = get_setting(setting)
    if not value and permit_empty:
        return None
    return eckey_from_str(value)


def eckey_from_str(encoded: str, require_private=False) -> ECKey:
    key = ECKey.import_key(encoded)
    if require_private and not key.is_private:
        raise ValueError("ECKey is a public key, but must be a private key")
    return key


def eckey_public_key_as_str(key: ECKey) -> str:
    return key.as_pem(private=False).decode("ascii")


def eckey_private_key_as_str(key: ECKey) -> str:
    return key.as_pem(private=True).decode("ascii")


def jws_deserialize(value: bytes | str, public_key: ECKey) -> CompactSignature:
    try:
        return jws.deserialize_compact(value, public_key, registry=jws_registry)
    except JoseError as error:
        raise ValueError(error)


def jws_serialize(value: bytes | str, private_key: ECKey) -> str:
    try:
        return jws.serialize_compact({"alg": "ES256"}, value, private_key, registry=jws_registry)
    except JoseError as error:  # pragma: no cover
        raise ValueError(error)
