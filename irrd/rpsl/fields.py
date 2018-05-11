import re
from typing import List, Type, Optional

from IPy import IP, _checkNetaddrWorksWithPrefixlen

from .config import PASSWORD_HASHERS
from .validators import clean_as_number, RPSLParserMessages

# The IPv4/IPv6 regexes are for initial screening - not full validators
re_ipv4_prefix = re.compile(r"^\d+\.\d+\.\d+\.\d+/\d+$")
re_ipv6_prefix = re.compile(r"^[A-F\d:]+/\d+$", re.IGNORECASE)

# This regex is not designed to catch every possible invalid variation,
# but rather meant to protect against unintentional mistakes.
#                         # Validate local-part           @ domain         | or IPv4 address        | or IPv6
re_email = re.compile(r"^[A-Z0-9$!#%&\"*+\/=?^_`{|}~\\.-]+@(([A-Z0-9\\.-]+)|(\[\d+\.\d+\.\d+\.\d+\])|(\[[A-f\d:]+\]))$", re.IGNORECASE)

re_pgpkey = re.compile(r"^PGPKEY-[A-F0-9]{8}$")
re_dnsname = re.compile(r"^(([A-Z0-9]|[A-Z0-9][A-Z0-9\-]*[A-Z0-9])\.)*([A-Z0-9]|[A-Z0-9][A-Z0-9\-]*[A-Z0-9])$", re.IGNORECASE)
re_generic_name = re.compile(r"^[A-Z][A-Z0-9_-]*[A-Z0-9]$", re.IGNORECASE)
reserved_words = ["ANY", "AS-ANY", "RS_ANY", "PEERAS", "AND", "OR", "NOT", "ATOMIC", "FROM", "TO", "AT", "ACTION",
                  "ACCEPT", "ANNOUNCE", "EXCEPT", "REFINE", "NETWORKS", "INTO", "INBOUND", "OUTBOUND"]
reserved_prefixes = ["AS-", "RS-", "RTRS-", "FLTR-", "PRNG-"]


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

    Note that clean() can expect data to be stripped from whitespaces and comments, and multiple
    lines be joined by commas. It should add any info, error or warning messages to the passed
    messages object, and return a cleaned version of the value. If it is not possible to extract
    a value, e.g. due to a validation error, it should return None.
    """
    def __init__(self, optional: bool=False, multiple: bool=False, primary_key: bool=False, lookup_key: bool=False) -> None:
        self.optional = optional
        self.multiple = multiple
        self.primary_key = primary_key
        self.lookup_key = lookup_key

    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        return value


class RPSLFieldListMixin:
    """fl
    Mixin to allow fields to support list values, like "AS1, AS2, AS3".

    For example, if you have an RPSLASNumberField that validates a single
    AS number, you can create RPSLASNumbersField that allows a list of
    AS numbers by creating:

        class RPSLASNumbersField(RPSLFieldListMixin, RPSLASNumberField):
            pass
    """
    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        values = []
        for single_value in value.split(","):
            value = super().clean(single_value.strip(), messages)  # type: ignore
            values.append(value)
        if not all(values):
            return None
        return ",".join(values)


class RPSLIPv4PrefixField(RPSLTextField):
    """Field for a single IPv4 prefix."""
    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        if not re_ipv4_prefix.match(value):
            messages.error(f"Invalid address prefix: {value}")
            return None

        ip_str, length = value.split("/")
        try:
            ip = IP(ip_str)
            if not _checkNetaddrWorksWithPrefixlen(ip.ip, int(length), 4):
                messages.error(f"Invalid prefix length in address prefix: {value}")
                return None
        except ValueError as ve:
            messages.error(f"Invalid address prefix: {value}: {ve}")
            return None

        cleaned_ip_str = str(ip) + "/" + str(int(length))
        if cleaned_ip_str != value:
            messages.info(f"Address prefix {value} was reformatted as {cleaned_ip_str}")
        return cleaned_ip_str


class RPSLIPv4PrefixesField(RPSLFieldListMixin, RPSLIPv4PrefixField):
    """Field for a comma-separated list of IPv4 prefixes."""
    pass


class RPSLIPv6PrefixField(RPSLTextField):
    """Field for a single IPv6 prefix."""
    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        if not re_ipv6_prefix.match(value):
            messages.error(f"Invalid address prefix: {value}")
            return None

        ip_str, length = value.split("/")
        try:
            ip = IP(ip_str)
            if not _checkNetaddrWorksWithPrefixlen(ip.ip, int(length), 6):
                messages.error(f"Invalid prefix length in address prefix: {value}")
                return None
        except ValueError as ve:
            messages.error(f"Invalid address prefix: {value}: {ve}")
            return None

        cleaned_ip_str = str(ip) + "/" + str(int(length))
        if cleaned_ip_str != value:
            messages.info(f"Address prefix {value} was reformatted as {cleaned_ip_str}")
        return cleaned_ip_str


class RPSLIPv6PrefixesField(RPSLFieldListMixin, RPSLIPv6PrefixField):
    """Field for a comma-separated list of IPv6 prefixes."""
    pass


class RPSLIPv4AddressRangeField(RPSLTextField):
    """
    Field for a range of IPv4 addresses, as used in inetnum keys.

    Note that a single IP address is also valid, and that the range does
    not have to align to bitwise boundaries of prefixes.
    """
    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        if "-" in value:
            ip1_input, ip2_input = value.split("-", 1)
        else:
            ip1_input = ip2_input = value

        try:
            ip1 = IP(ip1_input)
            ip2 = IP(ip2_input)
        except ValueError as ve:
            messages.error(f"Invalid address range: {value}: {ve}")
            return None

        if not ip1.version() == ip2.version() == 4:
            messages.error(f"Invalid address range: {value}: IP version mismatch")
            return None
        if ip1.int() > ip2.int():
            messages.error(f"Invalid address range: {value}: first IP is higher than second IP")
            return None

        if "-" in value:
            cleaned_value = f"{ip1} - {ip2}"
        else:
            cleaned_value = str(ip1)
        if cleaned_value != value:
            messages.info(f"Address range {value} was reformatted as {cleaned_value}")
        return cleaned_value


class RPSLASNumberField(RPSLTextField):
    """Field for a single AS number (in ASxxxx syntax)."""
    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        cleaned_value = clean_as_number(value, messages)
        if cleaned_value and cleaned_value.upper() != value.upper():
            messages.info(f"AS number {value} was reformatted as {cleaned_value}")
        return cleaned_value


class RPSLASBlockField(RPSLTextField):
    """Field for a block of AS numbers, e.g. AS1 - AS5."""
    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        if "-" not in value:
            messages.error(f"Invalid AS range: {value}: does not contain a hyphen")
            return None

        as1_raw, as2_raw = map(str.strip, value.split("-", 1))

        as1 = clean_as_number(as1_raw, messages)
        as2 = clean_as_number(as2_raw, messages)

        if not all([as1, as2]):
            return None  # Messages about the reason for validation failure were already added.

        if int(as1[2:]) > int(as2[2:]):  # type: ignore
            messages.error(f"Invalid AS range: {value}: first AS is higher then second AS")
            return None

        cleaned_value = f"{as1} - {as2}"
        if cleaned_value != value:
            messages.info(f"AS range {value} was reformatted as {cleaned_value}")
        return cleaned_value


class RPSLSetNameField(RPSLTextField):
    """
    Field for set names, i.e. names of objects like route-set, prefix-set, etc.

    The actual set name must start with a designated prefix (which is otherwise not
    permitted for RPSL names).
    Set names can consist of multiple components, e.g. AS23456:RS-FOO. Each
    component must be a valid set name or valid AS number, and one component
    must be a valid set name, i.e. start with the given prefix.

    The prefix provided is the expected prefix of the set name, e.g. "RS" for
    a route-set, or "AS" for an as-set.
    """
    def __init__(self, prefix: str, *args, **kwargs) -> None:
        self.prefix = prefix + "-"
        super().__init__(*args, **kwargs)

    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        assert self.prefix in reserved_prefixes
        input_components = value.split(":")
        output_components: List[str] = []

        if not any([c.upper().startswith(self.prefix) for c in input_components]):
            messages.error(f"Invalid set name {value}: at least one component must be "
                           f"an actual set name (i.e. start with {self.prefix})")
            return None
        for component in input_components:
            if component.upper() in reserved_words:
                messages.error(f"Invalid set name {value}: component {component} is a reserved word")
                return None

            # clean_as_number receives a new message object instance, as we want to ignore the message
            # it produces - we want to create our own message later if validation fails.
            cleaned_as_number = clean_as_number(component, RPSLParserMessages())
            if not component.upper().startswith(self.prefix) and not cleaned_as_number:
                messages.error(
                    f"Invalid set {value}: component {component} is not a valid AS number nor a valid set name"
                )
                return None

            if cleaned_as_number:
                output_components.append(cleaned_as_number)
            else:
                output_components.append(component)

        cleaned_value = ":".join(output_components)
        if cleaned_value != value:
            messages.info(f"Set name {value} was reformatted as {cleaned_value}")
        return cleaned_value


class RPSLEmailField(RPSLTextField):
    """Field for an e-mail address. Only performs basic validation."""
    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        if not re_email.match(value):
            messages.error(f"Invalid e-mail address: {value}")
            return None
        return value


class RPSLDNSNameField(RPSLTextField):
    """Field for a DNS name, as used in e.g. inet-rtr names."""
    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        if not re_dnsname.match(value):
            messages.error(f"Invalid DNS name: {value}")
            return None
        return value


class RPSLGenericNameField(RPSLTextField):
    """
    Field for a generic name.

    Generic names are names of objects that do not have a more strict definition,
    such as the nic-hdl of a person.
    Optionally, a list of allowed reserved prefixes can be provided.
    For example, this is used for the as-name attribute of an aut-num, as they
    are allowed to start with "AS".
    """
    def __init__(self, allowed_prefixes: List[str]=None, *args, **kwargs) -> None:
        if allowed_prefixes:
            self.allowed_prefixes = [prefix.upper() + "-" for prefix in allowed_prefixes]
        else:
            self.allowed_prefixes = []
        super().__init__(*args, **kwargs)

    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        upper_value = value.upper()
        if upper_value in reserved_words:
            messages.error(f"Invalid name: {value}: this is a reserved word")
            return None

        for prefix in reserved_prefixes:
            if upper_value.startswith(prefix) and prefix not in self.allowed_prefixes:
                messages.error(f"Invalid name: {value}: {prefix} is a reserved prefix")
                return None

        if not re_generic_name.match(upper_value):
            messages.error(f"Invalid name: {value}: contains invalid characters, does not start with a letter, "
                           f"or does not end in a letter/digit")
            return None
        return value


class RPSLReferenceField(RPSLTextField):
    """
    Field for a reference to another field.

    Example: the mntner field in a person object, refers to the primary key
    field of the mntner object. Upon validating a person:mntner value, this
    field will instead run the validator of mntner:mntner.

    The list of referred objects can contain multiple entries, which means that
    the value must refer to one of these objects (e.g. tech-c can refer to
    role or person).
    """
    def __init__(self, referring: List[str], *args, **kwargs) -> None:
        from .parser import RPSLObject
        self.referring = referring
        self.referring_object_classes: List[Type[RPSLObject]] = []
        self.referring_identifier_fields: List[RPSLTextField] = []
        super().__init__(*args, **kwargs)

    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        if not self.referring_identifier_fields:
            self._build_cache()

        referring_field_messages = RPSLParserMessages()
        for identifier_field in self.referring_identifier_fields:
            if identifier_field:
                cleaned_value = identifier_field.clean(value, referring_field_messages)
                if cleaned_value is not None:
                    return cleaned_value

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

    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        if self.allow_kw_any and value.upper() == "ANY":
            return "ANY"
        return super().clean(value, messages)


class RPSLAuthField(RPSLTextField):
    """Field for the auth attribute of a mntner."""
    def clean(self, value: str, messages: RPSLParserMessages) -> Optional[str]:
        valid_beginnings = [hasher + " " for hasher in PASSWORD_HASHERS.keys()]
        if any(value.upper().startswith(b) for b in valid_beginnings) or re_pgpkey.match(value.upper()):
            return value

        hashers = ", ".join(PASSWORD_HASHERS.keys())
        messages.error(f"Invalid auth attribute: {value}: supported options are {hashers} and PGPKEY-xxxxxxxx")
        return None
