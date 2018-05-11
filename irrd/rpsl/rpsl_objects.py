from collections import OrderedDict

import gnupg

from .config import PASSWORD_HASHERS
from .fields import (RPSLTextField, RPSLIPv4PrefixField, RPSLIPv4PrefixesField, RPSLIPv6PrefixField,
                     RPSLIPv6PrefixesField, RPSLIPv4AddressRangeField, RPSLASNumberField, RPSLASBlockField,
                     RPSLSetNameField, RPSLEmailField, RPSLDNSNameField, RPSLGenericNameField, RPSLReferenceField,
                     RPSLReferenceListField, RPSLAuthField)
from .parser import RPSLObject, UnknownRPSLObjectClassException


def rpsl_object_from_text(text, strict_validation=True):
    rpsl_object_class = text.split(":", maxsplit=1)[0].strip()
    try:
        klass = OBJECT_CLASS_MAPPING[rpsl_object_class]
    except KeyError:
        raise UnknownRPSLObjectClassException(f"Encountered unknown object class: {rpsl_object_class}")
    return klass(from_text=text, strict_validation=strict_validation)


class RPSLAsBlock(RPSLObject):
    fields = OrderedDict([
        ("as-block", RPSLASBlockField(primary_key=True, lookup_key=True)),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("admin-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLAsSet(RPSLObject):
    fields = OrderedDict([
        ("as-set", RPSLSetNameField(primary_key=True, lookup_key=True, prefix="AS")),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("members", RPSLReferenceListField(optional=True, multiple=True, referring=["aut-num", "as-set"])),
        ("mbrs-by-ref", RPSLReferenceListField(optional=True, multiple=True, referring=["mntner"], allow_kw_any=True)),
        ("admin-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLAutNum(RPSLObject):
    fields = OrderedDict([
        ("aut-num", RPSLASNumberField(primary_key=True, lookup_key=True)),
        ("as-name", RPSLGenericNameField(allowed_prefixes=["AS"])),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("member-of", RPSLReferenceListField(optional=True, multiple=True, referring=["as-set"])),
        ("import", RPSLTextField(optional=True, multiple=True)),
        ("mp-import", RPSLTextField(optional=True, multiple=True)),
        ("import-via", RPSLTextField(optional=True, multiple=True)),
        ("export", RPSLTextField(optional=True, multiple=True)),
        ("mp-export", RPSLTextField(optional=True, multiple=True)),
        ("export-via", RPSLTextField(optional=True, multiple=True)),
        ("default", RPSLTextField(optional=True, multiple=True)),
        ("mp-default", RPSLTextField(optional=True, multiple=True)),
        ("admin-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(optional=True, multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLDictionary(RPSLObject):
    fields = OrderedDict([
        ("dictionary", RPSLGenericNameField(primary_key=True, lookup_key=True)),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("admin-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("typedef", RPSLTextField(optional=True, multiple=True)),
        ("rp-attribute", RPSLTextField(optional=True, multiple=True)),
        ("protocol", RPSLTextField(optional=True, multiple=True)),
        ("afi", RPSLTextField(optional=True, multiple=True)),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLDomain(RPSLObject):
    fields = OrderedDict([
        ("domain", RPSLTextField(primary_key=True, lookup_key=True)),  # reverse delegation address (range), v4/v6/enum
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("admin-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("zone-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("nserver", RPSLTextField(optional=True, multiple=True)),  # DNS name, possibly followed v4/v6
        ("sub-dom", RPSLTextField(optional=True, multiple=True)),
        ("dom-net", RPSLTextField(optional=True, multiple=True)),
        ("refer", RPSLTextField(optional=True)),  # ???
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(optional=True, multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLFilterSet(RPSLObject):
    fields = OrderedDict([
        ("filter-set", RPSLSetNameField(primary_key=True, lookup_key=True, prefix="FLTR")),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("filter", RPSLTextField()),
        ("mp-filter", RPSLTextField(optional=True)),
        ("admin-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLInetRtr(RPSLObject):
    fields = OrderedDict([
        ("inet-rtr", RPSLDNSNameField(primary_key=True, lookup_key=True)),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("alias", RPSLDNSNameField(optional=True, multiple=True)),
        ("local-as", RPSLASNumberField()),
        ("ifaddr", RPSLTextField(optional=True, multiple=True)),
        ("interface", RPSLTextField(optional=True, multiple=True)),
        ("peer", RPSLTextField(optional=True, multiple=True)),
        ("mp-peer", RPSLTextField(optional=True, multiple=True)),
        ("member-of", RPSLReferenceListField(optional=True, multiple=True, referring=["rtr-set"])),
        ("rs-in", RPSLTextField(optional=True)),
        ("rs-out", RPSLTextField(optional=True)),
        ("admin-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLInet6Num(RPSLObject):
    fields = OrderedDict([
        ("inet6num", RPSLIPv6PrefixField(primary_key=True, lookup_key=True)),
        ("netname", RPSLTextField()),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("country", RPSLTextField(multiple=True)),
        ("admin-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("rev-srv", RPSLTextField(optional=True, multiple=True)),
        ("status", RPSLTextField()),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLInetnum(RPSLObject):
    fields = OrderedDict([
        ("inetnum", RPSLIPv4AddressRangeField(primary_key=True, lookup_key=True)),
        ("netname", RPSLTextField()),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("country", RPSLTextField(multiple=True)),
        ("admin-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("rev-srv", RPSLTextField(optional=True, multiple=True)),
        ("status", RPSLTextField()),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLKeyCert(RPSLObject):
    fields = OrderedDict([
        ("key-cert", RPSLGenericNameField(primary_key=True, lookup_key=True)),
        ("method", RPSLTextField(optional=True)),  # Fixed to PGP
        ("owner", RPSLTextField(optional=True, multiple=True)),  # key owner, autogenerate
        ("fingerpr", RPSLTextField(optional=True)),  # fingerprint, autogenerate
        ("certif", RPSLTextField(multiple=True)),  # Actual key
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("admin-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])

    def clean(self) -> bool:
        """
        Validate the PGP key and update relevant attributes.

        In key-cert objects, the method, owner and fingerpr objects should be
        auto-generated based on the certif object. The certif object should be
        a valid PGP key, matching the ID in the primary key.

        Note that the PGP key is imported into the keyring every time this is
        called - this is intentional, to decouple the RPSL database state from
        the gpg keyring state.
        """
        if not super().clean():
            return False  # pragma: no cover

        gpg = gnupg.GPG(gnupghome=self.gpg_dir())
        result = gpg.import_keys(self.cleaned_data.get("certif", ""))

        if len(result.fingerprints) != 1:
            msg = f"Unable to read public PGP key: key corrupt or multiple keys provided"
            if result.results:
                msg = f"{msg}: {result.results[0]['text']}"
            self.messages.error(msg)
            return False

        self.fingerprint = result.fingerprints[0]
        expected_object_name = "PGPKEY-" + self.fingerprint[-8:]
        actual_object_name = self.cleaned_data["key-cert"].upper()
        fingerprint_formatted = self.format_fingerprint(self.fingerprint)

        if expected_object_name != actual_object_name:
            self.messages.error(
                f"Invalid object name {actual_object_name}: does not match key fingerprint {fingerprint_formatted}, "
                f"expected object name {expected_object_name}"
            )
            return False

        self._update_attribute_value("fingerpr", fingerprint_formatted)
        self._update_attribute_value("owner", gpg.list_keys(keys=self.fingerprint)[0]["uids"])
        self._update_attribute_value("method", "PGP")

        return True

    # This API is correct, but not very practical.
    # In typical cases, the PGP key used to sign a message is not known until
    # the PGP signature is actually parsed. More useful is a generic method to find
    # which key signed a message, which can then be stored and compared to key-cert's later.
    # This method will probably be extracted to the update handler.
    def verify(self, message: str) -> bool:
        gpg = gnupg.GPG(gnupghome=self.gpg_dir())
        result = gpg.verify(message)
        return result.valid and result.key_status is None and result.fingerprint == self.fingerprint

    def gpg_dir(self) -> str:  # pragma: no cover
        return "gnupg"

    @staticmethod
    def format_fingerprint(fingerprint: str) -> str:
        string_parts = []
        for idx in range(0, 40, 4):
            string_parts.append(fingerprint[idx:idx + 4])
            if idx == 16:
                string_parts.append("")
        return " ".join(string_parts)


class RPSLLimerick(RPSLObject):
    fields = OrderedDict([
        ("limerick", RPSLTextField(primary_key=True, lookup_key=True)),  # ????
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("text", RPSLTextField(multiple=True)),
        ("admin-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("author", RPSLTextField(multiple=True)),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLMntner(RPSLObject):
    fields = OrderedDict([
        ("mntner", RPSLGenericNameField(primary_key=True, lookup_key=True)),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("admin-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("upd-to", RPSLEmailField(multiple=True)),
        ("mnt-nfy", RPSLEmailField(optional=True, multiple=True)),
        ("auth", RPSLAuthField(multiple=True)),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])

    def verify(self, password: str) -> bool:
        """
        Verify whether a given password meets any of the auth hashes in this object.
        Currently ignores PGP keys.
        """
        for auth in self.cleaned_data.get("auth", "").splitlines():
            if " " not in auth:
                continue
            scheme, hash = auth.split(" ", 1)
            hasher = PASSWORD_HASHERS.get(scheme.upper())
            if hasher and hasher.verify(password, hash):
                return True
        return False


class RPSLPeeringSet(RPSLObject):
    fields = OrderedDict([
        ("peering-set", RPSLSetNameField(primary_key=True, lookup_key=True, prefix="PRNG")),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("peering", RPSLTextField(optional=True, multiple=True)),
        ("mp-peering", RPSLTextField(optional=True, multiple=True)),
        ("admin-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLPerson(RPSLObject):
    fields = OrderedDict([
        ("person", RPSLTextField(lookup_key=True)),
        ("address", RPSLTextField(multiple=True)),
        ("phone", RPSLTextField(multiple=True)),
        ("fax-no", RPSLTextField(optional=True, multiple=True)),
        ("e-mail", RPSLEmailField(multiple=True)),
        ("nic-hdl", RPSLGenericNameField(primary_key=True, lookup_key=True)),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLRepository(RPSLObject):
    fields = OrderedDict([
        ("repository", RPSLGenericNameField(primary_key=True, lookup_key=True)),
        ("query-address", RPSLTextField(multiple=True)),
        ("response-auth-type", RPSLTextField(multiple=True)),
        ("submit-address", RPSLTextField(multiple=True)),
        ("submit-auth-type", RPSLTextField(multiple=True)),
        ("repository-cert", RPSLTextField(multiple=True)),
        ("expire", RPSLTextField()),
        ("heartbeat-interval", RPSLTextField()),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("admin-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(multiple=True, referring=["role", "person"])),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLRole(RPSLObject):
    fields = OrderedDict([
        ("role", RPSLTextField(lookup_key=True)),
        ("trouble", RPSLTextField(optional=True, multiple=True)),
        ("address", RPSLTextField(multiple=True)),
        ("phone", RPSLTextField(multiple=True)),
        ("fax-no", RPSLTextField(optional=True, multiple=True)),
        ("e-mail", RPSLEmailField(multiple=True)),
        ("admin-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("nic-hdl", RPSLGenericNameField(primary_key=True, lookup_key=True)),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLRoute(RPSLObject):
    fields = OrderedDict([
        ("route", RPSLIPv4PrefixField(primary_key=True, lookup_key=True)),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("origin", RPSLASNumberField(primary_key=True)),
        ("holes", RPSLIPv4PrefixesField(optional=True, multiple=True)),
        ("member-of", RPSLReferenceListField(optional=True, multiple=True, referring=["route-set"])),
        ("inject", RPSLTextField(optional=True, multiple=True)),
        ("aggr-bndry", RPSLTextField(optional=True)),
        ("aggr-mtd", RPSLTextField(optional=True)),
        ("export-comps", RPSLTextField(optional=True)),
        ("components", RPSLTextField(optional=True)),
        ("admin-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("geoidx", RPSLTextField(optional=True, multiple=True)),
        ("roa-uri", RPSLTextField(optional=True)),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLRouteSet(RPSLObject):
    fields = OrderedDict([
        ("route-set", RPSLSetNameField(primary_key=True, lookup_key=True, prefix="RS")),
        ("members", RPSLTextField(optional=True, multiple=True)),  # ipv4 prefix list, route set name, range operator
        ("mp-members", RPSLTextField(optional=True, multiple=True)),  # ipv6 prefix list, route set name, range operator
        ("mbrs-by-ref", RPSLReferenceListField(optional=True, multiple=True, referring=["mntner"], allow_kw_any=True)),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("admin-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLRoute6(RPSLObject):
    fields = OrderedDict([
        ("route6", RPSLIPv6PrefixField(primary_key=True, lookup_key=True)),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("origin", RPSLASNumberField(primary_key=True)),
        ("holes", RPSLIPv6PrefixesField(optional=True, multiple=True)),
        ("member-of", RPSLReferenceListField(optional=True, multiple=True, referring=["route-set"])),
        ("inject", RPSLTextField(optional=True, multiple=True)),
        ("aggr-bndry", RPSLTextField(optional=True)),
        ("aggr-mtd", RPSLTextField(optional=True)),
        ("export-comps", RPSLTextField(optional=True)),
        ("components", RPSLTextField(optional=True)),
        ("admin-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("geoidx", RPSLTextField(optional=True, multiple=True)),
        ("roa-uri", RPSLTextField(optional=True)),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


class RPSLRtrSet(RPSLObject):
    fields = OrderedDict([
        ("rtr-set", RPSLSetNameField(primary_key=True, lookup_key=True, prefix="RTRS")),
        ("descr", RPSLTextField(multiple=True, optional=True)),
        ("members", RPSLReferenceListField(optional=True, multiple=True, referring=["inet-rtr"])),
        ("mp-members", RPSLReferenceListField(optional=True, multiple=True, referring=["inet-rtr"])),
        ("mbrs-by-ref", RPSLReferenceListField(optional=True, multiple=True, referring=["mntner"], allow_kw_any=True)),
        ("admin-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("tech-c", RPSLReferenceField(optional=True, multiple=True, referring=["role", "person"])),
        ("remarks", RPSLTextField(optional=True, multiple=True)),
        ("notify", RPSLEmailField(optional=True, multiple=True)),
        ("mnt-by", RPSLReferenceField(multiple=True, referring=["mntner"])),
        ("changed", RPSLTextField(multiple=True)),
        ("source", RPSLGenericNameField()),
    ])


OBJECT_CLASS_MAPPING = {
    "as-block": RPSLAsBlock,
    "as-set": RPSLAsSet,
    "aut-num": RPSLAutNum,
    "dictionary": RPSLDictionary,
    "domain": RPSLDomain,
    "filter-set": RPSLFilterSet,
    "inet-rtr": RPSLInetRtr,
    "inet6num": RPSLInet6Num,
    "inetnum": RPSLInetnum,
    "key-cert": RPSLKeyCert,
    "limerick": RPSLLimerick,
    "mntner": RPSLMntner,
    "peering-set": RPSLPeeringSet,
    "person": RPSLPerson,
    "repository": RPSLRepository,
    "role": RPSLRole,
    "route": RPSLRoute,
    "route-set": RPSLRouteSet,
    "route6": RPSLRoute6,
    "rtr-set": RPSLRtrSet,
}
