from typing import Optional, Union

from joserfc import jws
from joserfc.errors import JoseError
from joserfc.rfc7515.model import CompactSignature
from joserfc.rfc7518.ec_key import ECKey

from irrd.conf import get_setting

"""
Convenience functions for handling ECKey private keys,
and decode/encode them for (at this time) NRTMv4 usage.
"""


def eckey_from_config(setting: str, permit_empty=False) -> Optional[ECKey]:
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


def jws_deserialize(value: Union[bytes, str], public_key: ECKey) -> CompactSignature:
    try:
        return jws.deserialize_compact(value, public_key)
    except JoseError as error:
        raise ValueError(error)


def jws_serialize(value: Union[bytes, str], private_key: ECKey) -> str:
    try:
        return jws.serialize_compact({"alg": "ES256"}, value, private_key)
    except JoseError as error:
        raise ValueError(error)
