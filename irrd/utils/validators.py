from typing import Tuple


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
