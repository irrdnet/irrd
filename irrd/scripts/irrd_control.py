#!/usr/bin/env python
# ruff: noqa: E402
import logging
import sys
import textwrap
import warnings
from functools import update_wrapper
from pathlib import Path

import click
from joserfc.rfc7518.ec_key import ECKey
from sqlalchemy.exc import SAWarning

sys.path.append(str(Path(__file__).resolve().parents[2]))

from irrd.conf import CONFIG_PATH_DEFAULT, config_init, get_setting
from irrd.storage.models import AuthUser, RPSLDatabaseStatus
from irrd.storage.orm_provider import ORMSessionProvider, session_provider_manager_sync
from irrd.utils.crypto import (
    eckey_from_config,
    eckey_private_key_as_str,
    eckey_public_key_as_str,
)
from irrd.webui import UI_DEFAULT_DATETIME_FORMAT
from irrd.webui.helpers import send_authentication_change_mail

warnings.filterwarnings("ignore", category=SAWarning)

logger = logging.getLogger(__name__)


def check_readonly_standby(f):
    def new_func(*args, **kwargs):
        if get_setting("readonly_standby"):
            raise click.ClickException("Unable to run this command, because readonly_standby is set.")
        return f(*args, **kwargs)

    return update_wrapper(new_func, f)


@click.group()
@click.option(
    "--config",
    type=click.Path(exists=True, dir_okay=False),
    help="use a different IRRd config file",
    default=CONFIG_PATH_DEFAULT,
    show_default=True,
)
def cli(config):
    config_init(config)  # pragma: no cover


@cli.command()
@click.argument("email")
@check_readonly_standby
@session_provider_manager_sync
def user_mfa_clear(email, session_provider: ORMSessionProvider):
    """
    Remove two-factor authentication for user EMAIL.
    """
    user = find_user(session_provider, email)

    if not user.has_mfa:
        raise click.ClickException("User has no two-factor methods enabled.")

    auth_methods = "\n    - ".join(
        [
            f"WebAuthn '{wa.name}' (last use {wa.last_used.strftime(UI_DEFAULT_DATETIME_FORMAT)})"
            for wa in user.webauthns
        ]
        + (["TOTP"] if user.has_totp else [])
    )

    click.echo(textwrap.dedent(f"""
    You are about to remove multi-factor authentication for user:
    {user.name} ({user.email})
    
    The user currently has the following methods enabled:
    - {auth_methods}
    
    After this, the user will be able to log in with their password.
    
    It is your own responsibility to determine that the legitimate
    user has lost access to their two-factor methods.
    The user will be notified of this change.
    """))
    click.confirm(f"Are you sure you want to remove two-factor authentication for {email}?", abort=True)
    for webauthn in user.webauthns:
        session_provider.session.delete(webauthn)
    user.totp_secret = None
    user.totp_last_used = None
    session_provider.session.add(user)

    click.echo("Two-factor authentication has been removed.")
    logger.info(f"cleared two-factor authentication for user {user.email} ({user.pk})")
    send_authentication_change_mail(
        user, request=None, msg="All two-factor authentication methods were removed by an IRRD administrator."
    )


@cli.command()
@click.argument("email")
@click.option("--enable/--disable", default=True)
@check_readonly_standby
@session_provider_manager_sync
def user_change_override(email: str, enable: bool, session_provider: ORMSessionProvider):
    """
    Change the override permission for user EMAIL.
    """
    user = find_user(session_provider, email)

    if not user.has_mfa:
        raise click.ClickException(
            "User has no two-factor methods enabled, which is required to add override."
        )

    if enable and user.override:
        raise click.ClickException("User already has override permission.")

    if not enable and not user.override:
        raise click.ClickException("User already has no override permission.")

    if enable:
        click.echo(textwrap.dedent(f"""
        You are about to assign override permission for user:
        {user.name} ({user.email})
    
        This will allow the user to edit any object in the database.
        """))
        click.confirm(f"Are you sure you want to assign this permission to {email}?", abort=True)

    user.override = enable
    session_provider.session.add(user)

    enabled_str = "enabled" if enable else "disabled"
    click.echo(f"Override permission has been {enabled_str}.")
    logger.info(f"override {enabled_str} for user {user.email} ({user.pk})")


@cli.group()
def nrtm4():
    """Manage NRTMv4 status."""
    pass  # pragma: no cover


@nrtm4.command()
@click.argument("source")
@check_readonly_standby
@session_provider_manager_sync
def client_clear_known_keys(source: str, session_provider: ORMSessionProvider):
    """
    Remove the known keys from the database for SOURCE.

    IRRD stores these known keys in the DB as part of NRTMv4 key rotation, to reflect
    the key currently used for signature validation. Explicit clearing is
    required when missing a key rotation window or switching to a different
    NRTMv4 server for the same source.

    After clearing, NRTMv4 client signature validation will revert to the key in
    sources.{source}.nrtm4_client_initial_public_key for the next NRTMv4
    update, and again store the current key after the first successful update.
    """
    if not get_setting(f"sources.{source}.nrtm4_client_initial_public_key"):
        raise click.ClickException(f"Source {source} is not configured as an NRTMv4 client")
    query = session_provider.session.query(RPSLDatabaseStatus).filter_by(source=source)
    status = session_provider.run_sync(query.one)
    if not status:
        raise click.ClickException(f"No current known keys for source {source}")
    status.nrtm4_client_current_key = None
    status.nrtm4_client_next_key = None
    session_provider.session.add(status)

    click.echo(
        "Known keys removed, expected key is now taken from the"
        f" sources.{source}.nrtm4_client_initial_public_key setting.\nNote that other data for this source is"
        " not reloaded - for that use irrd_mirror_force_reload."
    )
    logger.info(f"{source}: known NRTMv4 client keys removed")


@nrtm4.command()
def generate_private_key():
    """
    Generate a new private key for an NRTMv4 server.
    """
    private_key = ECKey.generate_key()
    private_key_str = eckey_private_key_as_str(private_key)
    public_key_str = eckey_public_key_as_str(private_key)

    click.echo(
        f"Private key:\n\n{private_key_str}\nCorresponding public key:\n\n{public_key_str}\nNote: this key"
        " has not been configured in IRRD, that is a manual step. This is only a convenience command."
    )


@nrtm4.command()
@click.argument("source")
def server_show_public_key(source: str):
    """
    Show the public key(s) matching the currently configured private keys.
    """
    private_key = eckey_from_config(f"sources.{source}.nrtm4_server_private_key", permit_empty=True)
    if not private_key:
        raise click.ClickException(f"Source {source} is not configured as an NRTMv4 server")
    public_key_str = eckey_public_key_as_str(private_key)

    click.echo(
        f"Current public key for {source} NRTMv4 server (from nrtm4_server_private_key):\n\n{public_key_str}"
    )

    next_private_key = eckey_from_config(f"sources.{source}.nrtm4_server_private_key_next", permit_empty=True)
    if next_private_key:
        next_public_key_str = eckey_public_key_as_str(next_private_key)
        click.echo(f"Next key (from nrtm4_server_private_key_next):\n{next_public_key_str}")


def find_user(session_provider: ORMSessionProvider, email: str) -> AuthUser:
    query = session_provider.session.query(AuthUser).filter_by(email=email)
    user = session_provider.run_sync(query.one)
    if not user:
        raise click.ClickException(f"No user found for {email}.")
    return user


if __name__ == "__main__":
    cli()
