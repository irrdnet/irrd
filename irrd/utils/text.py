import re
from typing import Iterator, Union, TextIO, Optional

from irrd.conf import PASSWORD_HASH_DUMMY_VALUE
from irrd.rpsl.config import PASSWORD_HASHERS

re_remove_passwords = re.compile(r'(%s)[^\n]+' % '|'.join(PASSWORD_HASHERS.keys()), flags=re.IGNORECASE)


def remove_auth_hashes(input: Optional[str]):
    if not input:
        return input
    return re_remove_passwords.sub(r'\1 %s  # Filtered for security' % PASSWORD_HASH_DUMMY_VALUE, input)


def splitline_unicodesafe(input: str) -> Iterator[str]:
    """
    Split an input string by newlines, and return an iterator of the lines.

    This is a replacement for Python's built-in splitlines, which also splits
    on characters such as unicode line separator (U+2028). In RPSL, that should
    not be considered a line separator.
    """
    if not input:
        return
    for line in input.strip('\n').split('\n'):
        yield line.strip('\r')


def split_paragraphs_rpsl(input: Union[str, TextIO], strip_comments=True) -> Iterator[str]:
    """
    Split an input into paragraphs, and return an iterator of the paragraphs.

    A paragraph is a block of text, separated by at least one empty line.
    Note that a line with other whitespace, e.g. a space, is not considered
    empty.

    If strip_comments=True, any line starting with % or # is entirely ignored,
    both within a paragraph and between paragraphs.
    """
    current_paragraph = ''
    if isinstance(input, str):
        generator = splitline_unicodesafe(input)
    else:
        generator = iter(input.readlines())

    for line in generator:
        line = line.strip('\r\n')
        if strip_comments and line.startswith('%') or line.startswith('#'):
            continue
        if line:
            current_paragraph += line + '\n'
        if not line:
            if current_paragraph:
                yield current_paragraph
            current_paragraph = ''

    if current_paragraph.strip():
        yield current_paragraph
