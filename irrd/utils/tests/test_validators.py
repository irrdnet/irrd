import pydantic
import pytest
from pytest import raises

from ..validators import RPSLChangeSubmission, ValidationError, parse_as_number


def test_validate_as_number():
    assert parse_as_number("AS00") == ("AS0", 0)
    assert parse_as_number("AS012345") == ("AS12345", 12345)
    assert parse_as_number("as4294967295") == ("AS4294967295", 4294967295)
    assert parse_as_number("012345", permit_plain=True) == ("AS12345", 12345)
    assert parse_as_number(12345, permit_plain=True) == ("AS12345", 12345)

    with raises(ValidationError) as ve:
        parse_as_number("12345")
    assert "must start with" in str(ve.value)

    with raises(ValidationError) as ve:
        parse_as_number("AS1.10")
    assert "number part is not numeric" in str(ve.value)

    with raises(ValidationError) as ve:
        parse_as_number("ASFOO")
    assert "number part is not numeric" in str(ve.value)

    with raises(ValidationError) as ve:
        parse_as_number("AS4294967296")
    assert "valid range is" in str(ve.value)


def test_validate_asdot_as_number(config_override):
    config_override({"compatibility": {"asdot_queries": True}})

    test_validate_as_number()

    assert parse_as_number("AS1.10", asdot_permitted=True) == ("AS65546", 65546)
    assert parse_as_number("1.10", permit_plain=True, asdot_permitted=True) == ("AS65546", 65546)

    with raises(ValidationError) as ve:
        parse_as_number("AS1.2.3", asdot_permitted=True)
    assert "number is not valid asdot format" in str(ve.value)

    with raises(ValidationError) as ve:
        parse_as_number("AS.10", asdot_permitted=True)
    assert "high order value missing" in str(ve.value)

    with raises(ValidationError) as ve:
        parse_as_number("AS65546.10", asdot_permitted=True)
    assert "high order value out of range" in str(ve.value)

    with raises(ValidationError) as ve:
        parse_as_number("AS1.", asdot_permitted=True)
    assert "low order value missing" in str(ve.value)

    with raises(ValidationError) as ve:
        parse_as_number("AS1.65546", asdot_permitted=True)
    assert "low order value out of range" in str(ve.value)

    with raises(ValidationError) as ve:
        parse_as_number("AS1.10")
    assert "number part is not numeric" in str(ve.value)


def test_validate_rpsl_change_submission():
    result = RPSLChangeSubmission.model_validate(
        {
            "objects": [
                {"object_text": "text"},
                {
                    "attributes": [
                        {"name": "name1", "value": "value1"},
                        {"name": "name1", "value": ["list1", "list2"]},
                    ]
                },
            ],
            "passwords": ["password"],
            "override": "override",
            "delete_reason": "delete reason",
        }
    )
    assert result.objects[1].attributes[1].value == "list1, list2"

    with pytest.raises(pydantic.ValidationError):
        RPSLChangeSubmission.model_validate(
            {
                "objects": [
                    {
                        "attributes": [
                            {"name": "name1", "missing-value": "value1"},
                        ]
                    },
                ],
            }
        )

    with pytest.raises(pydantic.ValidationError):
        RPSLChangeSubmission.model_validate(
            {
                "objects": [
                    {
                        "object_text": "text",
                        "attributes": [
                            {"name": "name1", "value": "value1"},
                        ],
                    },
                ],
            }
        )
