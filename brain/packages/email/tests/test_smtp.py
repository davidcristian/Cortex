# The autouse fixture below is called by pytest and never referenced, so pyright reads it
# as unused.
# pyright: reportUnusedFunction=false

import smtplib
import ssl

import pytest
from pydantic import ValidationError
from smtp_stub import CREDENTIAL, FakeSmtp, config, patch_smtp

from cortex_email import EmailAttachment, EmailDraft, SendError, SmtpConfig, SmtpSender

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
    # A developer who sourced ~/.cortex/email.env before running the suite would otherwise
    # leak send config into these assertions about the code's own defaults.
    for name in _SMTP_ENV:
        monkeypatch.delenv(name, raising=False)


def test_send_composes_from_the_authenticated_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeSmtp()
    patch_smtp(monkeypatch, client, "starttls")
    line = SmtpSender(config()).send(EmailDraft("you@example.com", "Hi", "hello there"))
    (message,) = client.sent
    assert message["From"] == "me@example.com"
    assert message["To"] == "you@example.com"
    assert message["Subject"] == "Hi"
    assert message.get_content().strip() == "hello there"
    assert message["Cc"] is None
    assert message["Bcc"] is None
    assert message.get_content_type() == "text/plain"
    assert line == 'email sent to you@example.com (subject: "Hi")'


def test_starttls_upgrades_then_logs_in(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeSmtp()
    captured = patch_smtp(monkeypatch, client, "starttls")
    SmtpSender(config()).send(EmailDraft("you@example.com", "s", "b"))
    assert (captured["host"], captured["port"]) == ("mail.local", 1025)
    (context,) = client.starttls_contexts
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert client.login_calls == [("me@example.com", "bridge-pass")]


def test_ssl_mode_uses_implicit_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeSmtp()
    captured = patch_smtp(monkeypatch, client, "ssl")
    SmtpSender(config(security="ssl")).send(EmailDraft("you@example.com", "s", "b"))
    context = captured["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert client.starttls_contexts == []
    assert client.login_calls == [("me@example.com", "bridge-pass")]


def test_insecure_tls_disables_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeSmtp()
    patch_smtp(monkeypatch, client, "starttls")
    SmtpSender(config(tls_insecure=True)).send(EmailDraft("you@example.com", "s", "b"))
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
    assert config.port == 1025


def test_the_smtp_prefixed_enable_name_is_not_a_second_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_EMAIL_SMTP_ENABLED", "true")
    monkeypatch.setenv("CORTEX_EMAIL_SMTP_USER", "me@example.com")
    monkeypatch.setenv("CORTEX_EMAIL_SMTP_PASSWORD", "pw")
    assert SmtpConfig().enabled is False


def test_send_composes_cc_bcc_and_an_html_alternative(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeSmtp()
    patch_smtp(monkeypatch, client, "starttls")
    line = SmtpSender(config()).send(
        EmailDraft(
            "you@example.com",
            "Hi",
            "plain body",
            cc="cc@example.com",
            bcc="bcc@example.com",
            html="<p>rich</p>",
        )
    )
    (message,) = client.sent
    assert message["Cc"] == "cc@example.com"
    assert message["Bcc"] == "bcc@example.com"
    assert message.get_content_type() == "multipart/alternative"
    plain, html = message.iter_parts()
    assert plain.get_content_type() == "text/plain"
    assert plain.get_content().strip() == "plain body"
    assert html.get_content_type() == "text/html"
    assert html.get_content().strip() == "<p>rich</p>"
    assert line == 'email sent to you@example.com (subject: "Hi")'


def test_send_attaches_authored_text(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeSmtp()
    patch_smtp(monkeypatch, client, "starttls")
    line = SmtpSender(config()).send(
        EmailDraft(
            "you@example.com",
            "Hi",
            "see attached",
            attachments=(EmailAttachment("notes.md", "# Notes\n\n- one\n", "markdown"),),
        )
    )
    (message,) = client.sent
    assert message.get_content_type() == "multipart/mixed"
    body, attached = message.iter_parts()
    assert body.get_content_type() == "text/plain"
    assert body.get_content().strip() == "see attached"
    assert attached.get_content_type() == "text/markdown"
    assert attached.get_filename() == "notes.md"
    assert attached.get_content().strip() == "# Notes\n\n- one"
    assert attached.get_content_disposition() == "attachment"
    assert line == 'email sent to you@example.com (subject: "Hi")'


def test_an_attachment_keeps_the_html_alternative_intact(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeSmtp()
    patch_smtp(monkeypatch, client, "starttls")
    SmtpSender(config()).send(
        EmailDraft(
            "you@example.com",
            "Hi",
            "plain body",
            html="<p>rich</p>",
            attachments=(EmailAttachment("data.csv", "a,b\n1,2\n", "csv"),),
        )
    )
    (message,) = client.sent
    assert message.get_content_type() == "multipart/mixed"
    alternative, attached = message.iter_parts()
    assert alternative.get_content_type() == "multipart/alternative"
    plain, html = alternative.iter_parts()
    assert (plain.get_content_type(), html.get_content_type()) == ("text/plain", "text/html")
    assert attached.get_content_type() == "text/csv"
    assert attached.get_filename() == "data.csv"


def test_a_refused_login_raises_send_error_without_the_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeSmtp()
    client.login_error = smtplib.SMTPAuthenticationError(535, b"5.7.8 authentication failed")
    patch_smtp(monkeypatch, client, "ssl")
    with pytest.raises(SendError, match="authentication failed") as caught:
        SmtpSender(config(security="ssl")).send(EmailDraft("you@example.com", "Hi", "b"))
    assert CREDENTIAL not in str(caught.value)
    assert isinstance(caught.value.__cause__, smtplib.SMTPAuthenticationError)
    assert client.sent == []
