from typing import Tuple, List, Union, Optional

import pydantic


def parse_as_number(value: Union[str, int], permit_plain=False) -> Tuple[str, int]:
    """Validate and clean an AS number. Returns it in ASxxxx and numeric format."""
    if isinstance(value, str):
        value = value.upper()
        if not permit_plain and not value.startswith('AS'):
            raise ValidationError(f'Invalid AS number {value}: must start with "AS"')

        start_index = 2 if value.startswith('AS') else 0

        if not value[start_index:].isnumeric():
            raise ValidationError(f'Invalid AS number {value}: number part is not numeric')

        value_int = int(value[start_index:])
    else:
        value_int = value

    if not 0 <= value_int <= 4294967295:
        raise ValidationError(f'Invalid AS number {value}: valid range is 0-4294967295')

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
