import pydantic
import pytest
from pytest import raises

from ..validators import parse_as_number, ValidationError, RPSLChangeSubmission


def test_validate_as_number():
    assert parse_as_number('AS012345') == ('AS12345', 12345)
    assert parse_as_number('as4294967290') == ('AS4294967290', 4294967290)

    with raises(ValidationError) as ve:
        parse_as_number('12345')
    assert 'must start with' in str(ve.value)

    with raises(ValidationError) as ve:
        parse_as_number('ASFOO')
    assert 'number part is not numeric' in str(ve.value)

    with raises(ValidationError) as ve:
        parse_as_number('AS429496729999')
    assert 'maximum value is' in str(ve.value)


def test_validate_rpsl_change_submission():
    result = RPSLChangeSubmission.parse_obj({
        'objects': [
            {'object_text': 'text'},
            {'attributes': [
                {'name': 'name1', 'value': 'value1'},
                {'name': 'name1', 'value': ['list1', 'list2']},
            ]},
        ],
        'passwords': ['password'],
        'override': 'override',
        'delete_reason': 'delete reason',
    })
    assert result.objects[1].attributes[1].value == 'list1, list2'

    with pytest.raises(pydantic.ValidationError):
        RPSLChangeSubmission.parse_obj({
            'objects': [
                {'attributes': [
                    {'name': 'name1', 'missing-value': 'value1'},
                ]},
            ],
        })

    with pytest.raises(pydantic.ValidationError):
        RPSLChangeSubmission.parse_obj({
            'objects': [
                {'object_text': 'text', 'attributes': [
                    {'name': 'name1', 'value': 'value1'},
                ]},
            ],
        })
