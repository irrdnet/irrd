import itertools
from typing import Iterable


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
