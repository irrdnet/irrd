from enum import Enum, unique
from typing import List, Optional

from dataclasses import dataclass, field

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


@dataclass
class UpdateRequest:
    rpsl_text: str
    rpsl_obj: Optional[RPSLObject] = None
    status = UpdateRequestStatus.PROCESSING

    error_messages: List[str] = field(default_factory=list)
    info_messages: List[str] = field(default_factory=list)

    passwords: List[str] = field(default_factory=list)
    overrides: List[str] = field(default_factory=list)
    pgp_signature: Optional[str] = None

    delete_request: bool = False


class UpdateRequestParser:
    def parse(self, object_texts: str) -> List[UpdateRequest]:
        results = []
        passwords = []
        overrides = []

        object_texts = object_texts.replace('\r', '')
        for object_text in object_texts.split('\n\n'):
            object_text = object_text.strip()

            rpsl_text = ''
            delete_request = False

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

            request = UpdateRequest(rpsl_text=rpsl_text, delete_request=delete_request)  # type: ignore

            try:
                request.rpsl_obj = rpsl_object_from_text(rpsl_text, strict_validation=True)
                if request.rpsl_obj.messages.errors():
                    request.status = UpdateRequestStatus.ERROR_PARSING
                request.error_messages = request.rpsl_obj.messages.errors()
                request.info_messages = request.rpsl_obj.messages.infos()

            except UnknownRPSLObjectClassException as exc:
                request.status = UpdateRequestStatus.ERROR_UNKNOWN_CLASS
                request.error_messages.append(str(exc))

            results.append(request)

        for result in results:
            result.passwords = passwords
            result.overrides = overrides
        return results
