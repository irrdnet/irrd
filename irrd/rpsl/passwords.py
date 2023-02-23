from enum import Enum, unique

from passlib.hash import bcrypt, des_crypt, md5_crypt

from irrd.conf import get_setting


@unique
class PasswordHasherAvailability(Enum):
    ENABLED = "enabled"
    LEGACY = "legacy"
    DISABLED = "disabled"


PASSWORD_HASHERS_ALL = {
    "CRYPT-PW": des_crypt,
    "MD5-PW": md5_crypt,
    "BCRYPT-PW": bcrypt,
}


def get_password_hashers(permit_legacy=True):
    """
    Get the enabled password hashers, and if permit_legacy is True, also legacy ones.
    Returned as a dict with keys being auth values, values being the hash functions.
    """
    hashers = {}
    included_availabilities = {PasswordHasherAvailability.ENABLED}
    if permit_legacy:
        included_availabilities.add(PasswordHasherAvailability.LEGACY)

    for hasher_name, hasher_function in PASSWORD_HASHERS_ALL.items():
        setting = get_setting(f"auth.password_hashers.{hasher_name.lower()}")
        availability = getattr(PasswordHasherAvailability, setting.upper())
        if availability in included_availabilities:
            hashers[hasher_name] = hasher_function

    return hashers


PASSWORD_REPLACEMENT_HASH = ("BCRYPT-PW", bcrypt)
