from collections import OrderedDict

from typing import Set, List, Optional, Union

from irrd.conf import PASSWORD_HASH_DUMMY_VALUE, get_setting
from irrd.utils.pgp import get_gpg_instance
from .config import PASSWORD_HASHERS
from .fields import (RPSLTextField, RPSLIPv4PrefixField, RPSLIPv4PrefixesField, RPSLIPv6PrefixField,
                     RPSLIPv6PrefixesField, RPSLIPv4AddressRangeField, RPSLASNumberField,
                     RPSLASBlockField,
                     RPSLSetNameField, RPSLEmailField, RPSLDNSNameField, RPSLGenericNameField,
                     RPSLReferenceField,
                     RPSLReferenceListField, RPSLAuthField, RPSLRouteSetMembersField,
                     RPSLChangedField, RPSLURLField)
from .parser import RPSLObject, UnknownRPSLObjectClassException
from ..utils.validators import parse_as_number, ValidationError

RPSL_ROUTE_OBJECT_CLASS_FOR_IP_VERSION = {
    4: 'route',
    6: 'route6',
}


def rpsl_object_from_text(text, strict_validation=True, default_source: Optional[str]=None) -> RPSLObject:
    rpsl_object_class = text.split(':', maxsplit=1)[0].strip()
    try:
        klass = OBJECT_CLASS_MAPPING[rpsl_object_class]
    except KeyError:
        raise UnknownRPSLObjectClassException(f'unknown object class: {rpsl_object_class}',
                                              rpsl_object_class=rpsl_object_class)
    return klass(from_text=text, strict_validation=strict_validation, default_source=default_source)


class RPSLAsBlock(RPSLObject):
    fields = OrderedDict([
        ('as-block', RPSLASBlockField(primary_key=True, lookup_key=True)),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, multiple=True, referring=['role', 'person'])),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLAsSet(RPSLObject):
    fields = OrderedDict([
        ('as-set', RPSLSetNameField(primary_key=True, lookup_key=True, prefix='AS')),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('members', RPSLReferenceListField(lookup_key=True, optional=True, multiple=True, referring=['aut-num', 'as-set'], strong=False)),
        ('mbrs-by-ref', RPSLReferenceListField(lookup_key=True, optional=True, multiple=True, referring=['mntner'], allow_kw_any=True, strong=False)),
        ('admin-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])

    def clean_for_create(self) -> bool:
        if get_setting('compatibility.permit_non_hierarchical_as_set_name'):
            return True

        first_segment = self.pk().split(':')[0]
        try:
            parse_as_number(first_segment)
            return True
        except ValidationError as ve:
            self.messages.error('AS set names must be hierarchical and the first component must '
                                f'be an AS number, e.g. "AS65537:AS-EXAMPLE": {str(ve)}')
        return False


class RPSLAutNum(RPSLObject):
    fields = OrderedDict([
        ('aut-num', RPSLASNumberField(primary_key=True, lookup_key=True)),
        ('as-name', RPSLGenericNameField(allowed_prefixes=['AS'])),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('member-of', RPSLReferenceListField(lookup_key=True, optional=True, multiple=True, referring=['as-set'], strong=False)),
        ('import', RPSLTextField(optional=True, multiple=True)),
        ('mp-import', RPSLTextField(optional=True, multiple=True)),
        ('import-via', RPSLTextField(optional=True, multiple=True)),
        ('export', RPSLTextField(optional=True, multiple=True)),
        ('mp-export', RPSLTextField(optional=True, multiple=True)),
        ('export-via', RPSLTextField(optional=True, multiple=True)),
        ('default', RPSLTextField(optional=True, multiple=True)),
        ('mp-default', RPSLTextField(optional=True, multiple=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, multiple=True, referring=['role', 'person'])),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, optional=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLDomain(RPSLObject):
    fields = OrderedDict([
        ('domain', RPSLTextField(primary_key=True, lookup_key=True)),  # reverse delegation address (range), v4/v6/enum
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, multiple=True, referring=['role', 'person'])),
        ('zone-c', RPSLReferenceField(lookup_key=True, multiple=True, referring=['role', 'person'])),
        ('nserver', RPSLTextField(optional=True, multiple=True)),  # DNS name, possibly followed v4/v6
        ('sub-dom', RPSLTextField(optional=True, multiple=True)),
        ('dom-net', RPSLTextField(optional=True, multiple=True)),
        ('refer', RPSLTextField(optional=True)),  # ???
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, optional=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLFilterSet(RPSLObject):
    fields = OrderedDict([
        ('filter-set', RPSLSetNameField(primary_key=True, lookup_key=True, prefix='FLTR')),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('filter', RPSLTextField()),
        ('mp-filter', RPSLTextField(optional=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLInetRtr(RPSLObject):
    fields = OrderedDict([
        ('inet-rtr', RPSLDNSNameField(primary_key=True, lookup_key=True)),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('alias', RPSLDNSNameField(optional=True, multiple=True)),
        ('local-as', RPSLASNumberField()),
        ('ifaddr', RPSLTextField(optional=True, multiple=True)),
        ('interface', RPSLTextField(optional=True, multiple=True)),
        ('peer', RPSLTextField(optional=True, multiple=True)),
        ('mp-peer', RPSLTextField(optional=True, multiple=True)),
        ('member-of', RPSLReferenceListField(lookup_key=True, optional=True, multiple=True, referring=['rtr-set'], strong=False)),
        ('rs-in', RPSLTextField(optional=True)),
        ('rs-out', RPSLTextField(optional=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLInet6Num(RPSLObject):
    fields = OrderedDict([
        ('inet6num', RPSLIPv6PrefixField(primary_key=True, lookup_key=True)),
        ('netname', RPSLTextField()),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('country', RPSLTextField(multiple=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, multiple=True, referring=['role', 'person'])),
        ('rev-srv', RPSLTextField(optional=True, multiple=True)),
        ('status', RPSLTextField()),
        ('geofeed', RPSLURLField(optional=True)),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLInetnum(RPSLObject):
    fields = OrderedDict([
        ('inetnum', RPSLIPv4AddressRangeField(primary_key=True, lookup_key=True)),
        ('netname', RPSLTextField()),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('country', RPSLTextField(multiple=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, multiple=True, referring=['role', 'person'])),
        ('rev-srv', RPSLTextField(optional=True, multiple=True)),
        ('status', RPSLTextField()),
        ('geofeed', RPSLURLField(optional=True)),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLKeyCert(RPSLObject):
    fields = OrderedDict([
        ('key-cert', RPSLGenericNameField(primary_key=True, lookup_key=True)),
        ('method', RPSLTextField(optional=True)),  # Fixed to PGP
        ('owner', RPSLTextField(optional=True, multiple=True)),  # key owner, autogenerate
        ('fingerpr', RPSLTextField(optional=True)),  # fingerprint, autogenerate
        ('certif', RPSLTextField(multiple=True)),  # Actual key
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
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

        gpg = get_gpg_instance()
        certif_data = '\n'.join(self.parsed_data.get('certif', [])).replace(',', '\n')
        result = gpg.import_keys(certif_data)

        if len(result.fingerprints) != 1:
            msg = 'Unable to read public PGP key: key corrupt or multiple keys provided'
            if result.results:
                msg = f'{msg}: {result.results[0]["text"]}'
            self.messages.error(msg)
            return False

        self.fingerprint = result.fingerprints[0]
        expected_object_name = 'PGPKEY-' + self.fingerprint[-8:]
        actual_object_name = self.parsed_data['key-cert'].upper()
        fingerprint_formatted = self.format_fingerprint(self.fingerprint)

        if expected_object_name != actual_object_name:
            self.messages.error(
                f'Invalid object name {actual_object_name}: does not match key fingerprint {fingerprint_formatted}, '
                f'expected object name {expected_object_name}'
            )
            return False

        self._update_attribute_value('fingerpr', fingerprint_formatted)
        self._update_attribute_value('owner', gpg.list_keys(keys=self.fingerprint)[0]['uids'])
        self._update_attribute_value('method', 'PGP')

        return True

    # This API is correct, but not very practical.
    # In typical cases, the PGP key used to sign a message is not known until
    # the PGP signature is actually parsed. More useful is a generic method to find
    # which key signed a message, which can then be stored and compared to key-cert's later.
    # This method will probably be extracted to the update handler.
    def verify(self, message: str) -> bool:
        gpg = get_gpg_instance()
        result = gpg.verify(message)
        return result.valid and result.key_status is None and \
            self.format_fingerprint(result.fingerprint) == self.parsed_data['fingerpr']

    @staticmethod
    def format_fingerprint(fingerprint: str) -> str:
        """Format a PGP fingerprint into sections of 4 characters, separated by spaces."""
        string_parts = []
        for idx in range(0, 40, 4):
            string_parts.append(fingerprint[idx:idx + 4])
            if idx == 16:
                string_parts.append('')
        return ' '.join(string_parts)


class RPSLMntner(RPSLObject):
    fields = OrderedDict([
        ('mntner', RPSLGenericNameField(primary_key=True, lookup_key=True)),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('upd-to', RPSLEmailField(multiple=True)),
        ('mnt-nfy', RPSLEmailField(optional=True, multiple=True)),
        ('auth', RPSLAuthField(multiple=True)),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])

    def clean(self):
        """Check whether either all hash values are dummy hashes, or none."""
        if not super().clean():
            return False  # pragma: no cover

        dummy_matches = [auth[1] == PASSWORD_HASH_DUMMY_VALUE for auth in self._auth_lines(True)]
        if any(dummy_matches) and not all(dummy_matches):
            self.messages.error('Either all password auth hashes in a submitted mntner must be dummy objects, or none.')

    def verify_auth(self, passwords: List[str], keycert_obj_pk: Optional[str]=None) -> bool:
        """
        Verify whether one of a given list of passwords matches
        any of the auth hashes in this object, or match the
        keycert object PK.
        """
        for auth in self.parsed_data.get('auth', []):
            if keycert_obj_pk and auth.upper() == keycert_obj_pk.upper():
                return True
            if ' ' not in auth:
                continue
            scheme, hash = auth.split(' ', 1)
            hasher = PASSWORD_HASHERS.get(scheme.upper())
            if hasher:
                for password in passwords:
                    try:
                        if hasher.verify(password, hash):
                            return True
                    except ValueError:
                        pass
        return False

    def has_dummy_auth_value(self) -> bool:
        """
        Check whether this object has dummy auth hashes.
        If clean() has returned successfully before, the answer from this method
        means that either all or no hashes have dummy values.
        """
        auth_values = [auth[1] for auth in self._auth_lines(password_hashes=True)]
        return bool(auth_values) and all([value == PASSWORD_HASH_DUMMY_VALUE for value in auth_values])

    def force_single_new_password(self, password) -> None:
        """
        Overwrite all auth hashes with a single new hash for the provided password.
        Retains other methods, i.e. PGPKEY.
        """
        hash = 'MD5-PW ' + PASSWORD_HASHERS['MD5-PW'].hash(password)
        auths = self._auth_lines(password_hashes=False)
        auths.append(hash)
        self._update_attribute_value('auth', auths)

    def _auth_lines(self, password_hashes=True) -> List[Union[str, List[str]]]:
        """
        Return a list of auth values in this object.
        If password_hashes=False, returns only non-hash (i.e. PGPKEY) lines.
        If password_hashes=True, returns a list of lists, each inner list containing
        the hash method and the hash.
        """
        lines = self.parsed_data.get('auth', [])
        if password_hashes is True:
            return [auth.split(' ', 1) for auth in lines if ' ' in auth]
        return [auth for auth in lines if ' ' not in auth]


class RPSLPeeringSet(RPSLObject):
    fields = OrderedDict([
        ('peering-set', RPSLSetNameField(primary_key=True, lookup_key=True, prefix='PRNG')),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('peering', RPSLTextField(optional=True, multiple=True)),
        ('mp-peering', RPSLTextField(optional=True, multiple=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLPerson(RPSLObject):
    fields = OrderedDict([
        ('person', RPSLTextField(lookup_key=True)),
        ('address', RPSLTextField(multiple=True)),
        ('phone', RPSLTextField(multiple=True)),
        ('fax-no', RPSLTextField(optional=True, multiple=True)),
        ('e-mail', RPSLEmailField(multiple=True)),
        ('nic-hdl', RPSLGenericNameField(primary_key=True, lookup_key=True, non_strict_allow_any=True)),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLRole(RPSLObject):
    fields = OrderedDict([
        ('role', RPSLTextField(lookup_key=True)),
        ('trouble', RPSLTextField(optional=True, multiple=True)),
        ('address', RPSLTextField(multiple=True)),
        ('phone', RPSLTextField(multiple=True)),
        ('fax-no', RPSLTextField(optional=True, multiple=True)),
        ('e-mail', RPSLEmailField(multiple=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('nic-hdl', RPSLGenericNameField(primary_key=True, lookup_key=True, non_strict_allow_any=True)),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLRoute(RPSLObject):
    rpki_relevant = True
    discarded_fields = ['rpki-ov-state']
    fields = OrderedDict([
        ('route', RPSLIPv4PrefixField(primary_key=True, lookup_key=True)),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('origin', RPSLASNumberField(primary_key=True)),
        ('holes', RPSLIPv4PrefixesField(optional=True, multiple=True)),
        ('member-of', RPSLReferenceListField(lookup_key=True, optional=True, multiple=True, referring=['route-set'], strong=False)),
        ('inject', RPSLTextField(optional=True, multiple=True)),
        ('aggr-bndry', RPSLTextField(optional=True)),
        ('aggr-mtd', RPSLTextField(optional=True)),
        ('export-comps', RPSLTextField(optional=True)),
        ('components', RPSLTextField(optional=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('geoidx', RPSLTextField(optional=True, multiple=True)),
        ('roa-uri', RPSLTextField(optional=True)),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLRouteSet(RPSLObject):
    fields = OrderedDict([
        ('route-set', RPSLSetNameField(primary_key=True, lookup_key=True, prefix='RS')),
        ('members', RPSLRouteSetMembersField(ip_version=4, lookup_key=True, optional=True, multiple=True)),
        ('mp-members', RPSLRouteSetMembersField(ip_version=None, lookup_key=True, optional=True, multiple=True)),
        ('mbrs-by-ref', RPSLReferenceListField(lookup_key=True, optional=True, multiple=True, referring=['mntner'], allow_kw_any=True, strong=False)),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLRoute6(RPSLObject):
    rpki_relevant = True
    discarded_fields = ['rpki-ov-state']
    fields = OrderedDict([
        ('route6', RPSLIPv6PrefixField(primary_key=True, lookup_key=True)),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('origin', RPSLASNumberField(primary_key=True)),
        ('holes', RPSLIPv6PrefixesField(optional=True, multiple=True)),
        ('member-of', RPSLReferenceListField(lookup_key=True, optional=True, multiple=True, referring=['route-set'], strong=False)),
        ('inject', RPSLTextField(optional=True, multiple=True)),
        ('aggr-bndry', RPSLTextField(optional=True)),
        ('aggr-mtd', RPSLTextField(optional=True)),
        ('export-comps', RPSLTextField(optional=True)),
        ('components', RPSLTextField(optional=True)),
        ('admin-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('geoidx', RPSLTextField(optional=True, multiple=True)),
        ('roa-uri', RPSLTextField(optional=True)),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


class RPSLRtrSet(RPSLObject):
    fields = OrderedDict([
        ('rtr-set', RPSLSetNameField(primary_key=True, lookup_key=True, prefix='RTRS')),
        ('descr', RPSLTextField(multiple=True, optional=True)),
        ('members', RPSLReferenceListField(lookup_key=True, optional=True, multiple=True, referring=['inet-rtr', 'rtr-set'], strong=False)),
        ('mp-members', RPSLReferenceListField(lookup_key=True, optional=True, multiple=True, referring=['inet-rtr', 'rtr-set'], strong=False)),
        ('mbrs-by-ref', RPSLReferenceListField(lookup_key=True, optional=True, multiple=True, referring=['mntner'], allow_kw_any=True, strong=False)),
        ('admin-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('tech-c', RPSLReferenceField(lookup_key=True, optional=True, multiple=True, referring=['role', 'person'])),
        ('remarks', RPSLTextField(optional=True, multiple=True)),
        ('notify', RPSLEmailField(optional=True, multiple=True)),
        ('mnt-by', RPSLReferenceListField(lookup_key=True, multiple=True, referring=['mntner'])),
        ('changed', RPSLChangedField(optional=True, multiple=True)),
        ('source', RPSLGenericNameField()),
    ])


OBJECT_CLASS_MAPPING = {
    'as-block': RPSLAsBlock,
    'as-set': RPSLAsSet,
    'aut-num': RPSLAutNum,
    'domain': RPSLDomain,
    'filter-set': RPSLFilterSet,
    'inet-rtr': RPSLInetRtr,
    'inet6num': RPSLInet6Num,
    'inetnum': RPSLInetnum,
    'key-cert': RPSLKeyCert,
    'mntner': RPSLMntner,
    'peering-set': RPSLPeeringSet,
    'person': RPSLPerson,
    'role': RPSLRole,
    'route': RPSLRoute,
    'route-set': RPSLRouteSet,
    'route6': RPSLRoute6,
    'rtr-set': RPSLRtrSet,
}

RPKI_RELEVANT_OBJECT_CLASSES = [
    rpsl_object.rpsl_object_class
    for rpsl_object in OBJECT_CLASS_MAPPING.values()
    if rpsl_object.rpki_relevant
]


def lookup_field_names() -> Set[str]:
    """Return all unique names of all lookup keys in all objects, plus 'origin'."""
    names = {'origin'}
    for object_class in OBJECT_CLASS_MAPPING.values():
        names.update([f for f in object_class.lookup_fields if f not in object_class.pk_fields])
    return names
