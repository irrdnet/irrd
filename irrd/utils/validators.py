from typing import Tuple, Union


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
