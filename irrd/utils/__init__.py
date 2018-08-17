from typing import Iterator


def splitline_unicodesafe(input: str) -> Iterator[str]:
    for line in input.strip("\n").split("\n"):
        yield line
