from pytest import raises

from ..validators import parse_as_number, ValidationError


def test_validate_as_number():
    assert parse_as_number("AS012345") == ("AS12345", 12345)
    assert parse_as_number("as4294967290") == ("AS4294967290", 4294967290)

    with raises(ValidationError) as ve:
        parse_as_number("12345")
    assert "must start with" in str(ve)

    with raises(ValidationError) as ve:
        parse_as_number("ASFOO")
    assert "number part is not numeric" in str(ve)

    with raises(ValidationError) as ve:
        parse_as_number("AS429496729999")
    assert "maximum value is" in str(ve)
