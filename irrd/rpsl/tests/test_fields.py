from ..fields import (
    RPSLASBlockField,
    RPSLASNumberField,
    RPSLAuthField,
    RPSLDNSNameField,
    RPSLEmailField,
    RPSLGenericNameField,
    RPSLIPv4AddressRangeField,
    RPSLIPv4PrefixField,
    RPSLIPv4PrefixesField,
    RPSLIPv6PrefixField,
    RPSLIPv6PrefixesField,
    RPSLReferenceField,
    RPSLReferenceListField,
    RPSLSetNameField,
    RPSLTextField,
)
from ..validators import RPSLParserMessages


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
    assert field.clean("AS-FOO$", messages), "AS-FOO$"
    assert not messages.errors()


def test_ipv4_prefix_field():
    field = RPSLIPv4PrefixField()
    messages = RPSLParserMessages()
    assert field.clean("192.0.2.0/24", messages) == "192.0.2.0/24"
    assert field.clean("192.00.02.0/25", messages) == "192.0.2.0/25"
    assert not messages.errors()
    assert messages.infos() == ["Address prefix 192.00.02.0/25 was reformatted as 192.0.2.0/25"]

    # 192.0.2/24 is generally seen as a valid prefix, but RFC 2622 does not allow this notation.
    assert_validation_err("Invalid address prefix", field.clean, "192.0.2/24")
    assert_validation_err("Invalid address prefix", field.clean, "555.555.555.555/24")
    assert_validation_err("Invalid address prefix", field.clean, "foo")
    assert_validation_err("Invalid address prefix", field.clean, "2001::/32")
    assert_validation_err("Invalid prefix length", field.clean, "192.0.2.0/16")


def test_ipv4_prefixes_field():
    field = RPSLIPv4PrefixesField()
    messages = RPSLParserMessages()
    assert field.clean("192.0.2.0/24", messages) == "192.0.2.0/24"
    assert field.clean("192.0.2.0/24, 192.00.02.0/25", messages) == "192.0.2.0/24,192.0.2.0/25"
    assert not messages.errors()
    assert messages.infos() == ["Address prefix 192.00.02.0/25 was reformatted as 192.0.2.0/25"]

    assert_validation_err("Invalid address prefix", field.clean, "192.0.2.0/24, 192.0.2/24")


def test_ipv6_prefix_field():
    field = RPSLIPv6PrefixField()
    messages = RPSLParserMessages()
    assert field.clean("12AB:0000:0000:CD30:0000:0000:0000:0000/60", messages) == "12ab:0:0:cd30::/60"
    assert field.clean("12ab::cd30:0:0:0:0/60", messages) == "12ab:0:0:cd30::/60"
    assert field.clean("12AB:0:0:CD30::/60", messages) == "12ab:0:0:cd30::/60"
    assert not messages.errors()
    assert messages.infos() == [
        "Address prefix 12AB:0000:0000:CD30:0000:0000:0000:0000/60 was reformatted as 12ab:0:0:cd30::/60",
        "Address prefix 12ab::cd30:0:0:0:0/60 was reformatted as 12ab:0:0:cd30::/60",
        "Address prefix 12AB:0:0:CD30::/60 was reformatted as 12ab:0:0:cd30::/60",
    ]

    assert_validation_err("Invalid address prefix", field.clean, "foo")
    assert_validation_err("Invalid address prefix", field.clean, "foo/bar")
    assert_validation_err("invalid hexlet", field.clean, "2001525::/32")
    assert_validation_err("should have 8 hextets", field.clean, "12AB:0:0:CD3/60")
    assert_validation_err("Invalid prefix length", field.clean, "12AB::CD30/60")
    assert_validation_err("Invalid prefix length", field.clean, "12AB::CD3/60")
    assert_validation_err("Invalid address prefix", field.clean, "192.0.2.0/16")


def test_ipv6_prefixes_field():
    field = RPSLIPv6PrefixesField()
    messages = RPSLParserMessages()
    assert field.clean("12AB:0:0:CD30::/60", messages) == "12ab:0:0:cd30::/60"
    assert field.clean("12AB:0:0:CD30::/60, 2001:DB8::0/64", messages) == "12ab:0:0:cd30::/60,2001:db8::/64"
    assert not messages.errors()

    assert_validation_err("Invalid address prefix", field.clean, "foo")
    assert_validation_err("Invalid address prefix", field.clean, "foo/bar")
    assert_validation_err("invalid hexlet", field.clean, "2001:db8::/32, 2001525::/32")
    assert_validation_err("should have 8 hextets", field.clean, "12AB:0:0:CD3/60")
    assert_validation_err("Invalid prefix length", field.clean, "12AB::CD30/60")
    assert_validation_err("Invalid prefix length", field.clean, "12AB::CD3/60")
    assert_validation_err("Invalid address prefix", field.clean, "192.0.2.0/16")


def test_ipv4_address_range_field():
    field = RPSLIPv4AddressRangeField()
    messages = RPSLParserMessages()
    assert field.clean("192.0.02.0", messages) == "192.0.2.0"
    assert field.clean("192.0.2.0 -192.0.02.128", messages) == "192.0.2.0 - 192.0.2.128"
    assert not messages.errors()
    assert messages.infos() == [
        "Address range 192.0.02.0 was reformatted as 192.0.2.0",
        "Address range 192.0.2.0 -192.0.02.128 was reformatted as 192.0.2.0 - 192.0.2.128",
    ]

    assert_validation_err("Invalid address", field.clean, "192.0.1.5555 - 192.0.2.0")
    assert_validation_err("IP version mismatch", field.clean, "192.0.2.0 - 2001:db8::")
    assert_validation_err("first IP is higher", field.clean, "192.0.2.1 - 192.0.2.0")
    assert_validation_err("IP version mismatch", field.clean, "2001:db8::0 - 2001:db8::1")


def test_validate_as_number_field():
    field = RPSLASNumberField()
    messages = RPSLParserMessages()
    assert field.clean("AS023456", messages) == "AS23456"
    assert not messages.errors()
    assert messages.infos() == ["AS number AS023456 was reformatted as AS23456"]

    assert_validation_err("not numeric", field.clean, "ASxxxx")


def test_validate_as_block_field():
    field = RPSLASBlockField()
    messages = RPSLParserMessages()
    assert field.clean("AS001- AS200", messages) == "AS1 - AS200"
    assert field.clean("AS200-AS0200", messages) == "AS200 - AS200"
    assert not messages.errors()
    assert messages.infos() == [
        "AS range AS001- AS200 was reformatted as AS1 - AS200", "AS range AS200-AS0200 was reformatted as AS200 - AS200"
    ]

    assert_validation_err("does not contain a hyphen", field.clean, "AS23456")
    assert_validation_err("number part is not numeric", field.clean, "ASxxxx - ASyyyy")
    assert_validation_err("Invalid AS number", field.clean, "AS-FOO - AS-BAR")
    assert_validation_err("Invalid AS range", field.clean, "AS300 - AS200")


def test_validate_set_name_field():
    field = RPSLSetNameField(prefix="AS")
    messages = RPSLParserMessages()
    assert field.clean("AS-FOO", messages) == "AS-FOO"
    assert field.clean("AS01:AS-FOO", messages) == "AS1:AS-FOO"
    assert field.clean("AS1:AS-FOO:AS3", messages) == "AS1:AS-FOO:AS3"
    assert field.clean("AS01:AS-3", messages) == "AS1:AS-3"
    assert not messages.errors()
    assert messages.infos() == [
        "Set name AS01:AS-FOO was reformatted as AS1:AS-FOO", "Set name AS01:AS-3 was reformatted as AS1:AS-3"
    ]

    assert_validation_err(
        "at least one component must be an actual set name",
        field.clean,
        "AS1",
    )
    assert_validation_err("at least one component must be an actual set name", field.clean, "AS1:AS3")
    assert_validation_err("not a valid AS number nor a valid set name", field.clean, ":AS-FOO")
    assert_validation_err("not a valid AS number nor a valid set name", field.clean, "AS-FOO:")
    assert_validation_err("reserved word", field.clean, "AS1:AS-ANY")

    field = RPSLSetNameField(prefix="RS")
    messages = RPSLParserMessages()
    assert field.clean("RS-FOO", messages) == "RS-FOO"
    assert field.clean("AS1:RS-FOO", messages) == "AS1:RS-FOO"
    assert field.clean("AS1:RS-FOO:AS3", messages) == "AS1:RS-FOO:AS3"
    assert field.clean("AS1:RS-3", messages) == "AS1:RS-3"
    assert not messages.errors()

    assert_validation_err("at least one component must be an actual set name", field.clean, "AS1:AS-FOO")


def test_validate_email_field():
    field = RPSLEmailField()
    messages = RPSLParserMessages()
    assert field.clean("foo.bar@example.asia", messages) == "foo.bar@example.asia"
    assert not messages.errors()

    assert_validation_err("Invalid e-mail", field.clean, "foo.bar+baz@")
    assert_validation_err("Invalid e-mail", field.clean, "a§§@example.com")


def test_validate_dns_name_field():
    field = RPSLDNSNameField()
    messages = RPSLParserMessages()
    assert field.clean("foo.bar.baz", messages) == "foo.bar.baz"
    assert not messages.errors()

    assert_validation_err("Invalid DNS name", field.clean, "foo.bar+baz@")


def test_validate_generic_name_field():
    field = RPSLGenericNameField()
    messages = RPSLParserMessages()
    assert field.clean("MAINT-FOO", messages) == "MAINT-FOO"
    assert field.clean("FOO-MNT", messages) == "FOO-MNT"
    assert field.clean("FOO-MN_T2", messages) == "FOO-MN_T2"
    assert not messages.errors()

    assert_validation_err("reserved word", field.clean, "any")
    assert_validation_err("reserved prefix", field.clean, "As-FOO")
    assert_validation_err("invalid character", field.clean, "FoO$BAR")
    assert_validation_err("invalid character", field.clean, "FOOBAR-")

    field = RPSLGenericNameField(allowed_prefixes=["as"])
    assert field.clean("As-FOO", messages) == "As-FOO"
    assert not messages.errors()

    assert_validation_err("reserved prefix", field.clean, "FLTr-FOO")


def test_rpsl_reference_field():
    field = RPSLReferenceField(referring=["person"])
    messages = RPSLParserMessages()
    assert field.clean("SR123-NTT", messages) == "SR123-NTT"
    assert not messages.errors()

    assert_validation_err("RS- is a reserved prefix", field.clean, "RS-1234")
    assert_validation_err("Invalid name", field.clean, "foo$$")

    field = RPSLReferenceField(referring=["aut-num", "as-set"])
    messages = RPSLParserMessages()
    assert field.clean("AS01234", messages) == "AS1234"
    assert field.clean("AS-FOO", messages) == "AS-FOO"
    assert not messages.errors()

    assert_validation_err(["Invalid AS number", "start with AS-"], field.clean, "RS-1234")
    assert_validation_err(["Invalid AS number", "start with AS-"], field.clean, "RS-1234")
    assert_validation_err(
        ["Invalid AS number", "at least one component must be an actual set name (i.e. start with AS-"], field.clean,
        "FOOBAR")


def test_rpsl_references_field():
    field = RPSLReferenceListField(referring=["aut-num"])
    messages = RPSLParserMessages()
    assert field.clean("AS1234", messages) == "AS1234"
    assert field.clean("AS01234, AS04567", messages) == "AS1234,AS4567"
    assert not messages.errors()

    assert_validation_err("Invalid AS number", field.clean, "ANY")

    field = RPSLReferenceListField(referring=["aut-num"], allow_kw_any=True)
    messages = RPSLParserMessages()
    assert field.clean("AS1234", messages) == "AS1234"
    assert field.clean("AS01234, AS04567", messages) == "AS1234,AS4567"
    assert field.clean("any", messages) == "ANY"
    assert not messages.errors()

    assert_validation_err("Invalid AS number", field.clean, "AS1234, any")


def test_rpsl_auth_field():
    field = RPSLAuthField()
    messages = RPSLParserMessages()
    assert field.clean("CRYPT-PW hashhash", messages) == "CRYPT-PW hashhash"
    assert field.clean("MD5-pw hashhash", messages) == "MD5-pw hashhash"
    assert field.clean("PGPKEY-AABB0011", messages) == "PGPKEY-AABB0011"
    assert not messages.errors()

    assert_validation_err("Invalid auth attribute", field.clean, "PGPKEY-XX")
    assert_validation_err("Invalid auth attribute", field.clean, "PGPKEY-AABB00112233")
    assert_validation_err("Invalid auth attribute", field.clean, "ARGON-PW hashhash")
    assert_validation_err("Invalid auth attribute", field.clean, "CRYPT-PWhashhash")
