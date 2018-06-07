from typing import Optional, Tuple

from irrd.rpsl.parser_state import RPSLParserMessages


def parse_as_number(value: str, messages: RPSLParserMessages) -> Tuple[Optional[str], Optional[int]]:
    """Validate and clean an AS number. Returns it in ASxxxx and numeric format."""
    value = value.upper()
    if not value.startswith("AS"):
        messages.error(f"Invalid AS number {value}: must start with 'AS'")
        return None, None

    if not value[2:].isnumeric():
        messages.error(f"Invalid AS number {value}: number part is not numeric")
        return None, None

    value_int = int(value[2:])
    if value_int > 4294967295:
        messages.error(f"Invalid AS number {value}: maximum value is 4294967295")
        return None, None

    return "AS" + str(value_int), value_int
