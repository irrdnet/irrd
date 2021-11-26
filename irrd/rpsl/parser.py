import datetime
import itertools
import json
import re
from collections import OrderedDict, Counter
from typing import Dict, List, Optional, Tuple, Any, Set

from IPy import IP

from irrd.rpki.status import RPKIStatus
from irrd.rpsl.parser_state import RPSLParserMessages
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.utils.text import splitline_unicodesafe
from .fields import RPSLTextField
from ..conf import get_setting

RPSL_ATTRIBUTE_TEXT_WIDTH = 16
TypeRPSLObjectData = List[Tuple[str, str, List[str]]]


class RPSLObjectMeta(type):
    """
    Meta class for RPSLObject (and all subclasses) for performance enhancement.

    As RPSLObject is instantiated once per object parsed, __init__ should be
    kept as small as possible. This metaclass pre-calculates some derived data
    from the fields defined by a subclass of RPSLObject, for optimised parsing speed.
    """
    def __init__(cls, name, bases, clsdict):  # noqa: N805
        super().__init__(name, bases, clsdict)
        fields = clsdict.get('fields')
        if fields:
            cls.rpsl_object_class = list(fields.keys())[0]
            cls.pk_fields = [field[0] for field in fields.items() if field[1].primary_key]
            cls.lookup_fields = [field[0] for field in fields.items() if field[1].lookup_key]
            cls.attrs_allowed = [field[0] for field in fields.items()]
            cls.attrs_required = [field[0] for field in fields.items() if not field[1].optional]
            cls.attrs_multiple = [field[0] for field in fields.items() if field[1].multiple]
            cls.field_extracts = list(itertools.chain(
                *[field[1].extracts for field in fields.items() if field[1].primary_key or field[1].lookup_key]
            ))
            cls.referring_strong_fields = [(field[0], field[1].referring) for field in fields.items() if hasattr(field[1], 'referring') and getattr(field[1], 'strong')]


class RPSLObject(metaclass=RPSLObjectMeta):
    """
    Base class for RPSL objects.

    To clean an RPSL object in string form, the best option is not to instance
    this or a subclass, but instead call rpsl_object_from_text() which
    automatically derives the correct class.

    This class should not be instanced directly - instead subclasses should be
    made for each RPSL type with the appropriate fields defined. Note that any
    subclasses should also be added to OBJECT_CLASS_MAPPING.
    """
    fields: Dict[str, RPSLTextField] = OrderedDict()
    rpsl_object_class: str
    pk_fields: List[str] = []
    attrs_allowed: List[str] = []
    attrs_required: List[str] = []
    attrs_multiple: List[str] = []
    ip_first: IP = None
    ip_last: IP = None
    asn_first: Optional[int] = None
    asn_last: Optional[int] = None
    prefix: IP = None
    prefix_length: Optional[int] = None
    rpki_status: RPKIStatus = RPKIStatus.not_found
    scopefilter_status: ScopeFilterStatus = ScopeFilterStatus.in_scope
    default_source: Optional[str] = None  # noqa: E704 (flake8 bug)
    # Whether this object has a relation to RPKI ROA data, and therefore RPKI
    # checks should be performed in certain scenarios. Enabled for route/route6.
    rpki_relevant = False
    # Fields whose values are discarded during parsing
    discarded_fields: List[str] = []
    # Fields that are ignored in validation even
    # for authoritative objects (see #587 for example).
    ignored_validation_fields: List[str] = ['last-modified']

    _re_attr_name = re.compile(r'^[a-z0-9_-]+$')

    def __init__(self, from_text: Optional[str]=None, strict_validation=True, default_source=None) -> None:
        """
        Create a new RPSL object, optionally instantiated from a string.

        Optionally, you can set/unset strict validation. This means all
        attribute values are validated, and attribute presence/absence is
        verified. Non-strict validation is limited to primary and lookup
        keys.

        If you set default_source, and strict_validation is False, the
        parser will accept objects without a source attribute, and treat
        them as if their source was default_source.
        """
        self.messages = RPSLParserMessages()
        self._object_data: TypeRPSLObjectData = []
        self.strict_validation = strict_validation
        if default_source:
            self.default_source = default_source.strip().upper()

        if from_text:
            self._extract_attributes_values(from_text)
            self._validate_object()

    def pk(self) -> str:
        """Get the primary key value of an RPSL object. The PK is always converted to uppercase."""
        if len(self.pk_fields) == 1:
            return self.parsed_data.get(self.pk_fields[0], "").upper()
        composite_values = []
        for field in self.pk_fields:
            composite_values.append(self.parsed_data.get(field, ""))
        return ''.join(composite_values).upper()

    def source(self) -> str:
        """Shortcut to retrieve object source"""
        try:
            return self.parsed_data['source']
        except KeyError:
            raise ValueError('RPSL object has no known source')

    def ip_version(self) -> Optional[int]:
        """
        Get the IP version to which this object relates, or None for
        e.g. person or as-block objects.
        """
        if self.ip_first:
            return self.ip_first.version()
        return None

    def referred_strong_objects(self) -> List[Tuple[str, List, List]]:
        """
        Get all objects that this object refers to (e.g. an admin-c attribute
        on this object, that refers to person/role) along with the data this
        object has for that reference. This information can be used to check
        whether all references from an object are valid.
        Only references which have strong=True are returned, weak references
        are not returned as they should not be included in reference validation.

        Returns a list of tuples, which each tuple having:
        - field name on this object (e.g. 'admin-c')
        - RPSL object class names of objects referred (e.g. ['role', 'person']
        - Values this object has for that field (e.g. ['A-RIPE', 'B-RIPE']
        """
        result = []
        for field_name, referred_objects in self.referring_strong_fields:  # type: ignore
            data = self.parsed_data.get(field_name)
            if not data:
                continue
            result.append((field_name, referred_objects, data))
        return result

    def references_strong_inbound(self) -> Set[str]:
        """
        Get a set of field names under which other objects refer to
        this object. E.g. for a person object, this would typically
        return {'zone-c', 'admin-c', 'tech-c'}.
        """
        result = set()
        from irrd.rpsl.rpsl_objects import OBJECT_CLASS_MAPPING
        for rpsl_object in OBJECT_CLASS_MAPPING.values():
            for field_name, field in rpsl_object.fields.items():
                if self.rpsl_object_class in getattr(field, 'referring', []) and getattr(field, 'strong'):
                    result.add(field_name)
        return result

    def render_rpsl_text(self, last_modified: datetime.datetime=None) -> str:
        """
        Render the RPSL object as an RPSL string.
        If last_modified is provided, removes existing last-modified:
        attributes and adds a new one with that timestamp, if self.source()
        is authoritative.
        """
        output = ""
        authoritative = get_setting(f'sources.{self.source()}.authoritative')
        for attr, value, continuation_chars in self._object_data:
            if authoritative and last_modified and attr == 'last-modified':
                continue
            attr_display = f'{attr}:'.ljust(RPSL_ATTRIBUTE_TEXT_WIDTH)
            value_lines = list(splitline_unicodesafe(value))
            if not value_lines:
                output += f'{attr}:\n'
            for idx, line in enumerate(value_lines):
                if idx == 0:
                    output += attr_display + line
                else:
                    continuation_char = continuation_chars[idx - 1]
                    # Override the continuation char for empty lines #298
                    if not line:
                        continuation_char = '+'
                    output += continuation_char + (RPSL_ATTRIBUTE_TEXT_WIDTH - 1) * ' ' + line
                output += '\n'
        if authoritative and last_modified:
            output += 'last-modified:'.ljust(RPSL_ATTRIBUTE_TEXT_WIDTH)
            output += last_modified.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
            output += '\n'
        return output

    def generate_template(self):
        """Generate a template in text form of the main attributes of all fields."""
        template = ""
        max_name_width = max(len(k) for k in self.fields.keys())
        for name, field in self.fields.items():
            mandatory = '[optional] ' if field.optional else '[mandatory]'
            single = '[multiple]' if field.multiple else '[single]  '
            metadata = []
            if field.primary_key and field.lookup_key:
                metadata.append('primary/look-up key')
            elif field.primary_key:
                metadata.append('primary key')
            elif field.lookup_key:
                metadata.append('look-up key')
            if getattr(field, 'referring', []):
                reference_type = 'strong' if getattr(field, 'strong') else 'weak'
                metadata.append(f'{reference_type} references ' + '/'.join(field.referring))
            metadata_str = ', '.join(metadata)
            name_padding = (max_name_width - len(name)) * ' '
            template += f'{name}: {name_padding}  {mandatory}  {single}  [{metadata_str}]\n'
        return template

    def clean(self) -> bool:
        """
        Additional cleaning steps for some objects.
        """
        return True

    def clean_for_create(self) -> bool:
        """
        Additional cleaning steps for creations only.
        """
        return True

    def _extract_attributes_values(self, text: str) -> None:
        """
        Extract all attributes and associated values from the input string.

        This is mostly straight forward, except for the tricky feature of line
        continuation. An attribute's value can be continued on the next lines,
        which is distinct from an attribute occurring multiple times.

        The parse result is internally stored in self._object_data. This is a
        list of 3-tuples, where each tuple contains the attribute name,
        attribute value, and the continuation characters. The continuation
        characters are needed to reconstruct the original object into a string.
        """
        continuation_chars = (' ', '+', '\t')
        current_attr = None
        current_value = ""
        current_continuation_chars: List[str] = []

        for line_no, line in enumerate(splitline_unicodesafe(text.strip())):
            if not line:
                self.messages.error(f'Line {line_no+1}: encountered empty line in the middle of object: [{line}]')
                return

            if not line.startswith(continuation_chars):
                if current_attr and current_attr not in self.discarded_fields:
                    # Encountering a new attribute requires saving the previous attribute data first, if any,
                    # which can't be done earlier as line continuation means we can't know earlier whether
                    # the attribute is finished.
                    self._object_data.append((current_attr, current_value, current_continuation_chars))

                if ':' not in line:
                    self.messages.error(f'Line {line_no+1}: line is neither continuation nor valid attribute [{line}]')
                    return
                current_attr, current_value = line.split(':', maxsplit=1)
                current_attr = current_attr.lower()
                current_value = current_value.strip()
                current_continuation_chars = []

                if current_attr not in self.attrs_allowed and not self._re_attr_name.match(current_attr):
                    self.messages.error(f'Line {line_no+1}: encountered malformed attribute name: [{current_attr}]')
                    return
            else:
                # Whitespace between the continuation character and the start of the data is not significant.
                current_value += '\n' + line[1:].strip()
                current_continuation_chars += line[0]
        if current_attr and current_attr not in self.discarded_fields:
            self._object_data.append((current_attr, current_value, current_continuation_chars))

    def _validate_object(self) -> None:
        """
        Validate an object. The strictness depends on self.strict_validation
        (see the docstring for __init__).
        """
        self.parsed_data: Dict[str, Any[str, List]] = {}
        if not self.messages.errors():
            self._validate_attribute_counts()
        self._parse_attribute_data(allow_invalid_metadata=bool(self.messages.errors()))

        if self.strict_validation and not self.messages.errors():
            self.clean()

    def _validate_attribute_counts(self) -> None:
        """
        Validate the number of times each attribute occurs.

        The expected counts (0, 1, or >=1) are derived indirectly
        from the field data. In non-strict mode, only validate
        presence of all PK attributes.
        """
        attrs_present = Counter([attr[0] for attr in self._object_data])

        if self.strict_validation:
            for attr_name, count in attrs_present.items():
                if attr_name in self.ignored_validation_fields:
                    continue
                if attr_name not in self.attrs_allowed:
                    self.messages.error(f'Unrecognised attribute {attr_name} on object {self.rpsl_object_class}')
                if count > 1 and attr_name not in self.attrs_multiple:
                    self.messages.error(
                        f'Attribute "{attr_name}" on object {self.rpsl_object_class} occurs multiple times, but is '
                        f'only allowed once')
            for attr_required in self.attrs_required:
                if attr_required not in attrs_present:
                    self.messages.error(
                        f'Mandatory attribute "{attr_required}" on object {self.rpsl_object_class} is missing'
                    )
        else:
            required_fields = self.pk_fields
            if not self.default_source:
                required_fields = required_fields + ['source']
            for attr_pk in required_fields:
                if attr_pk not in attrs_present:
                    self.messages.error(
                        f'Primary key attribute "{attr_pk}" on object {self.rpsl_object_class} is missing'
                    )

    def _parse_attribute_data(self, allow_invalid_metadata=False) -> None:
        """
        Clean the data stored in attributes.

        If self.strict_validation is not set, only checks primary and lookup keys,
        as they need to be indexed. All parsed values (e.g. without comments) are
        stored in self.parsed_data - stored in upper case unless a field is marked
        case sensitive.

        If allow_invald_metadata is set, the parser will accept invalid metadata
        being stored, but still make a best effort to extract data. This should
        only be used if it is already known the object is invalid, and will
        never be stored.
        """
        for idx, (attr_name, value, continuation_chars) in enumerate(self._object_data):
            field = self.fields.get(attr_name)
            if field:
                normalised_value = self._normalise_rpsl_value(value)

                # We always parse all fields, but only care about errors if we're running
                # in strict validation mode, if the field is primary or lookup, or if it's
                # the source field. In all other cases, the field parsing is best effort.
                # In all these other cases we pass a new parser messages object to the
                # field parser, so that we basically discard any errors.
                raise_errors = self.strict_validation or field.primary_key or field.lookup_key or attr_name == 'source'
                field_messages = self.messages if raise_errors else RPSLParserMessages()
                parsed_value = field.parse(normalised_value, field_messages, self.strict_validation)

                if parsed_value:
                    parsed_value_str = parsed_value.value
                    if parsed_value_str != normalised_value:
                        # Note: this replacement can be incomplete: if the normalised value is not contained in the
                        # parsed value as single string, the replacement will not occur. This is not a great concern,
                        # as this is purely cosmetic, and self.parsed_data will have the correct normalised value.
                        new_value = value.replace(normalised_value, parsed_value_str)
                        self._object_data[idx] = attr_name, new_value, continuation_chars
                    values_list = parsed_value.values_list
                    if values_list:
                        if not field.keep_case:
                            values_list = list(map(str.upper, values_list))
                        if attr_name in self.parsed_data:
                            self.parsed_data[attr_name] += values_list
                        else:
                            self.parsed_data[attr_name] = values_list
                    else:
                        if not field.keep_case:
                            parsed_value_str = parsed_value_str.upper()
                        if field.multiple:
                            if attr_name in self.parsed_data:
                                self.parsed_data[attr_name].append(parsed_value_str)
                            else:
                                self.parsed_data[attr_name] = [parsed_value_str]
                        else:
                            if attr_name in self.parsed_data:
                                self.parsed_data[attr_name] = '\n' + parsed_value_str
                            else:
                                self.parsed_data[attr_name] = parsed_value_str

                    # Some fields provide additional metadata about the resources to
                    # which this object pertains.
                    if field.primary_key or field.lookup_key:
                        for attr in 'ip_first', 'ip_last', 'asn_first', 'asn_last', 'prefix', 'prefix_length':
                            attr_value = getattr(parsed_value, attr, None)
                            if attr_value:
                                existing_attr_value = getattr(self, attr, None)
                                if existing_attr_value and not allow_invalid_metadata:  # pragma: no cover
                                    raise ValueError(f'Parsing of {parsed_value.value} reads {attr_value} for {attr},'
                                                     f'but value {existing_attr_value} is already set.')
                                setattr(self, attr, attr_value)

        if 'source' not in self.parsed_data and self.default_source:
            self.parsed_data['source'] = self.default_source

    def _normalise_rpsl_value(self, value: str) -> str:
        """
        Normalise an RPSL attribute value to its significant parts
        in a consistent format.

        For example, the following is valid in RPSL:

            inetnum: 192.0.2.0 # comment1
            +- # comment 2
            +192.0.2.1 # comment 3
            + # comment 4

        This value will be normalised by this method to:
            192.0.2.0 - 192.0.2.1
        to be used for further validation and extraction of primary keys.
        """
        normalized_lines = []
        # The shortcuts below are functionally inconsequential, but significantly improve performance,
        # as most values are single line without comments, and this method is called extremely often.
        if '\n' not in value:
            if '#' in value:
                return value.split('#')[0].strip()
            return value.strip()
        for line in splitline_unicodesafe(value):
            parsed_line = line.split('#')[0].strip('\n\t, ')
            if parsed_line:
                normalized_lines.append(parsed_line)
        return ','.join(normalized_lines)

    def _update_attribute_value(self, attribute, new_values):
        """
        Update the value of an attribute in the internal state and in
        parsed_data.

        This is used for key-cert objects, where e.g. owner lines are
        derived from other data in the object.

        All existing occurences of the attribute are removed, new items
        are always inserted at line 2 of the object.
        """
        if isinstance(new_values, str):
            new_values = [new_values]
        self.parsed_data[attribute] = '\n'.join(new_values)

        self._object_data = list(filter(lambda a: a[0] != attribute, self._object_data))
        insert_idx = 1
        for new_value in new_values:
            self._object_data.insert(insert_idx, (attribute, new_value, []))
            insert_idx += 1

    def __repr__(self):
        source = self.parsed_data.get('source', '')
        return f'{self.rpsl_object_class}/{self.pk()}/{source}'

    def __key(self):
        return self.rpsl_object_class, self.pk(), json.dumps(self.parsed_data, sort_keys=True)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(self, type(other)) and self.__key() == other.__key()


class UnknownRPSLObjectClassException(Exception):  # noqa: N818
    def __init__(self, message: str, rpsl_object_class: str) -> None:
        self.message = message
        self.rpsl_object_class = rpsl_object_class

    def __str__(self):
        return self.message
