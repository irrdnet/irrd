from IPy import IP
from pytest import raises

from ..fields import (
    RPSLASBlockField,
    RPSLASNumberField,
    RPSLAuthField,
    RPSLChangedField,
    RPSLDNSNameField,
    RPSLEmailField,
    RPSLGenericNameField,
    RPSLIPv4AddressRangeField,
    RPSLIPv4PrefixesField,
    RPSLIPv4PrefixField,
    RPSLIPv6PrefixesField,
    RPSLIPv6PrefixField,
    RPSLReferenceField,
    RPSLReferenceListField,
    RPSLRouteSetMemberField,
    RPSLSetNameField,
    RPSLTextField,
    RPSLURLField,
)
from ..parser_state import RPSLParserMessages


def assert_validation_err(expected_errors, callable, *args, **kwargs):
    __tracebackhide__ = True

    if isinstance(expected_errors, str):
        expected_errors = [expected_errors]
    messages = RPSLParserMessages()
    assert not callable(*args, messages, **kwargs)
    errors = messages.errors()

    matched_expected_errors = []
    matched_errors = []

    for expected_error in expected_errors:
        for error in errors:
            if expected_error in error:
                matched_errors.append(error)
                matched_expected_errors.append(expected_error)

    expected_errors = [e for e in expected_errors if e not in matched_expected_errors]
    errors = [e for e in errors if e not in matched_errors]
    assert len(errors) == 0, f"unexpected error messages in: {messages.errors()}"
    assert len(expected_errors) == 0, f"did not find error messages: {expected_errors}"


def test_rpsl_text_field():
    field = RPSLTextField()
    messages = RPSLParserMessages()
    assert field.parse("AS-FOO$", messages).value, "AS-FOO$"
    assert not messages.errors()


def test_ipv4_prefix_field():
    field = RPSLIPv4PrefixField()
    messages = RPSLParserMessages()

    parse_result = field.parse("192.0.2.0/24", messages)
    assert parse_result.value == "192.0.2.0/24"
    assert parse_result.ip_first == IP("192.0.2.0")
    assert parse_result.ip_last == IP("192.0.2.255")
    assert parse_result.prefix_length == 24
    assert field.parse("192.00.02.0/25", messages).value == "192.0.2.0/25"
    assert field.parse("192.0.2.0/32", messages).value == "192.0.2.0/32"
    assert not messages.errors()
    assert messages.infos() == ["Address prefix 192.00.02.0/25 was reformatted as 192.0.2.0/25"]

    # 192.0.2/24 is generally seen as a valid prefix, but RFC 2622 does not allow this notation.
    assert_validation_err("Invalid address prefix", field.parse, "192.0.2/24")
    assert_validation_err("Invalid address prefix", field.parse, "555.555.555.555/24")
    assert_validation_err("Invalid address prefix", field.parse, "foo")
    assert_validation_err("Invalid address prefix", field.parse, "2001::/32")
    assert_validation_err("Invalid address prefix", field.parse, "192.0.2.0/16")


def test_ipv4_prefixes_field():
    field = RPSLIPv4PrefixesField()
    messages = RPSLParserMessages()
    assert field.parse("192.0.2.0/24", messages).value == "192.0.2.0/24"
    # Technically, the trailing comma is not RFC-compliant.
    # However, it's used in some cases when the list is broken over
    # multiple lines, and accepting it is harmless.
    parse_result = field.parse("192.0.2.0/24, 192.00.02.0/25, ", messages)
    assert parse_result.value == "192.0.2.0/24,192.0.2.0/25"
    assert parse_result.values_list == ["192.0.2.0/24", "192.0.2.0/25"]
    assert not messages.errors()
    assert messages.infos() == ["Address prefix 192.00.02.0/25 was reformatted as 192.0.2.0/25"]

    assert_validation_err("Invalid address prefix", field.parse, "192.0.2.0/24, 192.0.2/16")


def test_ipv6_prefix_field():
    field = RPSLIPv6PrefixField()
    messages = RPSLParserMessages()

    parse_result = field.parse("12AB:0000:0000:CD30:0000:0000:0000:0000/60", messages)
    assert parse_result.value == "12ab:0:0:cd30::/60"
    assert parse_result.ip_first == IP("12ab:0:0:cd30::")
    assert parse_result.ip_last == IP("12ab::cd3f:ffff:ffff:ffff:ffff")
    assert parse_result.prefix_length == 60

    assert field.parse("12ab::cd30:0:0:0:0/60", messages).value == "12ab:0:0:cd30::/60"
    assert field.parse("12AB:0:0:CD30::/60", messages).value == "12ab:0:0:cd30::/60"
    assert field.parse("12ab:0:0:cd30::/128", messages).value == "12ab:0:0:cd30::/128"
    assert not messages.errors()
    assert messages.infos() == [
        "Address prefix 12AB:0000:0000:CD30:0000:0000:0000:0000/60 was reformatted as 12ab:0:0:cd30::/60",
        "Address prefix 12ab::cd30:0:0:0:0/60 was reformatted as 12ab:0:0:cd30::/60",
        "Address prefix 12AB:0:0:CD30::/60 was reformatted as 12ab:0:0:cd30::/60",
    ]

    assert_validation_err("Invalid address prefix", field.parse, "foo")
    assert_validation_err("Invalid address prefix", field.parse, "foo/bar")
    assert_validation_err("invalid hexlet", field.parse, "2001525::/32")
    assert_validation_err("should have 8 hextets", field.parse, "12AB:0:0:CD3/60")
    assert_validation_err("Invalid address prefix", field.parse, "12AB::CD30/60")
    assert_validation_err("Invalid address prefix", field.parse, "12AB::CD3/60")
    assert_validation_err("Invalid address prefix", field.parse, "192.0.2.0/16")


def test_ipv6_prefixes_field():
    field = RPSLIPv6PrefixesField()
    messages = RPSLParserMessages()
    assert field.parse("12AB:0:0:CD30::/60", messages).value == "12ab:0:0:cd30::/60"
    assert (
        field.parse("12AB:0:0:CD30::/60, 2001:DB8::0/64", messages).value
        == "12ab:0:0:cd30::/60,2001:db8::/64"
    )
    assert not messages.errors()

    assert_validation_err("Invalid address prefix", field.parse, "foo")
    assert_validation_err("Invalid address prefix", field.parse, "foo/bar")
    assert_validation_err("invalid hexlet", field.parse, "2001:db8::/32, 2001525::/32")
    assert_validation_err("should have 8 hextets", field.parse, "12AB:0:0:CD3/60")
    assert_validation_err("Invalid address prefix", field.parse, "12AB::CD30/60")
    assert_validation_err("Invalid address prefix", field.parse, "12AB::CD3/60")
    assert_validation_err("Invalid address prefix", field.parse, "192.0.2.0/16")


def test_ipv4_address_range_field():
    field = RPSLIPv4AddressRangeField()
    messages = RPSLParserMessages()

    parse_result = field.parse("192.0.02.0", messages)
    assert parse_result.value == "192.0.2.0"
    assert parse_result.ip_first == IP("192.0.2.0")
    assert parse_result.ip_last == IP("192.0.2.0")

    parse_result = field.parse("192.0.2.0 - 192.0.2.126", messages)
    assert parse_result.value == "192.0.2.0 - 192.0.2.126"

    parse_result = field.parse("192.0.2.0 -192.0.02.126", messages)
    assert parse_result.value == "192.0.2.0 - 192.0.2.126"
    assert parse_result.ip_first == IP("192.0.2.0")
    assert parse_result.ip_last == IP("192.0.2.126")

    assert not messages.errors()
    assert messages.infos() == [
        "Address range 192.0.02.0 was reformatted as 192.0.2.0",
        "Address range 192.0.2.0 -192.0.02.126 was reformatted as 192.0.2.0 - 192.0.2.126",
    ]

    assert_validation_err("Invalid address", field.parse, "192.0.1.5555 - 192.0.2.0")
    assert_validation_err("IP version mismatch", field.parse, "192.0.2.0 - 2001:db8::")
    assert_validation_err("first IP is higher", field.parse, "192.0.2.1 - 192.0.2.0")
    assert_validation_err("IP version mismatch", field.parse, "2001:db8::0 - 2001:db8::1")


def test_route_set_members_field():
    with raises(ValueError):
        RPSLRouteSetMemberField(ip_version=2)

    field = RPSLRouteSetMemberField(ip_version=4)
    messages = RPSLParserMessages()

    assert field.parse("192.0.2.0/24^24-25", messages).value == "192.0.2.0/24^24-25"
    assert field.parse("AS065537:RS-TEST^32", messages).value == "AS65537:RS-TEST^32"
    assert field.parse("AS065537^32", messages).value == "AS65537^32"
    assert field.parse("192.0.2.0/25^+", messages).value == "192.0.2.0/25^+"
    assert field.parse("192.0.2.0/25^32", messages).value == "192.0.2.0/25^32"
    assert field.parse("192.00.02.0/25^-", messages).value == "192.0.2.0/25^-"
    assert field.parse("192.0.02.0/32", messages).value == "192.0.2.0/32"
    assert not messages.errors()
    assert messages.infos() == [
        "Route set member AS065537:RS-TEST^32 was reformatted as AS65537:RS-TEST^32",
        "Route set member AS065537^32 was reformatted as AS65537^32",
        "Route set member 192.00.02.0/25^- was reformatted as 192.0.2.0/25^-",
        "Route set member 192.0.02.0/32 was reformatted as 192.0.2.0/32",
    ]

    assert_validation_err("Value is neither a valid set name nor a valid prefix", field.parse, "AS65537:TEST")
    assert_validation_err("Missing range operator", field.parse, "192.0.2.0/24^")
    assert_validation_err("Invalid range operator", field.parse, "192.0.2.0/24^x")
    assert_validation_err("Invalid range operator", field.parse, "192.0.2.0/24^-32")
    assert_validation_err("Invalid range operator", field.parse, "192.0.2.0/24^32-")
    assert_validation_err("Invalid range operator", field.parse, "192.0.2.0/24^24+32")
    assert_validation_err("operator length (23) must be equal ", field.parse, "192.0.2.0/24^23")
    assert_validation_err("operator start (23) must be equal ", field.parse, "192.0.2.0/24^23-32")
    assert_validation_err("operator end (30) must be equal", field.parse, "192.0.2.0/24^32-30")

    field = RPSLRouteSetMemberField(ip_version=None)
    messages = RPSLParserMessages()

    assert field.parse("192.0.2.0/24^24-25", messages).value == "192.0.2.0/24^24-25"
    assert field.parse("12ab:0:0:cd30::/128", messages).value == "12ab:0:0:cd30::/128"
    assert field.parse("12ab:0:0:cd30::/64^120-128", messages).value == "12ab:0:0:cd30::/64^120-128"
    assert field.parse("AS65537:RS-TEST", messages).value == "AS65537:RS-TEST"

    assert field.parse("192.0.2.0/25^+", messages).value == "192.0.2.0/25^+"
    assert field.parse("192.0.2.0/25^32", messages).value == "192.0.2.0/25^32"
    assert field.parse("12ab:00:0:cd30::/60^-", messages).value == "12ab:0:0:cd30::/60^-"
    assert field.parse("12ab:0:0:cd30::/60", messages).value == "12ab:0:0:cd30::/60"
    assert not messages.errors()
    assert messages.infos() == [
        "Route set member 12ab:00:0:cd30::/60^- was reformatted as 12ab:0:0:cd30::/60^-",
    ]

    assert_validation_err("Invalid range operator", field.parse, "192.0.2.0/32^24+32")
    assert_validation_err("Invalid range operator", field.parse, "12ab:0:0:cd30::/60^24+32")


def test_validate_as_number_field():
    field = RPSLASNumberField()
    messages = RPSLParserMessages()

    parse_result = field.parse("AS065537", messages)
    assert parse_result.value == "AS65537"
    assert parse_result.asn_first == 65537
    assert parse_result.asn_last == 65537
    assert not messages.errors()
    assert messages.infos() == ["AS number AS065537 was reformatted as AS65537"]

    assert_validation_err("not numeric", field.parse, "ASxxxx")
    assert_validation_err("not numeric", field.parse, "AS2345💩")
    assert_validation_err("must start with", field.parse, "💩AS2345")


def test_validate_as_block_field():
    field = RPSLASBlockField()
    messages = RPSLParserMessages()

    parse_result = field.parse("AS001- AS200", messages)
    assert parse_result.value == "AS1 - AS200"
    assert parse_result.asn_first == 1
    assert parse_result.asn_last == 200

    assert field.parse("AS200-AS0200", messages).value == "AS200 - AS200"
    assert not messages.errors()
    assert messages.infos() == [
        "AS range AS001- AS200 was reformatted as AS1 - AS200",
        "AS range AS200-AS0200 was reformatted as AS200 - AS200",
    ]

    assert_validation_err("does not contain a hyphen", field.parse, "AS65537")
    assert_validation_err("number part is not numeric", field.parse, "ASxxxx - ASyyyy")
    assert_validation_err("Invalid AS number", field.parse, "AS-FOO - AS-BAR")
    assert_validation_err("Invalid AS range", field.parse, "AS300 - AS200")


def test_validate_set_name_field():
    field = RPSLSetNameField(prefix="AS")
    messages = RPSLParserMessages()
    assert field.parse("AS-FOO", messages).value == "AS-FOO"
    assert field.parse("AS01:AS-FOO", messages).value == "AS1:AS-FOO"
    assert field.parse("AS1:AS-FOO:AS3", messages).value == "AS1:AS-FOO:AS3"
    assert field.parse("AS01:AS-3", messages).value == "AS1:AS-3"
    assert not messages.errors()
    assert messages.infos() == [
        "Set name AS01:AS-FOO was reformatted as AS1:AS-FOO",
        "Set name AS01:AS-3 was reformatted as AS1:AS-3",
    ]

    long_set = "AS1:AS-B:AS-C:AS-D:AS-E:AS-F"
    assert_validation_err(
        "at least one component must be an actual set name",
        field.parse,
        "AS1",
    )
    assert_validation_err("at least one component must be an actual set name", field.parse, "AS1:AS3")
    assert_validation_err(
        "not a valid AS number, nor does it start with AS-", field.parse, "AS1:AS-FOO:RS-FORBIDDEN"
    )
    assert_validation_err("not a valid AS number nor a valid set name", field.parse, ":AS-FOO")
    assert_validation_err("not a valid AS number nor a valid set name", field.parse, "AS-FOO:")
    assert_validation_err("can have a maximum of five components", field.parse, long_set)
    assert_validation_err("reserved word", field.parse, "AS1:AS-ANY")

    assert field.parse("AS-ANY", messages, strict_validation=False).value == "AS-ANY"
    assert field.parse(long_set, messages, strict_validation=False).value == long_set

    field = RPSLSetNameField(prefix="RS")
    messages = RPSLParserMessages()
    assert field.parse("RS-FOO", messages).value == "RS-FOO"
    assert field.parse("AS1:RS-FOO", messages).value == "AS1:RS-FOO"
    assert field.parse("AS1:RS-FOO:AS3", messages).value == "AS1:RS-FOO:AS3"
    assert field.parse("AS1:RS-3", messages).value == "AS1:RS-3"
    assert not messages.errors()

    assert_validation_err("at least one component must be an actual set name", field.parse, "AS1:AS-FOO")


def test_validate_email_field():
    field = RPSLEmailField()
    messages = RPSLParserMessages()
    assert field.parse("foo.bar@example.asia", messages).value == "foo.bar@example.asia"
    assert field.parse("foo.bar@[192.0.2.1]", messages).value == "foo.bar@[192.0.2.1]"
    assert field.parse("foo.bar@[2001:db8::1]", messages).value == "foo.bar@[2001:db8::1]"
    assert not messages.errors()

    assert_validation_err("Invalid e-mail", field.parse, "foo.bar+baz@")
    assert_validation_err("Invalid e-mail", field.parse, "a§§@example.com")
    assert_validation_err("Invalid e-mail", field.parse, "a@[192.0.2.2.2]")


def test_validate_changed_field():
    field = RPSLChangedField()
    messages = RPSLParserMessages()
    assert field.parse("foo.bar@example.asia", messages).value == "foo.bar@example.asia"
    assert field.parse("foo.bar@[192.0.2.1] 20190701", messages).value == "foo.bar@[192.0.2.1] 20190701"
    assert field.parse("foo.bar@[2001:db8::1] 19980101", messages).value == "foo.bar@[2001:db8::1] 19980101"
    assert not messages.errors()

    assert_validation_err("Invalid e-mail", field.parse, "foo.bar+baz@")
    assert_validation_err("Invalid changed date", field.parse, "foo.bar@example.com 20191301")
    assert_validation_err("Invalid e-mail", field.parse, "\nfoo.bar@example.com \n20190701")
    assert_validation_err("Invalid changed date", field.parse, "foo.bar@example.com \n20190701")
    assert_validation_err("Invalid changed date", field.parse, "foo.bar@example.com 20190701\n")


def test_validate_dns_name_field():
    field = RPSLDNSNameField()
    messages = RPSLParserMessages()
    assert field.parse("foo.bar.baz", messages).value == "foo.bar.baz"
    assert not messages.errors()

    assert_validation_err("Invalid DNS name", field.parse, "foo.bar+baz@")


def test_validate_url_field():
    field = RPSLURLField()
    messages = RPSLParserMessages()
    assert field.parse("http://example.com", messages).value == "http://example.com"
    assert field.parse("https://example.com", messages).value == "https://example.com"
    assert not messages.errors()

    assert_validation_err("Invalid http/https URL", field.parse, "ftp://test")
    assert_validation_err("Invalid http/https URL", field.parse, "test")
    assert_validation_err("Invalid http/https URL", field.parse, "test")


def test_validate_generic_name_field():
    field = RPSLGenericNameField()
    messages = RPSLParserMessages()
    assert field.parse("MAINT-FOO", messages).value == "MAINT-FOO"
    assert field.parse("FOO-MNT", messages).value == "FOO-MNT"
    assert field.parse("FOO-MN_T2", messages).value == "FOO-MN_T2"
    assert not messages.errors()

    assert_validation_err("reserved word", field.parse, "any")
    assert_validation_err("reserved prefix", field.parse, "As-FOO")
    assert_validation_err("invalid character", field.parse, "FoO$BAR")
    assert_validation_err("invalid character", field.parse, "FOOBAR-")
    assert_validation_err("invalid character", field.parse, "FOO💩BAR")

    assert field.parse("AS-FOO", messages, strict_validation=False).value == "AS-FOO"
    assert field.parse("FOO BAR", messages, strict_validation=False) is None

    field = RPSLGenericNameField(allowed_prefixes=["as"])
    messages = RPSLParserMessages()
    assert field.parse("As-FOO", messages).value == "As-FOO"
    assert not messages.errors()

    assert_validation_err("reserved prefix", field.parse, "FLTr-FOO")

    field = RPSLGenericNameField(non_strict_allow_any=True)
    assert field.parse("FOO BAR", messages, strict_validation=False).value == "FOO BAR"
    assert_validation_err("invalid character", field.parse, "FOO BAR")


def test_rpsl_reference_field():
    field = RPSLReferenceField(referring=["person"])
    messages = RPSLParserMessages()
    assert field.parse("SR123-NTT", messages).value == "SR123-NTT"
    assert not messages.errors()

    assert_validation_err("RS- is a reserved prefix", field.parse, "RS-1234")
    assert_validation_err("Invalid name", field.parse, "foo$$")

    field = RPSLReferenceField(referring=["aut-num", "as-set"])
    messages = RPSLParserMessages()
    assert field.parse("AS01234", messages).value == "AS1234"
    assert field.parse("AS-FOO", messages).value == "AS-FOO"
    assert not messages.errors()

    assert_validation_err(["Invalid AS number", "start with AS-"], field.parse, "RS-1234")
    assert_validation_err(["Invalid AS number", "start with AS-"], field.parse, "RS-1234")
    assert_validation_err(
        ["Invalid AS number", "at least one component must be an actual set name (i.e. start with AS-"],
        field.parse,
        "FOOBAR",
    )


def test_rpsl_references_field():
    field = RPSLReferenceListField(referring=["aut-num"])
    messages = RPSLParserMessages()
    assert field.parse("AS1234", messages).value == "AS1234"
    assert field.parse("AS01234, AS04567", messages).value == "AS1234,AS4567"
    assert not messages.errors()

    assert_validation_err("Invalid AS number", field.parse, "ANY")

    field = RPSLReferenceListField(referring=["aut-num"], allow_kw_any=True)
    messages = RPSLParserMessages()
    assert field.parse("AS1234", messages).value == "AS1234"
    assert field.parse("AS01234, AS04567", messages).value == "AS1234,AS4567"
    assert field.parse("any", messages).value == "ANY"
    assert not messages.errors()

    assert_validation_err("Invalid AS number", field.parse, "AS1234, any")


def test_rpsl_auth_field(config_override):
    field = RPSLAuthField()
    messages = RPSLParserMessages()
    assert field.parse("MD5-pw hashhash", messages).value == "MD5-pw hashhash"
    assert field.parse("bcrypt-pw hashhash", messages).value == "bcrypt-pw hashhash"
    assert field.parse("PGPKEY-AABB0011", messages).value == "PGPKEY-AABB0011"
    assert not messages.errors()

    assert_validation_err("Invalid auth attribute", field.parse, "PGPKEY-XX")
    assert_validation_err("Invalid auth attribute", field.parse, "PGPKEY-AABB00112233")
    assert_validation_err("Invalid auth attribute", field.parse, "ARGON-PW hashhash")
    assert_validation_err("Invalid auth attribute", field.parse, "BCRYPT-PWhashhash")

    assert_validation_err("Invalid auth attribute", field.parse, "CRYPT-PW hashhash")
    assert field.parse("CRYPT-PW hashhash", messages, strict_validation=False).value == "CRYPT-PW hashhash"

    config_override({"auth": {"password_hashers": {"crypt-pw": "enabled"}}})
    assert field.parse("CRYPT-PW hashhash", messages).value == "CRYPT-PW hashhash"

    config_override({"auth": {"password_hashers": {"crypt-pw": "disabled"}}})
    assert field.parse("CRYPT-PW hashhash", messages, strict_validation=False) is None
