import datetime

import pytest
from IPy import IP
from pytest import raises
from pytz import timezone

from irrd.conf import AUTH_SET_CREATION_COMMON_KEY, PASSWORD_HASH_DUMMY_VALUE
from irrd.utils.rpsl_samples import (
    KEY_CERT_SIGNED_MESSAGE_CORRUPT,
    KEY_CERT_SIGNED_MESSAGE_INVALID,
    KEY_CERT_SIGNED_MESSAGE_VALID,
    KEY_CERT_SIGNED_MESSAGE_WRONG_KEY,
    SAMPLE_INVALID_MULTIPLE_ATTRIBUTE,
    SAMPLE_LINE_NEITHER_CONTINUATION_NOR_ATTR,
    SAMPLE_MALFORMED_ATTRIBUTE_NAME,
    SAMPLE_MALFORMED_EMPTY_LINE,
    SAMPLE_MALFORMED_PK,
    SAMPLE_MALFORMED_SOURCE,
    SAMPLE_MISSING_MANDATORY_ATTRIBUTE,
    SAMPLE_MISSING_SOURCE,
    SAMPLE_ROUTE,
    SAMPLE_UNKNOWN_ATTRIBUTE,
    SAMPLE_UNKNOWN_CLASS,
    TEMPLATE_PERSON_OBJECT,
    TEMPLATE_ROUTE_OBJECT,
    object_sample_mapping,
)

from ..parser import UnknownRPSLObjectClassException
from ..rpsl_objects import (
    OBJECT_CLASS_MAPPING,
    RPSLAsBlock,
    RPSLAsSet,
    RPSLAutNum,
    RPSLDomain,
    RPSLFilterSet,
    RPSLInet6Num,
    RPSLInetnum,
    RPSLInetRtr,
    RPSLKeyCert,
    RPSLMntner,
    RPSLPeeringSet,
    RPSLPerson,
    RPSLRole,
    RPSLRoute,
    RPSLRoute6,
    RPSLRouteSet,
    RPSLRtrSet,
    rpsl_object_from_text,
)


class TestRPSLParsingGeneric:
    # Most malformed objects are tested without strict validation, as they should always fail.
    def test_unknown_class(self):
        with raises(UnknownRPSLObjectClassException) as ve:
            rpsl_object_from_text(SAMPLE_UNKNOWN_CLASS)
        assert "unknown object class" in str(ve.value)

    def test_malformed_empty_line(self):
        obj = rpsl_object_from_text(SAMPLE_MALFORMED_EMPTY_LINE, strict_validation=False)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "encountered empty line" in obj.messages.errors()[0]

        with raises(ValueError):
            obj.source()

    def test_malformed_attribute_name(self):
        obj = rpsl_object_from_text(SAMPLE_MALFORMED_ATTRIBUTE_NAME, strict_validation=False)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "malformed attribute name" in obj.messages.errors()[0]

    def test_missing_mandatory_attribute(self):
        obj = rpsl_object_from_text(SAMPLE_MISSING_MANDATORY_ATTRIBUTE, strict_validation=True)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert 'Mandatory attribute "mnt-by" on object route is missing' in obj.messages.errors()[0]

        obj = rpsl_object_from_text(SAMPLE_MISSING_MANDATORY_ATTRIBUTE, strict_validation=False)
        assert len(obj.messages.errors()) == 0, f"Unexpected extra errors: {obj.messages.errors()}"

    def test_unknown_atribute(self):
        obj = rpsl_object_from_text(SAMPLE_UNKNOWN_ATTRIBUTE, strict_validation=True)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "Unrecognised attribute" in obj.messages.errors()[0]

        obj = rpsl_object_from_text(SAMPLE_UNKNOWN_ATTRIBUTE, strict_validation=False)
        assert len(obj.messages.errors()) == 0, f"Unexpected extra errors: {obj.messages.errors()}"

    def test_invalid_multiple_attribute(self):
        obj = rpsl_object_from_text(SAMPLE_INVALID_MULTIPLE_ATTRIBUTE, strict_validation=True)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "occurs multiple times" in obj.messages.errors()[0]

        obj = rpsl_object_from_text(SAMPLE_INVALID_MULTIPLE_ATTRIBUTE, strict_validation=False)
        assert len(obj.messages.errors()) == 0, f"Unexpected extra errors: {obj.messages.errors()}"

    def test_malformed_pk(self):
        obj = rpsl_object_from_text(SAMPLE_MALFORMED_PK, strict_validation=True)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "Invalid address prefix: not-a-prefix" in obj.messages.errors()[0]

        # A primary key field should also be tested in non-strict mode
        obj = rpsl_object_from_text(SAMPLE_MALFORMED_PK, strict_validation=False)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "Invalid address prefix: not-a-prefix" in obj.messages.errors()[0]

    def test_malformed_source(self):
        obj = rpsl_object_from_text(SAMPLE_MALFORMED_SOURCE, strict_validation=False)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "contains invalid characters" in obj.messages.errors()[0]

    def test_missing_source_optional_default_source(self):
        obj = rpsl_object_from_text(SAMPLE_MISSING_SOURCE, strict_validation=False, default_source="TEST")
        assert len(obj.messages.errors()) == 0, f"Unexpected extra errors: {obj.messages.errors()}"
        assert obj.source() == "TEST"

        obj = rpsl_object_from_text(SAMPLE_MISSING_SOURCE, strict_validation=False)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert 'attribute "source" on object route is missing' in obj.messages.errors()[0]

    def test_line_neither_continuation_nor_attribute(self):
        obj = rpsl_object_from_text(SAMPLE_LINE_NEITHER_CONTINUATION_NOR_ATTR, strict_validation=False)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "line is neither continuation nor valid attribute" in obj.messages.errors()[0]

    def test_double_object_297(self):
        obj = rpsl_object_from_text(SAMPLE_ROUTE + " \n" + SAMPLE_ROUTE)
        assert len(obj.messages.errors()) == 3, f"Unexpected extra errors: {obj.messages.errors()}"
        assert 'Attribute "route" on object route occurs multiple times' in obj.messages.errors()[0]


class TestRPSLAsBlock:
    def test_has_mapping(self):
        obj = RPSLAsBlock()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLAsBlock().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLAsBlock
        assert not obj.messages.errors()
        assert obj.pk() == "AS65536 - AS65538"
        assert obj.asn_first == 65536
        assert obj.asn_last == 65538
        # Field parsing will cause our object to look slightly different than the original, hence the replace()
        assert obj.render_rpsl_text() == rpsl_text.replace("as065538", "AS65538")


class TestRPSLAsSet:
    def test_has_mapping(self):
        obj = RPSLAsSet()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLAsSet().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLAsSet
        assert obj.clean_for_create()
        assert not obj.messages.errors()
        assert obj.pk() == "AS65537:AS-SETTEST"
        assert obj.referred_strong_objects() == [
            ("admin-c", ["role", "person"], ["PERSON-TEST"]),
            ("tech-c", ["role", "person"], ["PERSON-TEST"]),
            ("mnt-by", ["mntner"], ["TEST-MNT"]),
        ]
        assert obj.references_strong_inbound() == set()
        assert obj.source() == "TEST"
        assert obj.pk_asn_segment == "AS65537"

        assert obj.parsed_data["members"] == ["AS65538", "AS65539", "AS65537", "AS-OTHERSET"]
        # Field parsing will cause our object to look slightly different than the original, hence the replace()
        assert obj.render_rpsl_text() == rpsl_text.replace("AS65538, AS65539", "AS65538,AS65539")

    def test_clean_for_create(self, config_override):
        rpsl_text = object_sample_mapping[RPSLAsSet().rpsl_object_class]
        rpsl_text = rpsl_text.replace("AS65537:AS-SETTEST", "AS-SETTEST")
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLAsSet
        assert not obj.messages.errors()
        assert not obj.clean_for_create()
        assert not obj.pk_asn_segment
        assert "as-set names must be hierarchical and the first " in obj.messages.errors()[0]

        config_override({"auth": {"set_creation": {"as-set": {"prefix_required": False}}}})
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.clean_for_create()
        assert not obj.pk_asn_segment

        config_override(
            {"auth": {"set_creation": {AUTH_SET_CREATION_COMMON_KEY: {"prefix_required": False}}}}
        )
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.clean_for_create()
        assert not obj.pk_asn_segment


class TestRPSLAutNum:
    def test_has_mapping(self):
        obj = RPSLAutNum()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLAutNum().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLAutNum
        assert not obj.messages.errors()
        assert obj.pk() == "AS65537"
        assert obj.asn_first == 65537
        assert obj.asn_last == 65537
        assert obj.ip_version() is None
        assert obj.references_strong_inbound() == set()
        # Field parsing will cause our object to look slightly different than the original, hence the replace()
        assert obj.render_rpsl_text() == rpsl_text.replace("as065537", "AS65537")


class TestRPSLDomain:
    def test_has_mapping(self):
        obj = RPSLDomain()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLDomain().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLDomain
        assert not obj.messages.errors()
        assert obj.pk() == "2.0.192.IN-ADDR.ARPA"
        assert obj.parsed_data["source"] == "TEST"
        assert obj.render_rpsl_text() == rpsl_text


class TestRPSLFilterSet:
    def test_has_mapping(self):
        obj = RPSLFilterSet()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLFilterSet().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLFilterSet
        assert not obj.messages.errors()
        assert obj.pk() == "FLTR-SETTEST"
        assert obj.render_rpsl_text() == rpsl_text.replace("\t", "+")  # #298


class TestRPSLInetRtr:
    def test_has_mapping(self):
        obj = RPSLInetRtr()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLInetRtr().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLInetRtr
        assert not obj.messages.errors()
        assert obj.pk() == "RTR.EXAMPLE.COM"
        assert obj.parsed_data["inet-rtr"] == "RTR.EXAMPLE.COM"
        assert obj.render_rpsl_text() == rpsl_text


class TestRPSLInet6Num:
    def test_has_mapping(self):
        obj = RPSLInet6Num()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLInet6Num().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLInet6Num
        assert not obj.messages.errors()
        assert obj.pk() == "2001:DB8::/48"
        assert obj.ip_first == IP("2001:db8::")
        assert obj.ip_last == IP("2001:db8::ffff:ffff:ffff:ffff:ffff")
        assert obj.ip_version() == 6
        assert obj.render_rpsl_text() == rpsl_text


class TestRPSLInetnum:
    def test_has_mapping(self):
        obj = RPSLInetnum()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLInetnum().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLInetnum
        assert not obj.messages.errors()
        assert obj.pk() == "192.0.2.0 - 192.0.2.255"
        assert obj.ip_first == IP("192.0.2.0")
        assert obj.ip_last == IP("192.0.2.255")
        assert obj.ip_version() == 4
        assert obj.references_strong_inbound() == set()
        # Field parsing will cause our object to look slightly different than the original, hence the replace()
        assert obj.render_rpsl_text() == rpsl_text.replace("192.0.02.255", "192.0.2.255")


class TestRPSLKeyCert:
    """
    The tests for KeyCert objects intentionally do not mock gnupg, meaning these
    tests call the actual gpg binary, as the test has little value when gpg is
    mocked out.
    """

    def test_has_mapping(self):
        obj = RPSLKeyCert()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    @pytest.mark.usefixtures("tmp_gpg_dir")  # noqa: F811
    def test_parse_parse(self):
        rpsl_text = object_sample_mapping[RPSLKeyCert().rpsl_object_class]

        # Mangle the fingerprint/owner/method lines to ensure the parser correctly re-generates them
        mangled_rpsl_text = rpsl_text.replace(
            "8626 1D8D BEBD A4F5 4692  D64D A838 3BA7 80F2 38C6", "fingerprint"
        )
        mangled_rpsl_text = mangled_rpsl_text.replace("sasha", "foo").replace(
            "method:         PGP", "method: test"
        )

        expected_text = rpsl_text.replace("                \n", "+               \n")  # #298
        obj = rpsl_object_from_text(mangled_rpsl_text)
        assert obj.__class__ == RPSLKeyCert
        assert not obj.messages.errors()
        assert obj.pk() == "PGPKEY-80F238C6"
        assert obj.render_rpsl_text() == expected_text
        assert obj.parsed_data["fingerpr"] == "8626 1D8D BEBD A4F5 4692  D64D A838 3BA7 80F2 38C6"

    @pytest.mark.usefixtures("tmp_gpg_dir")  # noqa: F811
    def test_parse_incorrect_object_name(self, tmp_gpg_dir):
        rpsl_text = object_sample_mapping[RPSLKeyCert().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text.replace("PGPKEY-80F238C6", "PGPKEY-80F23816"))

        errors = obj.messages.errors()
        assert len(errors) == 1, f"Unexpected multiple errors: {errors}"
        assert "does not match key fingerprint" in errors[0]

    @pytest.mark.usefixtures("tmp_gpg_dir")  # noqa: F811
    def test_parse_missing_key(self, tmp_gpg_dir):
        rpsl_text = object_sample_mapping[RPSLKeyCert().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text.replace("certif:", "remarks:"), strict_validation=True)

        errors = obj.messages.errors()
        assert len(errors) == 1, f"Unexpected multiple errors: {errors}"
        assert 'Mandatory attribute "certif" on object key-cert is missing' in errors[0]

    @pytest.mark.usefixtures("tmp_gpg_dir")  # noqa: F811
    def test_parse_invalid_key(self, tmp_gpg_dir):
        rpsl_text = object_sample_mapping[RPSLKeyCert().rpsl_object_class]
        obj = rpsl_object_from_text(
            rpsl_text.replace("mQINBFnY7YoBEADH5ooPsoR9G", "foo"), strict_validation=True
        )

        errors = obj.messages.errors()
        assert len(errors) == 1, f"Unexpected multiple errors: {errors}"
        assert "Unable to read public PGP key: key corrupt or multiple keys provided" in errors[0]

    @pytest.mark.usefixtures("tmp_gpg_dir")  # noqa: F811
    def test_verify(self, tmp_gpg_dir):
        rpsl_text = object_sample_mapping[RPSLKeyCert().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)

        assert obj.verify(KEY_CERT_SIGNED_MESSAGE_VALID)
        assert not obj.verify(KEY_CERT_SIGNED_MESSAGE_INVALID)
        assert not obj.verify(KEY_CERT_SIGNED_MESSAGE_CORRUPT)
        assert not obj.verify(KEY_CERT_SIGNED_MESSAGE_WRONG_KEY)


class TestRPSLMntner:
    def test_has_mapping(self):
        obj = RPSLMntner()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self, config_override):
        config_override({"auth": {"password_hashers": {"crypt-pw": "enabled"}}})
        rpsl_text = object_sample_mapping[RPSLMntner().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLMntner

        assert not obj.messages.errors()
        assert obj.pk() == "TEST-MNT"
        assert obj.parsed_data["mnt-by"] == ["TEST-MNT", "OTHER1-MNT", "OTHER2-MNT"]
        assert obj.render_rpsl_text() == rpsl_text
        assert obj.references_strong_inbound() == {"mnt-by"}

    def test_parse_invalid_partial_dummy_hash(self, config_override):
        config_override({"auth": {"password_hashers": {"crypt-pw": "enabled"}}})
        rpsl_text = object_sample_mapping[RPSLMntner().rpsl_object_class]
        rpsl_text = rpsl_text.replace("LEuuhsBJNFV0Q", PASSWORD_HASH_DUMMY_VALUE)
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLMntner
        assert obj.messages.errors() == [
            "Either all password auth hashes in a submitted mntner must be dummy objects, or none."
        ]

    @pytest.mark.usefixtures("tmp_gpg_dir")  # noqa: F811
    def test_verify(self, tmp_gpg_dir):
        rpsl_text = object_sample_mapping[RPSLMntner().rpsl_object_class]
        # Unknown hashes and invalid hashes should simply be ignored.
        # Strict validation set to False to allow legacy mode for CRYPT-PW
        obj = rpsl_object_from_text(
            rpsl_text + "auth: UNKNOWN_HASH foo\nauth: MD5-PW 💩", strict_validation=False
        )

        assert obj.verify_auth(["crypt-password"])
        assert obj.verify_auth(["md5-password"])
        assert obj.verify_auth(["bcrypt-password"])
        assert obj.verify_auth(["md5-password"], "PGPKey-80F238C6")
        assert not obj.verify_auth(["other-password"])
        assert not obj.verify_auth([KEY_CERT_SIGNED_MESSAGE_CORRUPT])
        assert not obj.verify_auth([KEY_CERT_SIGNED_MESSAGE_WRONG_KEY])


class TestRPSLPeeringSet:
    def test_has_mapping(self):
        obj = RPSLPeeringSet()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLPeeringSet().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLPeeringSet
        assert not obj.messages.errors()
        assert obj.pk() == "PRNG-SETTEST"
        assert obj.parsed_data["tech-c"] == ["PERSON-TEST", "DUMY2-TEST"]
        assert obj.render_rpsl_text() == rpsl_text


class TestRPSLPerson:
    def test_has_mapping(self):
        obj = RPSLPerson()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLPerson().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLPerson
        assert not obj.messages.errors()
        assert obj.pk() == "PERSON-TEST"
        assert obj.parsed_data["nic-hdl"] == "PERSON-TEST"
        assert obj.render_rpsl_text() == rpsl_text
        assert obj.references_strong_inbound() == {"admin-c", "tech-c", "zone-c"}

    def test_generate_template(self):
        template = RPSLPerson().generate_template()
        assert template == TEMPLATE_PERSON_OBJECT


class TestRPSLRole:
    def test_has_mapping(self):
        obj = RPSLRole()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLRole().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLRole
        assert not obj.messages.errors()
        assert obj.pk() == "ROLE-TEST"
        assert obj.render_rpsl_text() == rpsl_text
        assert obj.references_strong_inbound() == {"admin-c", "tech-c", "zone-c"}


class TestRPSLRoute:
    def test_has_mapping(self):
        obj = RPSLRoute()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLRoute().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLRoute
        assert not obj.messages.errors()
        assert obj.pk() == "192.0.2.0/24AS65537"
        assert obj.ip_first == IP("192.0.2.0")
        assert obj.ip_last == IP("192.0.2.255")
        assert obj.prefix == IP("192.0.2.0/24")
        assert obj.prefix_length == 24
        assert obj.asn_first == 65537
        assert obj.asn_last == 65537
        assert obj.ip_version() == 4
        assert obj.references_strong_inbound() == set()

        expected_text = rpsl_text.replace("  192.0.02.0/24", "  192.0.2.0/24")
        expected_text = expected_text.replace("rpki-ov-state: valid  # should be discarded\n", "")
        assert obj.render_rpsl_text() == expected_text

    def test_missing_pk_nonstrict(self):
        # In non-strict mode, the parser should not fail validation for missing
        # attributes, except for those part of the PK. Route is one of the few
        # objects that has two PK attributes.
        missing_pk_route = "route: 192.0.2.0/24"
        obj = rpsl_object_from_text(missing_pk_route, strict_validation=False)
        assert obj.__class__ == RPSLRoute
        errors = obj.messages.errors()
        assert len(errors) == 2, f"Unexpected extra errors: {errors}"
        assert 'Primary key attribute "origin" on object route is missing' in errors[0]
        assert 'Primary key attribute "source" on object route is missing' in errors[1]

    def test_generate_template(self):
        template = RPSLRoute().generate_template()
        assert template == TEMPLATE_ROUTE_OBJECT


class TestRPSLRouteSet:
    def test_has_mapping(self):
        obj = RPSLRouteSet()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLRouteSet().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLRouteSet
        assert not obj.messages.errors()
        assert obj.pk() == "RS-TEST"
        assert obj.parsed_data["mp-members"] == ["2001:db8::/48"]
        assert obj.render_rpsl_text() == rpsl_text.replace("2001:0dB8::/48", "2001:db8::/48")
        assert obj.references_strong_inbound() == set()


class TestRPSLRoute6:
    def test_has_mapping(self):
        obj = RPSLRoute6()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLRoute6().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLRoute6
        assert not obj.messages.errors()
        assert obj.pk() == "2001:DB8::/48AS65537"
        assert obj.ip_first == IP("2001:db8::")
        assert obj.ip_last == IP("2001:db8::ffff:ffff:ffff:ffff:ffff")
        assert obj.prefix == IP("2001:db8::/48")
        assert obj.prefix_length == 48
        assert obj.asn_first == 65537
        assert obj.asn_last == 65537
        assert obj.ip_version() == 6
        assert obj.parsed_data["mnt-by"] == ["TEST-MNT"]
        assert obj.render_rpsl_text() == rpsl_text
        assert obj.references_strong_inbound() == set()


class TestRPSLRtrSet:
    def test_has_mapping(self):
        obj = RPSLRtrSet()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLRtrSet().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLRtrSet
        assert not obj.messages.errors()
        assert obj.pk() == "RTRS-SETTEST"
        assert obj.parsed_data["rtr-set"] == "RTRS-SETTEST"
        assert obj.referred_strong_objects() == [
            ("admin-c", ["role", "person"], ["PERSON-TEST"]),
            ("tech-c", ["role", "person"], ["PERSON-TEST"]),
            ("mnt-by", ["mntner"], ["TEST-MNT"]),
        ]
        assert obj.references_strong_inbound() == set()
        assert obj.render_rpsl_text() == rpsl_text


class TestLastModified:
    def test_authoritative(self, config_override):
        config_override({"sources": {"TEST": {"authoritative": True}}})
        rpsl_text = object_sample_mapping[RPSLRtrSet().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text + "last-modified: old-value\n")
        assert not obj.messages.errors()
        last_modified = datetime.datetime(2020, 1, 1, tzinfo=timezone("UTC"))
        expected_text = rpsl_text + "last-modified:  2020-01-01T00:00:00Z\n"
        assert obj.render_rpsl_text(last_modified=last_modified) == expected_text

    def test_not_authoritative(self):
        rpsl_text = object_sample_mapping[RPSLRtrSet().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text + "last-modified: old-value\n")
        assert not obj.messages.errors()
        last_modified = datetime.datetime(2020, 1, 1, tzinfo=timezone("UTC"))
        expected_text = rpsl_text + "last-modified:  old-value\n"
        assert obj.render_rpsl_text(last_modified=last_modified) == expected_text
