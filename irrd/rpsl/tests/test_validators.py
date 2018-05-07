from ..validators import clean_as_number, RPSLParserMessages


def test_validate_as_number():
    messages = RPSLParserMessages()
    assert clean_as_number("AS012345", messages) == "AS12345"
    assert clean_as_number("as4294967290", messages) == "AS4294967290"
    assert not messages.errors()

    messages = RPSLParserMessages()
    assert not clean_as_number("12345", messages)
    assert "must start with" in messages.errors()[0]
    assert len(messages.errors()) == 1

    messages = RPSLParserMessages()
    assert not clean_as_number("ASFOO", messages)
    assert "number part is not numeric" in messages.errors()[0]
    assert len(messages.errors()) == 1

    messages = RPSLParserMessages()
    assert not clean_as_number("AS429496729999", messages)
    assert "maximum value is" in messages.errors()[0]
    assert len(messages.errors()) == 1
