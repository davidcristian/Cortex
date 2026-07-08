"""Behavior tests for SmtpSender over a fake smtplib (no server, no network).

Proves the composition (From is the authenticated identity, never a parameter), the TLS
mode selection, and the cert-verification escape hatches; the live send round-trip is
test_email_live.py.
"""
# The autouse env-isolation fixture below is invoked by pytest, not statically
# referenced. Pyright cannot see that. (Same class as server.py's decorator handlers.)
# pyright: reportUnusedFunction=false

import smtplib
import ssl
from email.message import EmailMessage
from typing import Self

import pytest
from pydantic import SecretStr, ValidationError

from cortex_email import SmtpConfig, SmtpSender
from cortex_email.config import TlsSecurity

_SMTP_ENV = (
    "CORTEX_EMAIL_SEND_ENABLED",
    "CORTEX_EMAIL_SMTP_ENABLED",
    "CORTEX_EMAIL_SMTP_USER",
    "CORTEX_EMAIL_SMTP_PASSWORD",
    "CORTEX_EMAIL_SMTP_HOST",
    "CORTEX_EMAIL_SMTP_PORT",
    "CORTEX_EMAIL_SMTP_SECURITY",
    "CORTEX_EMAIL_SMTP_TLS_INSECURE",
    "CORTEX_EMAIL_SMTP_CA_CERT",
)


@pytest.fixture(autouse=True)
def _clean_smtp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # A developer who sourced ~/.cortex/email.env before `just check` would otherwise leak
    # send config into these config assertions; isolate every SMTP var so the tests pin the
    # code's own defaults, not the shell's. Tests that need a var set it after this runs.
    for name in _SMTP_ENV:
        monkeypatch.delenv(name, raising=False)


class _FakeSmtp:
    """Stands in for smtplib.SMTP / SMTP_SSL: context-manager, starttls, login, send."""

    def __init__(self) -> None:
        self.starttls_contexts: list[ssl.SSLContext] = []
        self.login_calls: list[tuple[str, str]] = []
        self.sent: list[EmailMessage] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def starttls(self, context: ssl.SSLContext) -> None:
        self.starttls_contexts.append(context)

    def login(self, user: str, password: str) -> None:
        self.login_calls.append((user, password))

    def send_message(self, message: EmailMessage) -> None:
        self.sent.append(message)


def _config(*, security: TlsSecurity = "starttls", tls_insecure: bool = False) -> SmtpConfig:
    return SmtpConfig(
        host="mail.local",
        port=1025,
        user="me@example.com",
        password=SecretStr("bridge-pass"),
        security=security,
        tls_insecure=tls_insecure,
    )


def _patch(
    monkeypatch: pytest.MonkeyPatch, client: _FakeSmtp, security: TlsSecurity
) -> dict[str, object]:
    captured: dict[str, object] = {}

    if security == "starttls":

        def plain_factory(host: str, port: int) -> _FakeSmtp:
            captured["host"], captured["port"] = host, port
            return client

        monkeypatch.setattr(smtplib, "SMTP", plain_factory)
    else:

        def ssl_factory(host: str, port: int, context: ssl.SSLContext) -> _FakeSmtp:
            captured["host"], captured["port"], captured["ssl"] = host, port, context
            return client

        monkeypatch.setattr(smtplib, "SMTP_SSL", ssl_factory)
    return captured


def test_send_composes_from_the_authenticated_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    line = SmtpSender(_config()).send("you@example.com", "Hi", "hello there")
    (message,) = client.sent
    assert message["From"] == "me@example.com"  # never a parameter, so no sender spoofing
    assert message["To"] == "you@example.com"
    assert message["Subject"] == "Hi"
    assert message.get_content().strip() == "hello there"
    assert line == 'email sent to you@example.com (subject: "Hi")'


def test_starttls_upgrades_then_logs_in(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    captured = _patch(monkeypatch, client, "starttls")
    SmtpSender(_config()).send("you@example.com", "s", "b")
    assert (captured["host"], captured["port"]) == ("mail.local", 1025)
    (context,) = client.starttls_contexts
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert client.login_calls == [("me@example.com", "bridge-pass")]


def test_ssl_mode_uses_implicit_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    captured = _patch(monkeypatch, client, "ssl")
    SmtpSender(_config(security="ssl")).send("you@example.com", "s", "b")
    context = captured["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert client.starttls_contexts == []  # implicit TLS: no upgrade call
    assert client.login_calls == [("me@example.com", "bridge-pass")]


def test_insecure_tls_disables_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    SmtpSender(_config(tls_insecure=True)).send("you@example.com", "s", "b")
    (context,) = client.starttls_contexts
    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False


def test_send_stays_disabled_by_default() -> None:
    assert SmtpConfig().enabled is False


def test_enabling_send_without_credentials_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_EMAIL_SEND_ENABLED", "true")
    with pytest.raises(ValidationError, match="CORTEX_EMAIL_SMTP_USER"):
        SmtpConfig()


def test_enabling_send_with_credentials_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_EMAIL_SEND_ENABLED", "true")
    monkeypatch.setenv("CORTEX_EMAIL_SMTP_USER", "me@example.com")
    monkeypatch.setenv("CORTEX_EMAIL_SMTP_PASSWORD", "pw")
    config = SmtpConfig()
    assert config.enabled is True
    assert config.port == 1025  # the Bridge SMTP loopback default


def test_the_smtp_prefixed_enable_name_is_not_a_second_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Distrust green: prove CORTEX_EMAIL_SMTP_ENABLED does NOT enable send. The one switch
    # is CORTEX_EMAIL_SEND_ENABLED, so a stray prefixed var can't silently open the outbound
    # path (ADR-0022; no validate_by_name on SmtpConfig).
    monkeypatch.setenv("CORTEX_EMAIL_SMTP_ENABLED", "true")
    monkeypatch.setenv("CORTEX_EMAIL_SMTP_USER", "me@example.com")
    monkeypatch.setenv("CORTEX_EMAIL_SMTP_PASSWORD", "pw")
    assert SmtpConfig().enabled is False


def test_send_rejects_a_newline_in_the_recipient(monkeypatch: pytest.MonkeyPatch) -> None:
    # Header injection is refused in code, not left to the interpreter's patch level (ADR-0022).
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    with pytest.raises(ValueError, match="recipient must not contain a newline"):
        SmtpSender(_config()).send("you@example.com\r\nBcc: evil@x.test", "Hi", "b")
    assert client.sent == []  # never reached the wire


def test_send_rejects_a_newline_in_the_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    with pytest.raises(ValueError, match="subject must not contain a newline"):
        SmtpSender(_config()).send("you@example.com", "Hi\nBcc: evil@x.test", "b")
    assert client.sent == []
