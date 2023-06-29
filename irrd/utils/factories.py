import factory.alchemy
from webauthn import base64url_to_bytes

from irrd.storage.models import (
    AuthApiToken,
    AuthMntner,
    AuthPermission,
    AuthUser,
    AuthWebAuthn,
    ChangeLog,
    RPSLDatabaseObject,
)
from irrd.webui.auth.users import password_handler

SAMPLE_USER_PASSWORD = "password"
SAMPLE_USER_TOTP_TOKEN = "4U47VXPTM3GGM2MFDLN33G6XM4RIC6UT"


def set_factory_session(session):
    factories = [
        klass
        for klass in factory.alchemy.SQLAlchemyModelFactory.__subclasses__()
        if klass.__module__.startswith("irrd.")
    ]
    for factorie in factories:
        factorie._meta.sqlalchemy_session = session


class AuthUserFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = AuthUser
        sqlalchemy_session_persistence = "commit"

    email = factory.Sequence(lambda n: "user-%s@example.com" % n)
    name = "name"
    totp_secret = SAMPLE_USER_TOTP_TOKEN

    @factory.lazy_attribute
    def password(self):
        return password_handler.hash(SAMPLE_USER_PASSWORD)


class AuthWebAuthnFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = AuthWebAuthn
        sqlalchemy_session_persistence = "commit"

    name = "webauthn-key"
    credential_id = base64url_to_bytes("ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s")
    credential_public_key = base64url_to_bytes(
        "pAEDAzkBACBZAQDfV20epzvQP-HtcdDpX-cGzdOxy73WQEvsU7Dnr9UWJophEfpngouvgnRLXaEUn_d8HGkp_HIx8rrpkx4BVs6X_B6ZjhLlezjIdJbLbVeb92BaEsmNn1HW2N9Xj2QM8cH-yx28_vCjf82ahQ9gyAr552Bn96G22n8jqFRQKdVpO-f-bvpvaP3IQ9F5LCX7CUaxptgbog1SFO6FI6ob5SlVVB00lVXsaYg8cIDZxCkkENkGiFPgwEaZ7995SCbiyCpUJbMqToLMgojPkAhWeyktu7TlK6UBWdJMHc3FPAIs0lH_2_2hKS-mGI1uZAFVAfW1X-mzKL0czUm2P1UlUox7IUMBAAE"
    )
    credential_sign_count = 0


class AuthMntnerFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = AuthMntner
        sqlalchemy_session_persistence = "commit"

    rpsl_mntner_pk = ("TEST-MNT",)
    rpsl_mntner_source = ("TEST",)

    @factory.lazy_attribute
    def rpsl_mntner_obj_id(self):
        rpsl_mntner = (
            AuthMntnerFactory._meta.sqlalchemy_session.query(RPSLDatabaseObject)
            .filter(RPSLDatabaseObject.object_class == "mntner")
            .order_by(RPSLDatabaseObject.created.desc())
            .first()
        )
        return str(rpsl_mntner.pk)


class AuthPermissionFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = AuthPermission
        sqlalchemy_session_persistence = "commit"


class AuthApiTokenFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = AuthApiToken
        sqlalchemy_session_persistence = "commit"

    name = factory.Sequence(lambda n: "API token %s" % n)
    enabled_webapi = True
    enabled_email = True


class ChangeLogFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = ChangeLog
        sqlalchemy_session_persistence = "commit"
