import hashlib
import itertools
from typing import Iterable

from irrd.conf import get_setting


def chunked_iterable(iterable: Iterable, size: int) -> Iterable:
    """
    Yield chunks from an iterable in chunks of size `size`.
    """
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, size))
        if not chunk:
            break
        yield chunk


def secret_key_derive(scope: str):
    """
    Return the secret key for a particular scope.
    This is derived from the scope, an otherwise meaningless string,
    and the user configured secret key.
    """
    key_base = scope.encode("utf-8") + get_setting("secret_key").encode("utf-8")
    return str(hashlib.sha512(key_base).hexdigest())
