import hashlib
import logging
import secrets
import sys
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import date, timedelta
from typing import Optional, Tuple, Union

import passlib
import wtforms
from imia import (
    AuthenticationMiddleware,
    LoginManager,
    SessionAuthenticator,
    UserLike,
    UserProvider,
)
from sqlalchemy.orm import joinedload
from starlette.middleware import Middleware
from starlette.requests import HTTPConnection
from starlette_wtf import StarletteForm
from zxcvbn import zxcvbn

from irrd.storage.models import AuthUser
from irrd.storage.orm_provider import ORMSessionProvider
from irrd.webui.helpers import secret_key_derive

logger = logging.getLogger(__name__)

WEBAUTH_MIN_ZXCVBN_SCORE = 2
WEBAUTH_MAX_PASSWORD_LEN = 1000


class AuthProvider(UserProvider):
    async def find_by_id(self, connection: HTTPConnection, identifier: str) -> Optional[UserLike]:
        session_provider = ORMSessionProvider()
        target = session_provider.session.query(AuthUser).filter_by(email=identifier).options(joinedload("*"))
        user = await session_provider.run(target.one)
        session_provider.session.expunge_all()
        session_provider.commit_close()
        return user

    async def find_by_username(
        self, connection: HTTPConnection, username_or_email: str
    ) -> Optional[UserLike]:
        return await self.find_by_id(connection, username_or_email)

    async def find_by_token(self, connection: HTTPConnection, token: str) -> Optional[UserLike]:
        return None  # pragma: no cover


class PasswordHandler:
    def verify(self, plain: str, hashed: str) -> bool:
        try:
            return self._get_hasher().verify(plain, hashed)
        except ValueError:  # pragma: no cover
            return False

    def hash(self, plain: str):
        return self._get_hasher().hash(plain)

    def _get_hasher(self):
        return passlib.hash.md5_crypt if getattr(sys, "_called_from_test", None) else passlib.hash.bcrypt


user_provider = AuthProvider()
password_handler = PasswordHandler()


def get_login_manager() -> LoginManager:
    return LoginManager(user_provider, password_handler, secret_key_derive("web.login_manager"))


authenticators = [
    SessionAuthenticator(user_provider=user_provider),
]

auth_middleware = Middleware(AuthenticationMiddleware, authenticators=authenticators)


def verify_password(user: AuthUser, plain: str) -> bool:
    return password_handler.verify(plain, user.get_hashed_password())


def validate_password_strength(plain: str) -> Tuple[bool, str]:
    if len(plain) > WEBAUTH_MAX_PASSWORD_LEN:
        return False, "This password is too long."
    evaluation = zxcvbn(plain[:100])
    if evaluation["score"] < WEBAUTH_MIN_ZXCVBN_SCORE:
        return False, " ".join([evaluation["feedback"]["warning"]] + evaluation["feedback"]["suggestions"])
    return True, ""


class CurrentPasswordForm(StarletteForm):
    """
    Base form for cases where users need to enter their current password for verification.
    Ensures the current password field is always the last before submit.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fields.move_to_end("current_password")
        self._fields.move_to_end("submit")

    current_password = wtforms.PasswordField(
        "Your current password (for verification)",
        validators=[wtforms.validators.DataRequired()],
    )

    async def validate(self, current_user: AuthUser):
        if not await super().validate():
            return False

        if not verify_password(current_user, self.current_password.data):
            logger.info(
                f"{current_user.email}: entered incorrect current password while attempting an authenticated"
                " action"
            )
            self.current_password.errors.append("Incorrect password.")
            return False

        return True


PASSWORD_RESET_TOKEN_ROOT = date(2022, 1, 1)
PASSWORD_RESET_VALIDITY_DAYS = 2


class PasswordResetToken:
    """
    Generate or validate a password reset token.
    The reset token is derived from:
    - the user key, which is derived from:
      - user PK
      - last change to the User object
      - current hashed password
    - the configured secret key
    - the expiry day in number of days since PASSWORD_RESET_TOKEN_ROOT
    This automatically invalidates the token on any change to the user.
    """

    def __init__(self, user: AuthUser):
        self.user_key = str(user.pk) + str(user.updated) + user.password

    def generate_token(self) -> str:
        expiry_date = date.today() + timedelta(days=PASSWORD_RESET_VALIDITY_DAYS)
        expiry_days = expiry_date - PASSWORD_RESET_TOKEN_ROOT

        hash_str = urlsafe_b64encode(self._hash(expiry_days.days)).decode("ascii")
        return str(expiry_days.days) + "-" + hash_str

    def validate_token(self, token: str) -> bool:
        try:
            expiry_days, input_hash_encoded = token.split("-", 1)
            expiry_date = PASSWORD_RESET_TOKEN_ROOT + timedelta(days=int(expiry_days))

            expected_hash = self._hash(expiry_days)
            input_hash = urlsafe_b64decode(input_hash_encoded)

            return expiry_date >= date.today() and secrets.compare_digest(input_hash, expected_hash)
        except ValueError:
            return False

    def _hash(self, expiry_days: Union[int, str]) -> bytes:
        hash_data = secret_key_derive("web.password_reset_token") + self.user_key + str(expiry_days)
        return hashlib.sha224(hash_data.encode("utf-8")).digest()
