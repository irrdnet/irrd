from pytest import raises

from ..validators import parse_as_number, ValidationError


def test_validate_as_number():
    assert parse_as_number('AS00') == ('AS0', 0)
    assert parse_as_number('AS012345') == ('AS12345', 12345)
    assert parse_as_number('as4294967290') == ('AS4294967290', 4294967290)
    assert parse_as_number('012345', permit_plain=True) == ('AS12345', 12345)
    assert parse_as_number(12345, permit_plain=True) == ('AS12345', 12345)

    with raises(ValidationError) as ve:
        parse_as_number('12345')
    assert 'must start with' in str(ve.value)

    with raises(ValidationError) as ve:
        parse_as_number('ASFOO')
    assert 'number part is not numeric' in str(ve.value)

    with raises(ValidationError) as ve:
        parse_as_number('AS429496729999')
    assert 'valid range is' in str(ve.value)
