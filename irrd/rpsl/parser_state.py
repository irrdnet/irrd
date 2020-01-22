from typing import TypeVar, List

from IPy import IP

RPSLParserMessagesType = TypeVar('RPSLParserMessagesType', bound='RPSLParserMessages')


class RPSLParserMessages:
    levels = ['INFO', 'ERROR']

    def __init__(self) -> None:
        self._messages: List[tuple] = []

    def __str__(self) -> str:
        messages_str = [f'{msg[0]}: {msg[1]}' for msg in self._messages]
        return '\n'.join(messages_str)

    def messages(self) -> List[str]:
        return [msg[1] for msg in self._messages]

    def infos(self) -> List[str]:
        return [msg[1] for msg in self._messages if msg[0] == 'INFO']

    def errors(self) -> List[str]:
        return [msg[1] for msg in self._messages if msg[0] == 'ERROR']

    def info(self, msg: str) -> None:
        self._message('INFO', msg)

    def error(self, msg: str) -> None:
        self._message('ERROR', msg)

    def merge_messages(self, other_messages: RPSLParserMessagesType) -> None:
        self._messages += other_messages._messages

    def _message(self, level: str, message: str) -> None:
        self._messages.append((level, message))


class RPSLFieldParseResult:
    def __init__(self, value: str, values_list: List[str]=None, ip_first: IP=None, ip_last: IP=None,
                 prefix: IP=None, prefix_length: int=None, asn_first: int=None, asn_last: int=None) -> None:
        self.value = value
        self.values_list = values_list
        self.ip_first = ip_first
        self.ip_last = ip_last
        self.prefix = prefix
        self.prefix_length = prefix_length
        self.asn_first = asn_first
        self.asn_last = asn_last
