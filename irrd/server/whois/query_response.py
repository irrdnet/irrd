import re
from enum import Enum
from typing import Optional

from irrd.conf import PASSWORD_HASH_DUMMY_VALUE
from irrd.rpsl.config import PASSWORD_HASHERS

re_remove_passwords = re.compile(r'(%s)[^\n]+' % '|'.join(PASSWORD_HASHERS.keys()), flags=re.IGNORECASE)


class WhoisQueryResponseType(Enum):
    """Types of responses to queries. KEY_NOT_FOUND is specific to IRRD-style."""
    SUCCESS = 'success'
    ERROR = 'error'
    KEY_NOT_FOUND = 'key_not_found'


class WhoisQueryResponseMode(Enum):
    """Response mode for queries - IRRD and RIPE queries have different output."""
    IRRD = 'irrd'
    RIPE = 'ripe'


class WhoisQueryResponse:
    """
    Container for all data for a response to a query.

    Based on the response_type and mode, can render a string of the complete
    response to send back to the user.
    """
    response_type: WhoisQueryResponseType = WhoisQueryResponseType.SUCCESS
    mode: WhoisQueryResponseMode = WhoisQueryResponseMode.RIPE
    result: Optional[str] = None

    def __init__(
            self,
            response_type: WhoisQueryResponseType,
            mode: WhoisQueryResponseMode,
            result: Optional[str],
    ) -> None:
        self.response_type = response_type
        self.mode = mode
        self.result = result

    def generate_response(self) -> str:
        if self.result:
            self.result = re_remove_passwords.sub(r'\1 %s  # Filtered for security' % PASSWORD_HASH_DUMMY_VALUE, self.result)

        if self.mode == WhoisQueryResponseMode.IRRD:
            response = self._generate_response_irrd()
            if response:
                return response

        elif self.mode == WhoisQueryResponseMode.RIPE:
            response = self._generate_response_ripe()
            if response:
                return response

        raise RuntimeError(f'Unable to formulate response for {self.response_type} / {self.mode}: {self.result}')

    def _generate_response_irrd(self) -> Optional[str]:
        if self.response_type == WhoisQueryResponseType.SUCCESS:
            if self.result:
                result_len = len(self.result) + 1
                return f'A{result_len}\n{self.result}\nC\n'
            else:
                return 'C\n'
        elif self.response_type == WhoisQueryResponseType.KEY_NOT_FOUND:
            return f'D\n'
        elif self.response_type == WhoisQueryResponseType.ERROR:
            return f'F {self.result}\n'
        return None

    def _generate_response_ripe(self) -> Optional[str]:
        if self.response_type == WhoisQueryResponseType.SUCCESS:
            if self.result:
                return self.result + '\n\n'
            return '%  No entries found for the selected source(s).\n'
        elif self.response_type == WhoisQueryResponseType.KEY_NOT_FOUND:
            return '%  No entries found for the selected source(s).\n'
        elif self.response_type == WhoisQueryResponseType.ERROR:
            return f'%% {self.result}\n'
        return None
