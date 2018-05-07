from typing import Optional, List, TypeVar


RPSLParserMessagesType = TypeVar("RPSLParserMessagesType", bound="RPSLParserMessages")


class RPSLParserMessages:
    levels = ["INFO", "SUCCESS", "WARNING", "ERROR"]

    def __init__(self):
        self._messages: List[tuple] = []

    def __str__(self):
        messages_str = [f"{msg[0]}: {msg[1]}" for msg in self._messages]
        return "\n".join(messages_str)

    def messages(self):
        return [msg[1] for msg in self._messages]

    def infos(self):
        return [msg[1] for msg in self._messages if msg[0] == "INFO"]

    def errors(self):
        return [msg[1] for msg in self._messages if msg[0] == "ERROR"]

    def message(self, level, message):
        if level not in self.levels:
            raise ValueError(f"Unknown level {level}")
        self._messages.append((level, message))

    def info(self, msg):
        self.message("INFO", msg)

    def success(self, msg):
        self.message("SUCCESS", msg)

    def warning(self, msg):
        self.message("WARNING", msg)

    def error(self, msg):
        self.message("ERROR", msg)

    def merge_messages(self, other_messages: RPSLParserMessagesType):
        self._messages += other_messages._messages


def clean_as_number(value: str, messages: RPSLParserMessages) -> Optional[str]:
    """Validate and clean an AS number. Returns it in ASxxxx format."""
    value = value.upper()
    if not value.startswith("AS"):
        messages.error(f"Invalid AS number {value}: must start with 'AS'")
        return None

    if not value[2:].isnumeric():
        messages.error(f"Invalid AS number {value}: number part is not numeric")
        return None

    value_int = int(value[2:])
    if value_int > 4294967295:
        messages.error(f"Invalid AS number {value}: maximum value is 4294967295")
        return None

    return "AS" + str(value_int)
