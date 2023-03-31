from io import StringIO

import pytest

from irrd.conf import PASSWORD_HASH_DUMMY_VALUE
from irrd.utils.rpsl_samples import SAMPLE_MNTNER

from ..text import (
    remove_auth_hashes,
    remove_last_modified,
    snake_to_camel_case,
    split_paragraphs_rpsl,
    splitline_unicodesafe,
)


def test_remove_auth_hashes():
    with pytest.raises(ValueError):
        remove_auth_hashes(["a", "b"])

    original_text = SAMPLE_MNTNER
    assert "CRYPT-Pw LEuuhsBJNFV0Q" in original_text
    assert "MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM." in original_text
    assert "bcrypt-pw $2b$12$RMrlONJ0tasnpo.zHDF.yuYm/Gb1ARmIjP097ZoIWBn9YLIM2ao5W" in original_text

    result = remove_auth_hashes(original_text)
    assert "CRYPT-Pw " + PASSWORD_HASH_DUMMY_VALUE in result
    assert "CRYPT-Pw LEuuhsBJNFV0Q" not in result
    assert "MD5-pw " + PASSWORD_HASH_DUMMY_VALUE in result
    assert "MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM." not in result
    assert "bcrypt-pw " + PASSWORD_HASH_DUMMY_VALUE in result
    assert "bcrypt-pw $2b$12$RMrlONJ0tasnpo.zHDF.yuYm/Gb1ARmIjP097ZoIWBn9YLIM2ao5W" not in result
    assert "other_text" == remove_auth_hashes("other_text")


def test_remove_last_modified():
    # This descr line should be kept, only real last-modified attributes should be removed
    expected_text = SAMPLE_MNTNER + "descr: last-modified:  2020-01-01T00:00:00Z\n"
    result = remove_last_modified(expected_text + "last-modified:  2020-01-01T00:00:00Z\n")
    assert result == expected_text


def test_splitline_unicodesafe():
    # U+2028 is the unicode line separator
    assert list(splitline_unicodesafe("")) == []
    assert list(splitline_unicodesafe("\nfoo\n\rb\u2028ar\n")) == ["foo", "b\u2028ar"]


def test_split_paragraphs_rpsl():
    paragraphs = split_paragraphs_rpsl("\n% ignore\npar 1\npar 1\n\npar 2\npar \u20282")
    assert list(paragraphs) == [
        "par 1\npar 1\n",
        "par 2\npar \u20282\n",
    ]

    paragraphs = split_paragraphs_rpsl(StringIO("\n% include\n\npar 1\npar 1\n\npar 2\npar \u20282"), False)
    assert list(paragraphs) == [
        "% include\n",
        "par 1\npar 1\n",
        "par 2\npar \u20282\n",
    ]


def test_snake_to_camel_case():
    assert snake_to_camel_case("foo1_bar") == "foo1Bar"
    assert snake_to_camel_case(["foo1_bar", "second_item"]) == ["foo1Bar", "secondItem"]
