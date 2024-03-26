import base64
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from irrd.conf import get_setting

"""
Convenience functions for handling Ed25519 private keys,
and decode/encode them for (at this time) NRTMv4 usage.
"""


def ed25519_private_key_from_config(setting: str, permit_empty=False) -> Optional[Ed25519PrivateKey]:
    value = get_setting(setting)
    if not value and permit_empty:
        return None
    return ed25519_private_key_from_str(value)


def ed25519_public_key_from_str(encoded: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded))


def ed25519_private_key_from_str(encoded: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(encoded))


def ed25519_public_key_as_str(public_key: Ed25519PublicKey) -> str:
    return base64.b64encode(public_key.public_bytes_raw()).decode("ascii")


def ed25519_private_key_as_str(private_key: Ed25519PrivateKey) -> str:
    return base64.b64encode(private_key.private_bytes_raw()).decode("ascii")
