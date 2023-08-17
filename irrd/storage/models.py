import enum

import sqlalchemy as sa
from IPy import IP
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import relationship

from irrd.routepref.status import RoutePreferenceStatus
from irrd.rpki.status import RPKIStatus
from irrd.rpsl.rpsl_objects import lookup_field_names
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.updates.parser_state import UpdateRequestType


class DatabaseOperation(enum.Enum):
    add_or_update = "ADD"
    delete = "DEL"


class JournalEntryOrigin(enum.Enum):
    # Legacy journal entries for which the origin is unknown, can be auth_change or mirror
    unknown = "UNKNOWN"
    # Journal entry received from a mirror by NRTM or importing from a file
    mirror = "MIRROR"
    # Journal entry generated from synthesized NRTM
    synthetic_nrtm = "SYNTHETIC_NRTM"
    # Journal entry generated from pseudo IRR
    pseudo_irr = "PSEUDO_IRR"
    # Journal entry caused by a user-submitted change in an authoritative database
    auth_change = "AUTH_CHANGE"
    # Journal entry caused by a change in in the RPKI status of an object in an authoritative db
    rpki_status = "RPKI_STATUS"
    # Journal entry caused by a change in the scope filter status
    scope_filter = "SCOPE_FILTER"
    # Journal entry caused by an object being suspended or reactivated
    suspension = "SUSPENSION"
    # Journal entry caused by an object's route preference changing between suppressed and visible
    route_preference = "ROUTE_PREFERENCE"


class AuthoritativeChangeOrigin(enum.Enum):
    webui = "WEBUI"
    webapi = "WEBAPI"
    email = "EMAIL"
    other = "OTHER"


Base = declarative_base()


class Setting(Base):  # type: ignore
    """
    SQLAlchemy ORM object for settings stored in the DB.
    Only intended for internal IRRD state, not admin-modified settings.
    """

    __tablename__ = "setting"

    name = sa.Column(sa.String, primary_key=True)
    value = sa.Column(sa.String)

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    def __repr__(self):
        return f"<Setting/{self.name}>"


class RPSLDatabaseObject(Base):  # type: ignore
    """
    SQLAlchemy ORM object for RPSL database objects.

    Note that SQLAlchemy does not require you to use the ORM for ORM
    objects - as that can be slower with large queries.
    """

    __tablename__ = "rpsl_objects"

    # Requires extension pgcrypto
    # in alembic: op.execute('create EXTENSION if not EXISTS 'pgcrypto';')
    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)
    rpsl_pk = sa.Column(sa.String, index=True, nullable=False)
    source = sa.Column(sa.String, index=True, nullable=False)

    object_class = sa.Column(sa.String, nullable=False, index=True)
    parsed_data = sa.Column(pg.JSONB, nullable=False)
    object_text = sa.Column(sa.Text, nullable=False)

    ip_version = sa.Column(sa.Integer, index=True)
    ip_first = sa.Column(pg.INET, index=True)
    ip_last = sa.Column(pg.INET, index=True)
    ip_size = sa.Column(sa.DECIMAL(scale=0))
    # Only filled for route/route6
    prefix_length = sa.Column(sa.Integer, nullable=True)
    prefix = sa.Column(pg.CIDR, nullable=True)

    asn_first = sa.Column(sa.BigInteger, index=True)
    asn_last = sa.Column(sa.BigInteger, index=True)

    rpki_status = sa.Column(
        sa.Enum(RPKIStatus), nullable=False, index=True, server_default=RPKIStatus.not_found.name
    )
    scopefilter_status = sa.Column(
        sa.Enum(ScopeFilterStatus), nullable=False, index=True, server_default=ScopeFilterStatus.in_scope.name
    )
    route_preference_status = sa.Column(
        sa.Enum(RoutePreferenceStatus),
        nullable=False,
        index=True,
        server_default=RoutePreferenceStatus.visible.name,
    )

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    auth_mntner = relationship("AuthMntner", uselist=False, backref="rpsl_mntner_obj")

    @declared_attr
    def __table_args__(cls):  # noqa
        args = [
            sa.UniqueConstraint(
                "rpsl_pk", "source", "object_class", name="rpsl_objects_rpsl_pk_source_class_unique"
            ),
            sa.Index(
                "ix_rpsl_objects_ip_first_ip_last",
                "ip_first",
                "ip_last",
            ),
            sa.Index("ix_rpsl_objects_ip_last_ip_first", "ip_last", "ip_first"),
            sa.Index("ix_rpsl_objects_asn_first_asn_last", "asn_first", "asn_last"),
            sa.Index("ix_rpsl_objects_prefix_gist", sa.text("prefix inet_ops"), postgresql_using="gist"),
        ]
        for name in lookup_field_names():
            index_name = "ix_rpsl_objects_parsed_data_" + name.replace("-", "_")
            index_on = sa.text(f"(parsed_data->'{name}')")
            args.append(sa.Index(index_name, index_on, postgresql_using="gin"))
        return tuple(args)

    def __repr__(self):
        return f"<{self.rpsl_pk}/{self.source}/{self.pk}>"


class RPSLDatabaseJournal(Base):  # type: ignore
    """
    SQLAlchemy ORM object for change history of RPSL database objects.
    """

    __tablename__ = "rpsl_database_journal"

    # Requires extension pgcrypto
    # in alembic: op.execute('create EXTENSION if not EXISTS 'pgcrypto';')
    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)

    # Serial_journal is intended to allow querying by insertion order.
    # This could almost be met by the timestamp, except that fails in case
    # of clock changes. Unique and in insertion order, but may have gaps.
    serial_global_seq = sa.Sequence("rpsl_database_journal_serial_global_seq")
    serial_global = sa.Column(
        sa.BigInteger,
        serial_global_seq,
        server_default=serial_global_seq.next_value(),
        nullable=False,
        index=True,
        unique=True,
    )

    rpsl_pk = sa.Column(sa.String, index=True, nullable=False)
    source = sa.Column(sa.String, index=True, nullable=False)
    origin = sa.Column(
        sa.Enum(JournalEntryOrigin),
        nullable=False,
        index=True,
        server_default=JournalEntryOrigin.unknown.name,
    )

    serial_nrtm = sa.Column(sa.Integer, index=True, nullable=False)
    operation = sa.Column(sa.Enum(DatabaseOperation), nullable=False)

    object_class = sa.Column(sa.String, nullable=False, index=True)
    object_text = sa.Column(sa.Text, nullable=False)

    # These objects are not mutable, so creation time is sufficient.
    timestamp = sa.Column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), index=True, nullable=False
    )

    @declared_attr
    def __table_args__(cls):  # noqa
        return (
            sa.UniqueConstraint(
                "serial_nrtm", "source", name="rpsl_objects_history_serial_nrtm_source_unique"
            ),
        )

    def __repr__(self):
        return f"<{self.source}/{self.serial}/{self.operation}/{self.rpsl_pk}>"


class RPSLDatabaseObjectSuspended(Base):  # type: ignore
    """
    SQLAlchemy ORM object for suspended RPSL objects (#577)
    """

    __tablename__ = "rpsl_objects_suspended"

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)
    rpsl_pk = sa.Column(sa.String, index=True, nullable=False)
    source = sa.Column(sa.String, index=True, nullable=False)

    object_class = sa.Column(sa.String, nullable=False, index=True)
    object_text = sa.Column(sa.Text, nullable=False)
    mntners = sa.Column(pg.ARRAY(sa.Text), nullable=False, index=True)

    timestamp = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    original_created = sa.Column(sa.DateTime(timezone=True), nullable=False)
    original_updated = sa.Column(sa.DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<{self.rpsl_pk}/{self.source}/{self.pk}>"


class RPSLDatabaseStatus(Base):  # type: ignore
    """
    SQLAlchemy ORM object for the status of authoritative and mirrored DBs.

    Note that this database is for keeping status, and is not the source
    of configuration parameters.
    """

    __tablename__ = "database_status"

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)
    source = sa.Column(sa.String, index=True, nullable=False, unique=True)

    # The oldest and newest serial_nrtm's seen, for any reason since the last import
    serial_oldest_seen = sa.Column(sa.Integer)
    serial_newest_seen = sa.Column(sa.Integer)
    # The oldest and newest serials in the current local journal
    serial_oldest_journal = sa.Column(sa.Integer)
    serial_newest_journal = sa.Column(sa.Integer)
    # The serial at which this IRRd last exported
    serial_last_export = sa.Column(sa.Integer)
    # The last serial seen from an NRTM mirror, i.e. resume NRTM query from this serial
    serial_newest_mirror = sa.Column(sa.Integer)

    force_reload = sa.Column(sa.Boolean(), default=False, nullable=False)
    synchronised_serials = sa.Column(sa.Boolean(), default=True, nullable=False)

    last_error = sa.Column(sa.Text)
    last_error_timestamp = sa.Column(sa.DateTime(timezone=True))

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated = sa.Column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )

    def __repr__(self):
        return self.source


class ROADatabaseObject(Base):  # type: ignore
    """
    SQLAlchemy ORM object for ROA objects.
    """

    __tablename__ = "roa_object"

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)

    prefix = sa.Column(pg.CIDR, nullable=False)
    asn = sa.Column(sa.BigInteger, nullable=False)
    max_length = sa.Column(sa.Integer, nullable=False)
    trust_anchor = sa.Column(sa.String)
    ip_version = sa.Column(sa.Integer, nullable=False, index=True)

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    @declared_attr
    def __table_args__(cls):  # noqa
        args = [
            sa.UniqueConstraint(
                "prefix", "asn", "max_length", "trust_anchor", name="roa_object_prefix_asn_maxlength_unique"
            ),
            sa.Index("ix_roa_objects_prefix_gist", sa.text("prefix inet_ops"), postgresql_using="gist"),
        ]
        return tuple(args)

    def __repr__(self):
        return f"<{self.prefix}/{self.asn}>"


class ProtectedRPSLName(Base):  # type: ignore
    """
    SQLAlchemy ORM object for recording protected names.

    This stores nic-hdl/mntner name of person, role or mntner
    objects that have been deleted, to prevent reuse. #616.
    """

    __tablename__ = "protected_rpsl_name"

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)
    rpsl_pk = sa.Column(sa.String, index=True, nullable=False)
    source = sa.Column(sa.String, index=True, nullable=False)
    object_class = sa.Column(sa.String, nullable=False, index=True)

    # The name that is protected depends on the object class
    protected_name = sa.Column(sa.String, index=True, nullable=False)

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    def __repr__(self):
        return f"<ProtectedRPSLName/{self.protected_name}/{self.source}/{self.pk}>"


class AuthPermission(Base):  # type: ignore
    __tablename__ = "auth_permission"

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)
    user_id = sa.Column(pg.UUID, sa.ForeignKey("auth_user.pk", ondelete="RESTRICT"), index=True)
    mntner_id = sa.Column(pg.UUID, sa.ForeignKey("auth_mntner.pk", ondelete="RESTRICT"), index=True)

    user_management = sa.Column(sa.Boolean, default=False, nullable=False)

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    @declared_attr
    def __table_args__(cls):  # noqa
        args = [
            sa.UniqueConstraint("user_id", "mntner_id", name="auth_permission_user_mntner_unique"),
        ]
        return tuple(args)

    def __repr__(self):
        return f"AuthPermission<{self.pk}, user {self.user_id}, mntner {self.mntner_id}>"


class AuthUser(Base):  # type: ignore
    __tablename__ = "auth_user"

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)
    email = sa.Column(sa.String, index=True, unique=True, nullable=False)
    name = sa.Column(sa.String, nullable=False)
    password = sa.Column(sa.String, nullable=False)

    totp_secret = sa.Column(sa.String, nullable=True)
    totp_last_used = sa.Column(sa.String, nullable=True)

    active = sa.Column(sa.Boolean, default=False, nullable=False)
    override = sa.Column(sa.Boolean, default=False, nullable=False)

    permissions = relationship(
        "AuthPermission",
        backref=sa.orm.backref("user", uselist=False),
    )
    webauthns = relationship(
        "AuthWebAuthn",
        backref=sa.orm.backref("user", uselist=False),
    )
    mntners = relationship(
        "AuthMntner",
        backref="users",
        secondary=(
            "join(AuthPermission, AuthMntner, and_(AuthMntner.pk==AuthPermission.mntner_id,"
            " AuthMntner.migration_token.is_(None)))"
        ),
    )
    mntners_user_management = relationship(
        "AuthMntner",
        secondary=(
            "join(AuthPermission, AuthMntner, and_(AuthMntner.pk==AuthPermission.mntner_id,"
            " AuthMntner.migration_token.is_(None),AuthPermission.user_management==True))"
        ),
    )
    mntners_no_user_management = relationship(
        "AuthMntner",
        secondary=(
            "join(AuthPermission, AuthMntner, and_(AuthMntner.pk==AuthPermission.mntner_id,"
            " AuthMntner.migration_token.is_(None),AuthPermission.user_management==False))"
        ),
    )

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    def __repr__(self):
        return f"AuthUser<{self.pk}, {self.email}>"

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.pk == other.pk
        raise NotImplementedError

    @property
    def has_totp(self) -> bool:
        return bool(self.totp_secret)

    @property
    def has_webauthn(self) -> bool:
        return bool(self.webauthns)

    @property
    def has_mfa(self) -> bool:
        return self.has_webauthn or self.has_totp

    # getter methods are for compatibility with imia UserLike object
    def get_display_name(self) -> str:  # pragma: no cover
        return self.name

    def get_id(self) -> str:
        return self.email

    def get_hashed_password(self) -> str:
        return self.password

    def get_scopes(self) -> list:  # pragma: no cover
        return []


class AuthWebAuthn(Base):  # type: ignore
    __tablename__ = "auth_webauthn"

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)
    user_id = sa.Column(pg.UUID, sa.ForeignKey("auth_user.pk", ondelete="RESTRICT"), index=True)
    name = sa.Column(sa.String, nullable=False)
    credential_id = sa.Column(sa.LargeBinary, nullable=False)
    credential_public_key = sa.Column(sa.LargeBinary, nullable=False)
    credential_sign_count = sa.Column(sa.Integer, nullable=False)
    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    last_used = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


class AuthApiToken(Base):  # type: ignore
    __tablename__ = "auth_api_token"

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)
    token = sa.Column(
        pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), unique=True, index=True
    )
    name = sa.Column(sa.String, nullable=False)
    creator_id = sa.Column(pg.UUID, sa.ForeignKey("auth_user.pk", ondelete="RESTRICT"), index=True)
    mntner_id = sa.Column(pg.UUID, sa.ForeignKey("auth_mntner.pk", ondelete="RESTRICT"), index=True)
    creator = relationship(
        "AuthUser",
        backref=sa.orm.backref("api_tokens_created"),
    )
    mntner = relationship(
        "AuthMntner",
        backref=sa.orm.backref("api_tokens"),
    )

    # This is not an ARRAY(CIDR) because psycopg2cffi does not support those.
    ip_restriction = sa.Column(sa.String, nullable=True)
    enabled_webapi = sa.Column(sa.Boolean(), default=True, nullable=False)
    enabled_email = sa.Column(sa.Boolean(), default=True, nullable=False)

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    def __repr__(self):
        return f"<{self.token}/{self.name}/{self.mntner.rpsl_mntner_pk if self.mntner else None}>"

    def valid_for(self, origin: AuthoritativeChangeOrigin, remote_ip: IP) -> bool:
        if not any(
            [
                self.enabled_webapi and origin == AuthoritativeChangeOrigin.webapi,
                self.enabled_email and origin == AuthoritativeChangeOrigin.email,
            ]
        ):
            return False
        if self.ip_restriction:
            for ip in self.ip_restriction.split(","):
                if remote_ip and remote_ip in IP(ip):
                    return True
            return False
        return True


class AuthMntner(Base):  # type: ignore
    __tablename__ = "auth_mntner"

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)
    rpsl_mntner_pk = sa.Column(sa.String, index=True, nullable=False)
    rpsl_mntner_obj_id = sa.Column(
        pg.UUID,
        sa.ForeignKey("rpsl_objects.pk", ondelete="RESTRICT"),
        index=True,
        unique=True,
        nullable=False,
    )
    rpsl_mntner_source = sa.Column(sa.String, index=True, nullable=False)

    migration_token = sa.Column(sa.String, nullable=True)

    permissions = relationship(
        "AuthPermission",
        backref=sa.orm.backref("mntner", uselist=False),
    )

    created = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    @property
    def migration_complete(self) -> bool:
        return self.migration_token is None

    @declared_attr
    def __table_args__(cls):  # noqa
        args = [
            sa.UniqueConstraint(
                "rpsl_mntner_obj_id",
                "rpsl_mntner_source",
                name="auth_mntner_rpsl_mntner_obj_id_source_unique",
            ),
        ]
        return tuple(args)

    def __repr__(self):
        return f"AuthMntner<{self.pk}, {self.rpsl_mntner_pk}>"


class ChangeLog(Base):  # type: ignore
    __tablename__ = "change_log"

    pk = sa.Column(pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)
    auth_by_user_id = sa.Column(pg.UUID, sa.ForeignKey("auth_user.pk", ondelete="SET NULL"), nullable=True)
    auth_by_user_email = sa.Column(sa.String, nullable=True)
    auth_by_api_key_id = sa.Column(
        pg.UUID, sa.ForeignKey("auth_api_token.pk", ondelete="SET NULL"), nullable=True
    )
    auth_by_api_key = relationship(
        "AuthApiToken",
        foreign_keys="ChangeLog.auth_by_api_key_id",
    )
    auth_by_api_key_id_fixed = sa.Column(pg.UUID, nullable=True)
    auth_through_mntner_id = sa.Column(
        pg.UUID, sa.ForeignKey("auth_mntner.pk", ondelete="SET NULL"), index=True, nullable=True
    )
    auth_through_mntner = relationship(
        "AuthMntner",
        foreign_keys="ChangeLog.auth_through_mntner_id",
    )
    auth_through_rpsl_mntner_pk = sa.Column(sa.String, index=True, nullable=True)
    auth_by_rpsl_mntner_password = sa.Column(sa.Boolean, nullable=False, default=False)
    auth_by_rpsl_mntner_pgp_key = sa.Column(sa.Boolean, nullable=False, default=False)
    auth_by_override = sa.Column(sa.Boolean, default=False)

    from_email = sa.Column(sa.String, nullable=True)
    from_ip = sa.Column(pg.INET, nullable=True)

    auth_change_descr = sa.Column(sa.String, nullable=True)
    auth_affected_user_id = sa.Column(
        pg.UUID, sa.ForeignKey("auth_user.pk", ondelete="SET NULL"), nullable=True
    )
    auth_affected_mntner_id = sa.Column(
        pg.UUID, sa.ForeignKey("auth_mntner.pk", ondelete="SET NULL"), index=True, nullable=True
    )
    auth_affected_mntner = relationship(
        "AuthMntner",
        foreign_keys="ChangeLog.auth_affected_mntner_id",
    )
    auth_affected_user = relationship(
        "AuthUser",
        foreign_keys="ChangeLog.auth_affected_user_id",
    )

    rpsl_target_request_type = sa.Column(sa.Enum(UpdateRequestType), nullable=True)
    rpsl_target_pk = sa.Column(sa.String, index=True, nullable=True)
    rpsl_target_source = sa.Column(sa.String, nullable=True)
    rpsl_target_object_class = sa.Column(sa.String, nullable=True)
    rpsl_target_object_text_old = sa.Column(sa.Text, nullable=True)
    rpsl_target_object_text_new = sa.Column(sa.Text, nullable=True)

    timestamp = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    def __repr__(self):
        return f"<{self.pk}/{self.description()}>"

    def description(self) -> str:
        if self.rpsl_target_pk:
            return (
                f"{self.rpsl_target_request_type.value} of"
                f" {self.rpsl_target_object_class} {self.rpsl_target_pk} in {self.rpsl_target_source}"
            )
        elif self.auth_change_descr:
            return self.auth_change_descr
        else:  # pragma: no cover
            return "<unknown>"


# Before you update this, please check the storage documentation for changing lookup fields.
expected_lookup_field_names = {
    "admin-c",
    "tech-c",
    "zone-c",
    "member-of",
    "mnt-by",
    "role",
    "members",
    "person",
    "mp-members",
    "origin",
    "mbrs-by-ref",
}
if sorted(lookup_field_names()) != sorted(expected_lookup_field_names):  # pragma: no cover
    raise RuntimeError(
        "Field names of lookup fields do not match expected set. Indexes may be missing. "
        f"Expected: {expected_lookup_field_names}, actual: {lookup_field_names()}"
    )
