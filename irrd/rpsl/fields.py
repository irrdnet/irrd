import datetime
import re
from typing import List, Type, Optional

from IPy import IP

from .config import PASSWORD_HASHERS
from .parser_state import RPSLParserMessages, RPSLFieldParseResult
from irrd.utils.validators import parse_as_number, ValidationError

# The IPv4/IPv6 regexes are for initial screening - not full validators
re_ipv4_prefix = re.compile(r"^\d+\.\d+\.\d+\.\d+/\d+$")
re_ipv6_prefix = re.compile(r"^[A-F\d:]+/\d+$", re.IGNORECASE)

# This regex is not designed to catch every possible invalid variation,
# but rather meant to protect against unintentional mistakes.
#                         # Validate local-part           @ domain         | or IPv4 address        | or IPv6
re_email = re.compile(r"^[A-Z0-9$!#%&\"*+\/=?^_`{|}~\\.-]+@(([A-Z0-9\\.-]+)|(\[\d+\.\d+\.\d+\.\d+\])|(\[[A-f\d:]+\]))$", re.IGNORECASE)

re_range_operator = re.compile(r"^((\d{1,3}-\d{1,3})|(-)|(\+)|(\d{1,3}))$")
re_pgpkey = re.compile(r"^PGPKEY-[A-F0-9]{8}$")
re_dnsname = re.compile(r"^(([A-Z0-9]|[A-Z0-9][A-Z0-9\-]*[A-Z0-9])\.)*([A-Z0-9]|[A-Z0-9][A-Z0-9\-]*[A-Z0-9])$", re.IGNORECASE)
re_generic_name = re.compile(r"^[A-Z][A-Z0-9_-]*[A-Z0-9]$", re.IGNORECASE)
reserved_words = ["ANY", "AS-ANY", "RS_ANY", "PEERAS", "AND", "OR", "NOT", "ATOMIC", "FROM", "TO", "AT", "ACTION",
                  "ACCEPT", "ANNOUNCE", "EXCEPT", "REFINE", "NETWORKS", "INTO", "INBOUND", "OUTBOUND"]
reserved_prefixes = ["AS-", "RS-", "RTRS-", "FLTR-", "PRNG-"]

# Turn "IP('193.0.1.1/21') has invalid prefix length (21)" into "invalid prefix length (21)"
re_clean_ip_error = re.compile(r"IP\('[A-F0-9:./]+'\) has ", re.IGNORECASE)

"""
Fields for RPSL data.

Note that these objects are instantiated once per attribute during RPSL object
class loading. Therefore, the instances will be shared between different RPSL
objects. In other words, two role object's nic-hdl fields will use the same
instance of RPSLGenericNameField. Never store object-specific state in self
in any field instances.
"""


class RPSLTextField:
    """
    Base field class for simple RPSL text fields. All other fields should inherit from this class.

    Note that parse() can expect data to be stripped from whitespaces and comments, and multiple
    lines be joined by commas. It should add any info, error or warning messages to the passed
    messages object, and return a parsed version of the value. If it is not possible to extract
    a value, e.g. due to a validation error, it should return None.

    The keep_case property affects the generation of RPSLObject.parsed_data during parsing.
    If keep_case is False, all data is converted to upper case. The original object text is not
    modified for this. As parsed_data is indexed in the databases, this is important for searches,
    to match e.g. 'mntner: FOO' to 'mnt-by: foo' - as these values are equivalent.
    """
    keep_case = True

    def __init__(self, optional: bool=False, multiple: bool=False, primary_key: bool=False, lookup_key: bool=False) -> None:
        self.optional = optional
        self.multiple = multiple
        self.primary_key = primary_key
        self.lookup_key = lookup_key

    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        return RPSLFieldParseResult(value)


class RPSLFieldListMixin:
    """
    Mixin to allow fields to support list values, like 'AS1, AS2, AS3'.

    For example, if you have an RPSLASNumberField that validates a single
    AS number, you can create RPSLASNumbersField that allows a list of
    AS numbers by creating:

        class RPSLASNumbersField(RPSLFieldListMixin, RPSLASNumberField):
            pass
    """
    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        parse_results = []
        for single_value in value.split(','):
            single_value = single_value.strip()
            if single_value:
                parse_result = super().parse(single_value, messages, strict_validation)  # type: ignore
                parse_results.append(parse_result)
        if not all(parse_results):
            return None
        values = [result.value for result in parse_results]
        return RPSLFieldParseResult(','.join(values), values_list=values)


class RPSLIPv4PrefixField(RPSLTextField):
    """Field for a single IPv4 prefix."""
    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        if not re_ipv4_prefix.match(value):
            messages.error(f'Invalid address prefix: {value}')
            return None

        try:
            ip = IP(value, ipversion=4)
        except ValueError as ve:
            clean_error = clean_ip_value_error(ve)
            messages.error(f'Invalid address prefix: {value}: {clean_error}')
            return None

        parsed_ip_str = str(ip)
        if ip.prefixlen() == 32:
            parsed_ip_str += '/32'
        if parsed_ip_str != value:
            messages.info(f'Address prefix {value} was reformatted as {parsed_ip_str}')
        return RPSLFieldParseResult(parsed_ip_str, ip_first=ip.net(), ip_last=ip.broadcast(),
                                    prefix=ip, prefix_length=ip.prefixlen())


class RPSLIPv4PrefixesField(RPSLFieldListMixin, RPSLIPv4PrefixField):
    """Field for a comma-separated list of IPv4 prefixes."""
    pass


class RPSLIPv6PrefixField(RPSLTextField):
    """Field for a single IPv6 prefix."""
    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        if not re_ipv6_prefix.match(value):
            messages.error(f'Invalid address prefix: {value}')
            return None

        try:
            ip = IP(value, ipversion=6)
        except ValueError as ve:
            clean_error = clean_ip_value_error(ve)
            messages.error(f'Invalid address prefix: {value}: {clean_error}')
            return None

        parsed_ip_str = str(ip)
        if ip.prefixlen() == 128:
            parsed_ip_str += '/128'
        if parsed_ip_str != value:
            messages.info(f'Address prefix {value} was reformatted as {parsed_ip_str}')
        return RPSLFieldParseResult(parsed_ip_str, ip_first=ip.net(), ip_last=ip.broadcast(),
                                    prefix=ip, prefix_length=ip.prefixlen())


class RPSLIPv6PrefixesField(RPSLFieldListMixin, RPSLIPv6PrefixField):
    """Field for a comma-separated list of IPv6 prefixes."""
    pass


class RPSLIPv4AddressRangeField(RPSLTextField):
    """
    Field for a range of IPv4 addresses, as used in inetnum keys.

    Note that a single IP address is also valid, and that the range does
    not have to align to bitwise boundaries of prefixes.
    """
    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        value = value.replace(',', '')  # #311, process multiline PK correctly
        if '-' in value:
            ip1_input, ip2_input = value.split('-', 1)
        else:
            ip1_input = ip2_input = value

        try:
            ip1 = IP(ip1_input)
            ip2 = IP(ip2_input)
        except ValueError as ve:
            clean_error = clean_ip_value_error(ve)
            messages.error(f'Invalid address range: {value}: {clean_error}')
            return None

        if not ip1.version() == ip2.version() == 4:
            messages.error(f'Invalid address range: {value}: IP version mismatch')
            return None
        if ip1.int() > ip2.int():
            messages.error(f'Invalid address range: {value}: first IP is higher than second IP')
            return None

        if '-' in value:
            parsed_value = f'{ip1} - {ip2}'
        else:
            parsed_value = str(ip1)
        if parsed_value != value:
            messages.info(f'Address range {value} was reformatted as {parsed_value}')
        return RPSLFieldParseResult(parsed_value, ip_first=ip1, ip_last=ip2)


class RPSLRouteSetMemberField(RPSLTextField):
    """
    Field for the members of a route-set. These can be:
        - A valid name for another route set.
        - A valid IPv4 or IPv6 (depending on ip_version) prefix
        - A valid prefix followed by:
          - ^-
          - ^+
          - ^[integer]
          - ^[integer]-[integer]
    """
    keep_case = True

    def __init__(self, ip_version: Optional[int], *args, **kwargs) -> None:
        if ip_version and ip_version not in [4, 6]:
            raise ValueError(f'Invalid IP version: {ip_version}')
        self.ip_version = ip_version
        super().__init__(*args, **kwargs)

    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        if '^' in value:
            address, range_operator = value.split('^', maxsplit=1)
            if not range_operator:
                messages.error(f'Missing range operator in value: {value}')
                return None
        else:
            address = value
            range_operator = ''

        parse_set_result_messages = RPSLParserMessages()
        parse_set_result = parse_set_name(['RS-', 'AS-'], address, parse_set_result_messages, strict_validation)
        if parse_set_result and not parse_set_result_messages.errors():
            result_value = parse_set_result.value
            if range_operator:
                result_value += '^' + range_operator
            if result_value != value:
                messages.info(f'Route set member {value} was reformatted as {result_value}')
            return RPSLFieldParseResult(value=result_value)
        try:
            parsed_str, parsed_int = parse_as_number(address)
            result_value = parsed_str
            if range_operator:
                result_value += '^' + range_operator
            if result_value != value:
                messages.info(f'Route set member {value} was reformatted as {result_value}')
            return RPSLFieldParseResult(value=result_value)
        except ValidationError:
            pass

        try:
            ip_version = self.ip_version if self.ip_version else 0
            ip = IP(address, ipversion=ip_version)
        except ValueError as ve:
            clean_error = clean_ip_value_error(ve)
            messages.error(f'Value is neither a valid set name nor a valid prefix: {address}: {clean_error}')
            return None

        if range_operator and not re_range_operator.match(range_operator):
            messages.error(f'Invalid range operator {range_operator} in value: {value}')
            return None

        parsed_ip_str = str(ip)
        if ip.version() == 4 and ip.prefixlen() == 32:
            parsed_ip_str += '/32'
        if ip.version() == 6 and ip.prefixlen() == 128:
            parsed_ip_str += '/128'
        if range_operator:
            parsed_ip_str += '^' + range_operator

        if parsed_ip_str != value:
            messages.info(f'Route set member {value} was reformatted as {parsed_ip_str}')
        return RPSLFieldParseResult(parsed_ip_str)


class RPSLRouteSetMembersField(RPSLFieldListMixin, RPSLRouteSetMemberField):
    pass


class RPSLASNumberField(RPSLTextField):
    """Field for a single AS number (in ASxxxx syntax)."""
    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        try:
            parsed_str, parsed_int = parse_as_number(value)
        except ValidationError as ve:
            messages.error(str(ve))
            return None
        if parsed_str and parsed_str.upper() != value.upper():
            messages.info(f'AS number {value} was reformatted as {parsed_str}')
        return RPSLFieldParseResult(parsed_str, asn_first=parsed_int, asn_last=parsed_int)


class RPSLASBlockField(RPSLTextField):
    """Field for a block of AS numbers, e.g. AS1 - AS5."""
    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        if '-' not in value:
            messages.error(f'Invalid AS range: {value}: does not contain a hyphen')
            return None

        as1_raw, as2_raw = map(str.strip, value.split('-', 1))

        try:
            as1_str, as1_int = parse_as_number(as1_raw)
            as2_str, as2_int = parse_as_number(as2_raw)
        except ValidationError as ve:
            messages.error(str(ve))
            return None

        if as1_int > as2_int:  # type: ignore
            messages.error(f'Invalid AS range: {value}: first AS is higher then second AS')
            return None

        parsed_value = f'{as1_str} - {as2_str}'
        if parsed_value != value:
            messages.info(f'AS range {value} was reformatted as {parsed_value}')
        return RPSLFieldParseResult(parsed_value, asn_first=as1_int, asn_last=as2_int)


class RPSLSetNameField(RPSLTextField):
    """
    Field for set names, i.e. names of objects like route-set, prefix-set, etc.

    The actual set name must start with a designated prefix (which is otherwise not
    permitted for RPSL names).
    Set names can consist of multiple components, e.g. AS65537:RS-FOO. Each
    component must be a valid set name or valid AS number, and one component
    must be a valid set name for this specific set, i.e. start with the given prefix.

    The prefix provided is the expected prefix of the set name, e.g. 'RS' for
    a route-set, or 'AS' for an as-set.R
    """
    keep_case = False

    def __init__(self, prefix: str, *args, **kwargs) -> None:
        self.prefix = prefix + '-'
        super().__init__(*args, **kwargs)

    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        return parse_set_name([self.prefix], value, messages, strict_validation)


class RPSLEmailField(RPSLTextField):
    """Field for an e-mail address. Only performs basic validation."""
    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        if not re_email.match(value):
            messages.error(f'Invalid e-mail address: {value}')
            return None
        return RPSLFieldParseResult(value)


class RPSLChangedField(RPSLTextField):
    """Field for an changed line. Only performs basic validation for email."""
    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        date: Optional[str]
        try:
            email, date = value.split(' ')
        except ValueError:
            email = value
            date = None

        if not re_email.match(email):
            messages.error(f'Invalid e-mail address: {email}')
            return None
        if date:
            try:
                datetime.datetime.strptime(date, '%Y%m%d')
            except ValueError as ve:
                messages.error(f'Invalid changed date: {date}: {ve}')
                return None
        return RPSLFieldParseResult(value)


class RPSLDNSNameField(RPSLTextField):
    """Field for a DNS name, as used in e.g. inet-rtr names."""
    keep_case = False

    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        if not re_dnsname.match(value):
            messages.error(f'Invalid DNS name: {value}')
            return None
        return RPSLFieldParseResult(value)


class RPSLGenericNameField(RPSLTextField):
    """
    Field for a generic name.

    Generic names are names of objects that do not have a more strict definition,
    such as the nic-hdl of a person.
    Optionally, a list of allowed reserved prefixes can be provided.
    For example, this is used for the as-name attribute of an aut-num, as they
    are allowed to start with 'AS'.

    If non_strict_allow_any is set, the parser will allow any value if strict_validation
    is disabled. This is needed on nic-hdl for legacy reasons -
    see https://github.com/irrdnet/irrd/issues/60
    """
    keep_case = False

    def __init__(self, allowed_prefixes: List[str]=None, non_strict_allow_any=False, *args, **kwargs) -> None:
        self.non_strict_allow_any = non_strict_allow_any
        if allowed_prefixes:
            self.allowed_prefixes = [prefix.upper() + '-' for prefix in allowed_prefixes]
        else:
            self.allowed_prefixes = []
        super().__init__(*args, **kwargs)

    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        if not strict_validation and self.non_strict_allow_any:
            return RPSLFieldParseResult(value)

        upper_value = value.upper()
        if strict_validation:
            if upper_value in reserved_words:
                messages.error(f'Invalid name: {value}: this is a reserved word')
                return None

            for prefix in reserved_prefixes:
                if upper_value.startswith(prefix) and prefix not in self.allowed_prefixes:
                    messages.error(f'Invalid name: {value}: {prefix} is a reserved prefix')
                    return None

        if not re_generic_name.match(upper_value):
            messages.error(f'Invalid name: {value}: contains invalid characters, does not start with a letter, '
                           f'or does not end in a letter/digit')
            return None
        return RPSLFieldParseResult(value)


class RPSLReferenceField(RPSLTextField):
    """
    Field for a reference to another field.

    Example: the mntner field in a person object, refers to the primary key
    field of the mntner object. Upon validating a person:mntner value, this
    field will instead run the validator of mntner:mntner.

    The list of referred objects can contain multiple entries, which means that
    the value must refer to one of these objects (e.g. tech-c can refer to
    role or person).

    If the references are strong, this reference is included in reference checks
    on updates, i.e. adding an object with a strong reference to another object
    that does not exist, is a validation failure.
    """
    keep_case = False

    def __init__(self, referring: List[str], strong=True, *args, **kwargs) -> None:
        from .parser import RPSLObject
        self.referring = referring
        self.strong = strong
        self.referring_object_classes: List[Type[RPSLObject]] = []
        self.referring_identifier_fields: List[RPSLTextField] = []
        super().__init__(*args, **kwargs)

    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        if not self.referring_identifier_fields:
            self._build_cache()

        referring_field_messages = RPSLParserMessages()
        for identifier_field in self.referring_identifier_fields:
            if identifier_field:
                parsed_value = identifier_field.parse(value, referring_field_messages, strict_validation)
                if parsed_value is not None:
                    return parsed_value

        messages.merge_messages(referring_field_messages)
        return None

    def _build_cache(self):
        from .rpsl_objects import OBJECT_CLASS_MAPPING
        for ref in self.referring:
            rpsl_object_class = OBJECT_CLASS_MAPPING[ref]
            pk_field = [field for field in rpsl_object_class.fields.values() if field.primary_key and field.lookup_key][0]
            self.referring_object_classes.append(rpsl_object_class)
            self.referring_identifier_fields.append(pk_field)


class RPSLReferenceListField(RPSLFieldListMixin, RPSLReferenceField):
    """
    Field for a comma-seperated list of references to another field.

    Optionally, ANY can be allowed as a valid option too, instead of a list.
    """
    def __init__(self, allow_kw_any: bool=False, *args, **kwargs) -> None:
        self.allow_kw_any = allow_kw_any
        super().__init__(*args, **kwargs)

    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        if self.allow_kw_any and value.upper() == 'ANY':
            return RPSLFieldParseResult('ANY', values_list=['ANY'])
        return super().parse(value, messages, strict_validation)


class RPSLAuthField(RPSLTextField):
    """Field for the auth attribute of a mntner."""
    def parse(self, value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
        valid_beginnings = [hasher + ' ' for hasher in PASSWORD_HASHERS.keys()]
        has_valid_beginning = any(value.upper().startswith(b) for b in valid_beginnings)
        is_valid_hash = has_valid_beginning and value.count(' ') == 1 and not value.count(',')
        if is_valid_hash or re_pgpkey.match(value.upper()):
            return RPSLFieldParseResult(value)

        hashers = ', '.join(PASSWORD_HASHERS.keys())
        messages.error(f'Invalid auth attribute: {value}: supported options are {hashers} and PGPKEY-xxxxxxxx')
        return None


def parse_set_name(prefixes: List[str], value: str, messages: RPSLParserMessages, strict_validation=True) -> Optional[RPSLFieldParseResult]:
    assert all([prefix in reserved_prefixes for prefix in prefixes])
    input_components = value.split(':')
    output_components: List[str] = []
    prefix_display = '/'.join(prefixes)

    if strict_validation and len(input_components) > 5:
        messages.error('Set names can have a maximum of five components.')
        return None

    if strict_validation and not any([c.upper().startswith(tuple(prefixes)) for c in input_components]):
        messages.error(f'Invalid set name {value}: at least one component must be '
                       f'an actual set name (i.e. start with {prefix_display})')
        return None

    for component in input_components:
        if strict_validation and component.upper() in reserved_words:
            messages.error(f'Invalid set name {value}: component {component} is a reserved word')
            return None

        parsed_as_number = None
        try:
            parsed_as_number, _ = parse_as_number(component)
        except ValidationError:
            pass
        if not re_generic_name.match(component.upper()) and not parsed_as_number:
            messages.error(
                f'Invalid set {value}: component {component} is not a valid AS number nor a valid set name'
            )
            return None
        if strict_validation and not parsed_as_number and not component.upper().startswith(tuple(prefixes)):
            messages.error(f'Invalid set {value}: component {component} is not a valid AS number, '
                           f'nor does it start with {prefix_display}')
            return None

        if parsed_as_number:
            output_components.append(parsed_as_number)
        else:
            output_components.append(component)

    parsed_value = ':'.join(output_components)
    if parsed_value != value:
        messages.info(f'Set name {value} was reformatted as {parsed_value}')
    return RPSLFieldParseResult(parsed_value)


def clean_ip_value_error(value_error):
    return re.sub(re_clean_ip_error, '', str(value_error))
