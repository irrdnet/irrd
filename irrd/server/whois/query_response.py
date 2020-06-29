from enum import Enum
from typing import Optional

from irrd.utils.text import remove_auth_hashes


class WhoisQueryResponseType(Enum):
    """
    Types of responses to queries.
    KEY_NOT_FOUND is specific to IRRD-style.
    NO_RESPONSE means no response should be sent at all.
    """
    SUCCESS = 'success'
    ERROR = 'error'
    KEY_NOT_FOUND = 'key_not_found'
    NO_RESPONSE = 'no_response'


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
        self.result = remove_auth_hashes(self.result)

        if self.mode == WhoisQueryResponseMode.IRRD:
            response = self._generate_response_irrd()
            if response is not None:
                return response

        elif self.mode == WhoisQueryResponseMode.RIPE:
            response = self._generate_response_ripe()
            if response is not None:
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
            return 'D\n'
        elif self.response_type == WhoisQueryResponseType.ERROR:
            return f'F {self.result}\n'
        elif self.response_type == WhoisQueryResponseType.NO_RESPONSE:
            return ''
        return None

    def _generate_response_ripe(self) -> Optional[str]:
        s = None
        if self.response_type == WhoisQueryResponseType.SUCCESS:
            if self.result:
                s = self.result
            else:
                s = '%  No entries found for the selected source(s).'
        elif self.response_type == WhoisQueryResponseType.KEY_NOT_FOUND:
            s = '%  No entries found for the selected source(s).'
        elif self.response_type == WhoisQueryResponseType.ERROR:
            s = f'%% ERROR: {self.result}'
        if s is not None:
            # Sending an RPSL response in RIPE format. According to
            # https://www.ripe.net/manage-ips-and-asns/db/support/documentation/ripe-database-query-reference-manual#2-0-querying-the-ripe-database
            # there need to be exactly 2 empty lines at the end of a response.
            s = s.rstrip('\n')
            return "{0}{1}\n\n".format(s, '\n' if len(s) else '')
        return None
