import itertools
from typing import Iterable, List

import pydantic


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


def format_pydantic_errors(exception: pydantic.ValidationError) -> List[str]:
    """
    Format a rich pydantic ValidationError into a list of strings
    with reasonable formatting, suitable for user output or logs.
    """
    errors = []
    for error in exception.errors():
        loc_str = "->".join(map(str, error["loc"]))
        if loc_str:
            loc_str = loc_str + ": "
        errors.append(loc_str + error["msg"])
    return errors
