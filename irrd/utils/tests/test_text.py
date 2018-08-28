from io import StringIO

from ..text import splitline_unicodesafe, split_paragraphs_rpsl


def test_splitline_unicodesafe():
    # U+2028 is the unicode line separator
    assert list(splitline_unicodesafe('')) == []
    assert list(splitline_unicodesafe('\nfoo\n\rb\u2028ar\n')) == ['foo', 'b\u2028ar']


def test_split_paragraphs_rpsl():
    paragraphs = split_paragraphs_rpsl('\n% ignore\npar 1\npar 1\n\npar 2\npar \u20282')
    assert list(paragraphs) == [
        'par 1\npar 1\n',
        'par 2\npar \u20282\n',
    ]

    paragraphs = split_paragraphs_rpsl(StringIO('\n% include\n\npar 1\npar 1\n\npar 2\npar \u20282'), False)
    assert list(paragraphs) == [
        '% include\n',
        'par 1\npar 1\n',
        'par 2\npar \u20282\n',
    ]
