from enum import Enum, unique

from passlib.hash import bcrypt, des_crypt, md5_crypt

from irrd.conf import BCRYPT_MAX_ROUNDS, PASSWORD_HASH_DUMMY_VALUE, get_setting


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


def bcrypt_hash_error(auth_value: str) -> str | None:
    """Check a BCRYPT-PW auth attribute value, returning an error if it is unusable."""
    scheme, _, password_hash = auth_value.partition(" ")
    # Queries return dummy values, which are submitted back unchanged
    if scheme.upper() != "BCRYPT-PW" or password_hash == PASSWORD_HASH_DUMMY_VALUE:
        return None
    try:
        rounds = bcrypt.from_string(password_hash).rounds
    except ValueError:
        # Includes a cost factor over 31, which passlib refuses to verify
        return "invalid bcrypt hash"
    if rounds > BCRYPT_MAX_ROUNDS:
        return f"bcrypt cost factor must be {BCRYPT_MAX_ROUNDS} or lower"
    return None


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


def verify_auth_lines(
    auth_lines: list[str], passwords: list[str], keycert_obj_pk: str | None = None
) -> str | None:
    """
    Verify whether one of a given list of passwords matches
    any of the auth lines in the provided list, or match the
    keycert object PK.
    Returns None for auth failed, a scheme or PGP key PK
    for success.
    """
    hashers = get_password_hashers(permit_legacy=True)
    for auth in auth_lines:
        if keycert_obj_pk and auth.upper() == keycert_obj_pk.upper():
            return keycert_obj_pk.upper()
        if " " not in auth:
            continue
        scheme, hash = auth.split(" ", 1)
        scheme = scheme.upper()
        hasher = hashers.get(scheme)
        if hasher:
            for password in passwords:
                try:
                    if hasher.verify(password, hash):
                        return scheme
                except ValueError:
                    pass
    return None
