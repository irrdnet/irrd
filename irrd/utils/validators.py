from typing import Tuple, List, Union, Optional

import pydantic


def parse_as_number(value: str) -> Tuple[str, int]:
    """Validate and clean an AS number. Returns it in ASxxxx and numeric format."""
    value = value.upper()
    if not value.startswith('AS'):
        raise ValidationError(f'Invalid AS number {value}: must start with "AS"')

    if not value[2:].isnumeric():
        raise ValidationError(f'Invalid AS number {value}: number part is not numeric')

    value_int = int(value[2:])
    if value_int > 4294967295:
        raise ValidationError(f'Invalid AS number {value}: maximum value is 4294967295')

    return 'AS' + str(value_int), value_int


class ValidationError(ValueError):
    pass


class RPSLChangeSubmissionObjectAttribute(pydantic.main.BaseModel):
    """
    Model for a single name/value pair of an RPSL attribute
    in an object in an RPSL change submission
    """
    name: str
    value: Union[str, List[str]]

    @pydantic.validator('value')
    def translate_list_to_str(cls, value):  # noqa: N805
        """Translate lists to RPSL-compatible strings"""
        if not isinstance(value, str):
            return ', '.join(value)
        return value


class RPSLChangeSubmissionObject(pydantic.main.BaseModel):
    """Model for a single object in an RPSL change submission"""
    object_text: Optional[str]
    attributes: Optional[List[RPSLChangeSubmissionObjectAttribute]]

    @pydantic.root_validator(pre=True)
    def check_text_xor_attributes_present(cls, values):  # noqa: N805
        if bool(values.get('object_text')) == bool(values.get('attributes')):
            raise ValueError('You must describe each object with either '
                             '"object_text" or "attributes"')
        return values


class RPSLChangeSubmission(pydantic.main.BaseModel):
    """Model for an RPSL change submission"""
    objects: List[RPSLChangeSubmissionObject]
    passwords: List[str] = []
    override: Optional[str]
    delete_reason: str = '(No reason provided)'
