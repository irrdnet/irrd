from ..parser_state import RPSLParserMessages
from ..validators import parse_as_number


def test_validate_as_number():
    messages = RPSLParserMessages()
    assert parse_as_number("AS012345", messages) == ("AS12345", 12345)
    assert parse_as_number("as4294967290", messages) == ("AS4294967290", 4294967290)
    assert not messages.errors()

    messages = RPSLParserMessages()
    assert parse_as_number("12345", messages) == (None, None)
    assert "must start with" in messages.errors()[0]
    assert len(messages.errors()) == 1

    messages = RPSLParserMessages()
    assert parse_as_number("ASFOO", messages) == (None, None)
    assert "number part is not numeric" in messages.errors()[0]
    assert len(messages.errors()) == 1

    messages = RPSLParserMessages()
    assert parse_as_number("AS429496729999", messages) == (None, None)
    assert "maximum value is" in messages.errors()[0]
    assert len(messages.errors()) == 1
