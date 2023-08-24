import pytest
from click.testing import CliRunner

from irrd.scripts.irrd_control import (
    cli,
    client_clear_known_keys,
    user_change_override,
    user_mfa_clear,
)
from irrd.storage.models import AuthWebAuthn, RPSLDatabaseStatus
from irrd.utils.factories import AuthWebAuthnFactory


def test_cli():
    runner = CliRunner()
    result = runner.invoke(cli)
    assert result.exit_code == 0


@pytest.fixture
def smtpd_override(config_override, smtpd):
    config_override(
        {
            "email": {"smtp": f"localhost:{smtpd.port}", "from": "irrd@example.net"},
        }
    )
    yield smtpd


class TestUserMfaClear:
    def test_valid(self, irrd_db_session_with_user, smtpd_override):
        session_provider, user = irrd_db_session_with_user
        wn_token = AuthWebAuthnFactory(user_id=str(user.pk))
        wn_token_name = wn_token.name

        runner = CliRunner()
        result = runner.invoke(user_mfa_clear, [user.email], input="y")
        assert result.exit_code == 0
        assert wn_token_name in result.output
        assert "TOTP" in result.output

        assert not session_provider.run_sync(session_provider.session.query(AuthWebAuthn).one)
        session_provider.session.refresh(user)
        assert not user.totp_secret
        assert len(smtpd_override.messages) == 1
        assert "removed by an IRRD administrator" in smtpd_override.messages[0].as_string()

    def test_rejected_confirmation(self, irrd_db_session_with_user, smtpd_override):
        session_provider, user = irrd_db_session_with_user
        AuthWebAuthnFactory(user_id=str(user.pk))

        runner = CliRunner()
        result = runner.invoke(user_mfa_clear, [user.email], input="n")
        assert result.exit_code == 1

        assert session_provider.run_sync(session_provider.session.query(AuthWebAuthn).one)
        session_provider.session.refresh(user)
        assert user.totp_secret
        assert not smtpd_override.messages

    def test_user_has_no_mfa(self, irrd_db_session_with_user, smtpd_override):
        session_provider, user = irrd_db_session_with_user
        user.totp_secret = None
        session_provider.session.commit()

        runner = CliRunner()
        result = runner.invoke(user_mfa_clear, [user.email])
        assert result.exit_code == 1
        assert "no two-factor methods enabled" in result.output
        assert not smtpd_override.messages

    def test_user_does_not_exist(self, irrd_db_session_with_user, smtpd_override):
        session_provider, user = irrd_db_session_with_user
        user.totp_secret = None
        session_provider.session.commit()

        runner = CliRunner()
        result = runner.invoke(user_mfa_clear, ["invalid"])
        assert result.exit_code == 1
        assert "No user found" in result.output
        assert not smtpd_override.messages

    def test_readonly_standby(self, irrd_db_session_with_user, config_override, smtpd_override):
        config_override({"readonly_standby": True})

        runner = CliRunner()
        result = runner.invoke(user_mfa_clear, ["user.email"])
        assert result.exit_code == 1
        assert "readonly_standby" in result.output
        assert not smtpd_override.messages


class TestUserChangeOverride:
    def test_valid_enable(self, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user

        runner = CliRunner()
        result = runner.invoke(user_change_override, [user.email, "--enable"], input="y")
        assert result.exit_code == 0

        session_provider.session.refresh(user)
        assert user.override

    def test_valid_disable(self, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        user.override = True
        session_provider.session.commit()

        runner = CliRunner()
        result = runner.invoke(user_change_override, [user.email, "--disable"], input="y")
        assert result.exit_code == 0

        session_provider.session.refresh(user)
        assert not user.override

    def test_enable_already_enabled(self, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        user.override = True
        session_provider.session.commit()

        runner = CliRunner()
        result = runner.invoke(user_change_override, [user.email, "--enable"], input="y")
        assert result.exit_code == 1
        assert "already has" in result.output

        session_provider.session.refresh(user)
        assert user.override

    def test_disable_already_disabled(self, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user

        runner = CliRunner()
        result = runner.invoke(user_change_override, [user.email, "--disable"], input="y")
        assert result.exit_code == 1
        assert "already has" in result.output

        session_provider.session.refresh(user)
        assert not user.override

    def test_rejected_confirmation(self, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user

        runner = CliRunner()
        result = runner.invoke(user_change_override, [user.email, "--enable"], input="n")
        assert result.exit_code == 1

        session_provider.session.refresh(user)
        assert not user.override

    def test_user_does_not_exist(self, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user

        runner = CliRunner()
        result = runner.invoke(user_change_override, [user.email, "--enable"], input="y")
        assert result.exit_code == 0

        session_provider.session.refresh(user)
        assert user.override

    def test_no_mfa(self, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        user.totp_secret = None
        session_provider.session.commit()

        runner = CliRunner()
        result = runner.invoke(user_change_override, [user.email, "--enable"], input="y")
        assert result.exit_code == 1
        assert "has no two-factor" in result.output

    def test_readonly_standby(self, irrd_db_session_with_user, config_override):
        config_override({"readonly_standby": True})
        session_provider, user = irrd_db_session_with_user

        runner = CliRunner()
        result = runner.invoke(user_change_override, [user.email, "--enable"], input="y")
        assert result.exit_code == 1
        assert "readonly_standby" in result.output


class TestNRTMv4ClientClearKnownKeys:
    def test_valid_clear(self, irrd_db_session_with_user, config_override):
        config_override({"sources": {"TEST2": {"nrtm4_client_initial_public_key": "key"}}})

        session_provider, _ = irrd_db_session_with_user
        status = RPSLDatabaseStatus(
            source="TEST2", force_reload=False, nrtm4_client_current_key="key", nrtm4_client_next_key="key"
        )
        session_provider.session.add(status)
        session_provider.session.commit()

        runner = CliRunner()
        result = runner.invoke(client_clear_known_keys, ["TEST2"])
        assert result.exit_code == 0, result.output
        assert "keys removed" in result.output

        session_provider.session.refresh(status)
        assert not status.nrtm4_client_next_key
        assert not status.nrtm4_client_next_key

    def test_no_current_state(self, irrd_db_session_with_user, config_override):
        config_override({"sources": {"TEST2": {"nrtm4_client_initial_public_key": "key"}}})

        session_provider, _ = irrd_db_session_with_user

        runner = CliRunner()
        result = runner.invoke(client_clear_known_keys, ["TEST2"])
        assert result.exit_code == 1
        assert "No current known" in result.output

    def test_no_nrtm4_client_configured(self, irrd_db_session_with_user, config_override):
        session_provider, _ = irrd_db_session_with_user

        runner = CliRunner()
        result = runner.invoke(client_clear_known_keys, ["TEST2"])
        assert result.exit_code == 1, result.output
        assert "not configured as an NRTMv4 client" in result.output
