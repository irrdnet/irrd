from enum import Enum, unique
from typing import List, Optional

from irrd.rpsl.parser import UnknownRPSLObjectClassException, RPSLObject
from irrd.rpsl.rpsl_objects import rpsl_object_from_text


@unique
class UpdateRequestStatus(Enum):
    PROCESSED = 'processed'
    PROCESSING = 'processing'
    ERROR_UNKNOWN_CLASS = 'error: unknown RPSL class'
    ERROR_PARSING = 'errors encountered during object parsing'
    ERROR_AUTH = 'error: update not authorised'
    ERROR_REFERENCE = 'error: reference to object that does not exist'
    ERROR_NON_AUTHORITIVE = 'error: attempt to update object in non-authoritive database'


class UpdateRequest:
    rpsl_text: str
    rpsl_obj: Optional[RPSLObject] = None
    status = UpdateRequestStatus.PROCESSING

    error_messages: List[str]
    info_messages: List[str]

    passwords: List[str]
    overrides: List[str]
    pgp_signature: Optional[str] = None

    delete_request: bool = False

    def __init__(self, rpsl_text, delete_request=False):
        self.rpsl_text = rpsl_text
        self.delete_request = delete_request

        try:
            self.rpsl_obj = rpsl_object_from_text(rpsl_text, strict_validation=True)
            if self.rpsl_obj.messages.errors():
                self.status = UpdateRequestStatus.ERROR_PARSING
            self.error_messages = self.rpsl_obj.messages.errors()
            self.info_messages = self.rpsl_obj.messages.infos()

        except UnknownRPSLObjectClassException as exc:
            self.status = UpdateRequestStatus.ERROR_UNKNOWN_CLASS
            self.info_messages = []
            self.error_messages = [str(exc)]


class UpdateRequestParser:
    # TODO: consider placing this in a regular function
    def parse(self, object_texts: str) -> List[UpdateRequest]:
        results = []
        passwords = []
        overrides = []

        object_texts = object_texts.replace('\r', '')
        for object_text in object_texts.split('\n\n'):
            object_text = object_text.strip()

            rpsl_text = ''
            delete_request = False

            # The attributes password/override/delete are magical attributes
            # and need to be extracted before parsing. Delete refers to a specific
            # object, password/override apply to all included objects.
            for line in object_text.splitlines():
                if line.startswith('password:'):
                    password = line.split(':', maxsplit=1)[1].strip()
                    passwords.append(password)
                elif line.startswith('override:'):
                    override = line.split(':', maxsplit=1)[1].strip()
                    overrides.append(override)
                elif line.startswith('delete:'):
                    delete_request = True
                else:
                    rpsl_text += line + '\n'

            if not rpsl_text:
                continue

            results.append(UpdateRequest(rpsl_text, delete_request=delete_request))

        for result in results:
            result.passwords = passwords
            result.overrides = overrides
        return results
