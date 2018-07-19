import pytest
from IPy import IP
from pytest import raises

from irrd.utils.rpsl_samples import (object_sample_mapping, SAMPLE_MALFORMED_EMPTY_LINE, SAMPLE_MALFORMED_ATTRIBUTE_NAME,
                                     SAMPLE_UNKNOWN_CLASS, SAMPLE_MISSING_MANDATORY_ATTRIBUTE, SAMPLE_MALFORMED_SOURCE,
                                     SAMPLE_MALFORMED_PK, SAMPLE_UNKNOWN_ATTRIBUTE, SAMPLE_INVALID_MULTIPLE_ATTRIBUTE,
                                     KEY_CERT_SIGNED_MESSAGE_VALID, KEY_CERT_SIGNED_MESSAGE_INVALID,
                                     KEY_CERT_SIGNED_MESSAGE_CORRUPT, KEY_CERT_SIGNED_MESSAGE_WRONG_KEY, TEMPLATE_ROUTE_OBJECT,
                                     TEMPLATE_PERSON_OBJECT)
from ..parser import UnknownRPSLObjectClassException
from ..rpsl_objects import (RPSLAsBlock, RPSLAsSet, RPSLAutNum, RPSLDictionary, RPSLDomain, RPSLFilterSet, RPSLInetRtr,
                            RPSLInet6Num, RPSLInetnum, RPSLKeyCert, RPSLLimerick, RPSLMntner, RPSLPeeringSet,
                            RPSLPerson, RPSLRepository, RPSLRole, RPSLRoute, RPSLRouteSet, RPSLRoute6, RPSLRtrSet,
                            OBJECT_CLASS_MAPPING, rpsl_object_from_text)


@pytest.fixture()
def tmp_gpg_dir(tmpdir, monkeypatch):
    """
    Fixture to use a temporary separate gpg dir, to prevent it using your
    user's keyring.

    NOTE: if the gpg homedir name is very long, this introduces a 5 second
    delay in all gpg tests due to gpg incorrectly waiting to find a gpg-agent.
    Default tmpdirs on Mac OS X are affected, to prevent this run pytest with:
        --basetemp=.tmpdirs
    """
    def gpg_dir(self):
        return str(tmpdir) + "/gnupg"
    monkeypatch.setattr(RPSLKeyCert, "gpg_dir", gpg_dir)


class TestRPSLParsingGeneric:
    # Most malformed objects are tested without strict validation, as they should always fail.
    def test_unknown_class(self):
        with raises(UnknownRPSLObjectClassException) as ve:
            rpsl_object_from_text(SAMPLE_UNKNOWN_CLASS)
        assert "unknown object class" in str(ve)

    def test_malformed_empty_line(self):
        obj = rpsl_object_from_text(SAMPLE_MALFORMED_EMPTY_LINE, strict_validation=False)
        assert len(obj.messages.errors()) == 2, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "encountered empty line" in obj.messages.errors()[0]

    def test_malformed_attribute_name(self):
        obj = rpsl_object_from_text(SAMPLE_MALFORMED_ATTRIBUTE_NAME, strict_validation=False)
        assert len(obj.messages.errors()) == 2, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "malformed attribute name" in obj.messages.errors()[0]

    def test_missing_mandatory_attribute(self):
        obj = rpsl_object_from_text(SAMPLE_MISSING_MANDATORY_ATTRIBUTE, strict_validation=True)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "Mandatory attribute 'tech-c' on object as-block is missing" in obj.messages.errors()[0]

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
        assert "Invalid AS number" in obj.messages.errors()[0]

        # A primary key field should also be tested in non-strict mode
        obj = rpsl_object_from_text(SAMPLE_MALFORMED_PK, strict_validation=False)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "Invalid AS number" in obj.messages.errors()[0]

    def test_malformed_source(self):
        obj = rpsl_object_from_text(SAMPLE_MALFORMED_SOURCE, strict_validation=False)
        assert len(obj.messages.errors()) == 1, f"Unexpected extra errors: {obj.messages.errors()}"
        assert "contains invalid characters" in obj.messages.errors()[0]


class TestRPSLAsBlock:
    def test_has_mapping(self):
        obj = RPSLAsBlock()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLAsBlock().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLAsBlock
        assert not obj.messages.errors()
        assert obj.pk() == "AS2043 - AS2043"
        assert obj.asn_first == 2043
        assert obj.asn_last == 2043
        # Field parsing will cause our object to look slightly different than the original, hence the replace()
        assert obj.render_rpsl_text() == rpsl_text.replace("as02043", "AS2043")


class TestRPSLAsSet:
    def test_has_mapping(self):
        obj = RPSLAsSet()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLAsSet().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLAsSet
        assert not obj.messages.errors()
        assert obj.pk() == "AS-RESTENA"
        assert obj.referred_objects() == [
            ('members', ['aut-num', 'as-set'], ['AS2602', 'AS42909', 'AS51966', 'AS49624']),
            ('admin-c', ['role', 'person'], ['DUMY-RIPE']),
            ('tech-c', ['role', 'person'], ['DUMY-RIPE']),
            ('mnt-by', ['mntner'], ['AS2602-MNT'])
        ]
        assert obj.source() == 'RIPE'

        assert obj.parsed_data['members'] == ['AS2602', 'AS42909', 'AS51966', 'AS49624']
        # Field parsing will cause our object to look slightly different than the original, hence the replace()
        assert obj.render_rpsl_text() == rpsl_text.replace("AS2602, AS42909, AS51966", "AS2602,AS42909,AS51966")


class TestRPSLAutNum:
    def test_has_mapping(self):
        obj = RPSLAutNum()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLAutNum().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLAutNum
        assert not obj.messages.errors()
        assert obj.pk() == "AS3255"
        assert obj.asn_first == 3255
        assert obj.asn_last == 3255
        assert obj.ip_version() is None
        # Field parsing will cause our object to look slightly different than the original, hence the replace()
        assert obj.render_rpsl_text() == rpsl_text.replace("as03255", "AS3255")


class TestRPSLDictionary:
    def test_has_mapping(self):
        obj = RPSLDictionary()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__


class TestRPSLDomain:
    def test_has_mapping(self):
        obj = RPSLDomain()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLDomain().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLDomain
        assert not obj.messages.errors()
        assert obj.pk() == "200.193.193.IN-ADDR.ARPA"
        assert obj.parsed_data["source"] == 'RIPE'
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
        assert obj.pk() == "FLTR-BOGONS-INTEGRA-IT"
        assert obj.render_rpsl_text() == rpsl_text


class TestRPSLInetRtr:
    def test_has_mapping(self):
        obj = RPSLInetRtr()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLInetRtr().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLInetRtr
        assert not obj.messages.errors()
        assert obj.pk() == "KST1-CORE.SWIP.NET"
        assert obj.parsed_data['inet-rtr'] == "KST1-CORE.SWIP.NET"
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
        assert obj.pk() == "2001:638:501::/48"
        assert obj.ip_first == IP("2001:638:501::")
        assert obj.ip_last == IP("2001:638:501:ffff:ffff:ffff:ffff:ffff")
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
        assert obj.pk() == "80.16.151.184 - 80.16.151.191"
        assert obj.ip_first == IP("80.16.151.184")
        assert obj.ip_last == IP("80.16.151.191")
        assert obj.ip_version() == 4
        # Field parsing will cause our object to look slightly different than the original, hence the replace()
        assert obj.render_rpsl_text() == rpsl_text.replace("80.016.151.191", "80.16.151.191")


class TestRPSLKeyCert:
    """
    The tests for KeyCert objects intentionally do not mock gnupg, meaning these
    tests call the actual gpg binary, as the test has little value when gpg is
    mocked out.
    """
    def test_has_mapping(self):
        obj = RPSLKeyCert()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse_parse(self, tmp_gpg_dir):
        rpsl_text = object_sample_mapping[RPSLKeyCert().rpsl_object_class]

        # Mangle the fingerprint/owner/method lines to ensure the parser correctly re-generates them
        mangled_rpsl_text = rpsl_text.replace("8626 1D8D BEBD A4F5 4692  D64D A838 3BA7 80F2 38C6", "fingerprint")
        mangled_rpsl_text = mangled_rpsl_text.replace("sasha", "foo").replace("method:         PGP", "method: test")

        obj = rpsl_object_from_text(mangled_rpsl_text)
        assert obj.__class__ == RPSLKeyCert
        assert not obj.messages.errors()
        assert obj.pk() == "PGPKEY-80F238C6"
        assert obj.render_rpsl_text() == rpsl_text

    def test_parse_incorrect_object_name(self, tmp_gpg_dir):
        rpsl_text = object_sample_mapping[RPSLKeyCert().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text.replace("PGPKEY-80F238C6", "PGPKEY-80F23816"))

        errors = obj.messages.errors()
        assert len(errors) == 1, f"Unexpected multiple errors: {errors}"
        assert "does not match key fingerprint" in errors[0]

    def test_parse_missing_key(self, tmp_gpg_dir):
        rpsl_text = object_sample_mapping[RPSLKeyCert().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text.replace("certif:", "remarks:"), strict_validation=True)

        errors = obj.messages.errors()
        assert len(errors) == 2, f"Unexpected multiple errors: {errors}"
        assert "Mandatory attribute 'certif' on object key-cert is missing" in errors[0]
        assert "No valid data found" in errors[1]

    def test_verify(self, tmp_gpg_dir):
        rpsl_text = object_sample_mapping[RPSLKeyCert().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)

        assert obj.verify(KEY_CERT_SIGNED_MESSAGE_VALID)
        assert not obj.verify(KEY_CERT_SIGNED_MESSAGE_INVALID)
        assert not obj.verify(KEY_CERT_SIGNED_MESSAGE_CORRUPT)
        assert not obj.verify(KEY_CERT_SIGNED_MESSAGE_WRONG_KEY)


class TestRPSLLimerick:
    def test_has_mapping(self):
        obj = RPSLLimerick()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__


class TestRPSLMntner:
    def test_has_mapping(self):
        obj = RPSLMntner()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLMntner().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLMntner
        assert not obj.messages.errors()
        assert obj.pk() == "AS760-MNT"
        assert obj.parsed_data["mnt-by"] == ['AS760-MNT', 'ACONET-LIR-MNT', 'ACONET2-LIR-MNT']
        assert obj.render_rpsl_text() == rpsl_text

    def test_verify(self, tmp_gpg_dir):
        rpsl_text = object_sample_mapping[RPSLMntner().rpsl_object_class]
        # Unknown hashes should simply be ignored.
        obj = rpsl_object_from_text(rpsl_text + "auth: UNKNOWN_HASH foo")

        assert obj.verify("crypt-password")
        assert obj.verify("md5-password")
        assert not obj.verify("other-password")
        assert not obj.verify(KEY_CERT_SIGNED_MESSAGE_CORRUPT)
        assert not obj.verify(KEY_CERT_SIGNED_MESSAGE_WRONG_KEY)


class TestRPSLPeeringSet:
    def test_has_mapping(self):
        obj = RPSLPeeringSet()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLPeeringSet().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLPeeringSet
        assert not obj.messages.errors()
        assert obj.pk() == "PRNG-MEDIAFAX"
        assert obj.parsed_data['tech-c'] == "DUMY-RIPE\nDUMY2-RIPE"
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
        assert obj.pk() == "DUMY-RIPE"
        assert obj.parsed_data['nic-hdl'] == "DUMY-RIPE"
        assert obj.render_rpsl_text() == rpsl_text

    def test_generate_template(self):
        template = RPSLPerson().generate_template()
        assert template == TEMPLATE_PERSON_OBJECT


class TestRPSLRepository:
    def test_has_mapping(self):
        obj = RPSLRepository()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__


class TestRPSLRole:
    def test_has_mapping(self):
        obj = RPSLRole()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLRole().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLRole
        assert not obj.messages.errors()
        assert obj.pk() == "BISP-RIPE"
        assert obj.render_rpsl_text() == rpsl_text


class TestRPSLRoute:
    def test_has_mapping(self):
        obj = RPSLRoute()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLRoute().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLRoute
        assert not obj.messages.errors()
        assert obj.pk() == "193.254.30.0/24,AS12726"
        assert obj.ip_first == IP("193.254.30.0")
        assert obj.ip_last == IP("193.254.30.255")
        assert obj.asn_first == 12726
        assert obj.asn_last == 12726
        assert obj.ip_version() == 4
        # Field parsing will cause our object to look slightly different than the original, hence the replace()
        assert obj.render_rpsl_text() == rpsl_text.replace("193.254.030.00/24", "193.254.30.0/24")

    def test_missing_pk_nonstrict(self):
        # In non-strict mode, the parser should not fail validation for missing
        # attributes, except for those part of the PK. Route is one of the few
        # objects that has two PK attributes.
        missing_pk_route = "route: 192.0.2.0/24"
        obj = rpsl_object_from_text(missing_pk_route, strict_validation=False)
        assert obj.__class__ == RPSLRoute
        errors = obj.messages.errors()
        assert len(errors) == 2, f"Unexpected extra errors: {errors}"
        assert "Primary key attribute 'origin' on object route is missing" in errors[0]
        assert "Primary key attribute 'source' on object route is missing" in errors[1]

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
        assert obj.render_rpsl_text() == rpsl_text


class TestRPSLRoute6:
    def test_has_mapping(self):
        obj = RPSLRoute6()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLRoute6().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLRoute6
        assert not obj.messages.errors()
        assert obj.pk() == "2001:1578:200::/40,AS12817"
        assert obj.ip_first == IP("2001:1578:200::")
        assert obj.ip_last == IP("2001:1578:2ff:ffff:ffff:ffff:ffff:ffff")
        assert obj.asn_first == 12817
        assert obj.asn_last == 12817
        assert obj.ip_version() == 6
        assert obj.parsed_data['mnt-by'] == ['EXAMPLE-MNT']
        assert obj.render_rpsl_text() == rpsl_text


class TestRPSLRtrSet:
    def test_has_mapping(self):
        obj = RPSLRtrSet()
        assert OBJECT_CLASS_MAPPING[obj.rpsl_object_class] == obj.__class__

    def test_parse(self):
        rpsl_text = object_sample_mapping[RPSLRtrSet().rpsl_object_class]
        obj = rpsl_object_from_text(rpsl_text)
        assert obj.__class__ == RPSLRtrSet
        assert not obj.messages.errors()
        assert obj.pk() == "RTRS-MWAYS-CALLBACK"
        assert obj.parsed_data['rtr-set'] == "RTRS-MWAYS-CALLBACK"
        assert obj.render_rpsl_text() == rpsl_text
