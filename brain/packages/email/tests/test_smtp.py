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

from cortex_email import EmailAttachment, EmailDraft, SmtpConfig, SmtpSender
from cortex_email.config import TlsSecurity
from cortex_email.smtp import MAX_ATTACHMENT_CHARS, MAX_ATTACHMENTS, MAX_FILENAME_CHARS

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
    line = SmtpSender(_config()).send(EmailDraft("you@example.com", "Hi", "hello there"))
    (message,) = client.sent
    assert message["From"] == "me@example.com"  # never a parameter, so no sender spoofing
    assert message["To"] == "you@example.com"
    assert message["Subject"] == "Hi"
    assert message.get_content().strip() == "hello there"
    # A plain draft stays a single text/plain part: no cc/bcc headers, no html alternative.
    assert message["Cc"] is None
    assert message["Bcc"] is None
    assert message.get_content_type() == "text/plain"
    assert line == 'email sent to you@example.com (subject: "Hi")'


def test_starttls_upgrades_then_logs_in(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    captured = _patch(monkeypatch, client, "starttls")
    SmtpSender(_config()).send(EmailDraft("you@example.com", "s", "b"))
    assert (captured["host"], captured["port"]) == ("mail.local", 1025)
    (context,) = client.starttls_contexts
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert client.login_calls == [("me@example.com", "bridge-pass")]


def test_ssl_mode_uses_implicit_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    captured = _patch(monkeypatch, client, "ssl")
    SmtpSender(_config(security="ssl")).send(EmailDraft("you@example.com", "s", "b"))
    context = captured["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert client.starttls_contexts == []  # implicit TLS: no upgrade call
    assert client.login_calls == [("me@example.com", "bridge-pass")]


def test_insecure_tls_disables_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    SmtpSender(_config(tls_insecure=True)).send(EmailDraft("you@example.com", "s", "b"))
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
        SmtpSender(_config()).send(EmailDraft("you@example.com\r\nBcc: evil@x.test", "Hi", "b"))
    assert client.sent == []  # never reached the wire


def test_send_rejects_a_newline_in_the_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    with pytest.raises(ValueError, match="subject must not contain a newline"):
        SmtpSender(_config()).send(EmailDraft("you@example.com", "Hi\nBcc: evil@x.test", "b"))
    assert client.sent == []


def test_send_composes_cc_bcc_and_an_html_alternative(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    line = SmtpSender(_config()).send(
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
    # The Bcc header is composed here; smtplib.send_message strips it from the transmitted
    # copy while still delivering to it, so the header being present on the composed message
    # (which never touches a real server in this test) is correct.
    assert message["Bcc"] == "bcc@example.com"
    assert message.get_content_type() == "multipart/alternative"
    plain, html = message.iter_parts()
    assert plain.get_content_type() == "text/plain"
    assert plain.get_content().strip() == "plain body"
    assert html.get_content_type() == "text/html"
    assert html.get_content().strip() == "<p>rich</p>"
    assert line == 'email sent to you@example.com (subject: "Hi")'


def test_send_rejects_a_newline_in_cc(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    with pytest.raises(ValueError, match="cc must not contain a newline"):
        SmtpSender(_config()).send(
            EmailDraft("you@example.com", "Hi", "b", cc="c@example.com\r\nBcc: evil@x.test")
        )
    assert client.sent == []


def test_send_rejects_a_newline_in_bcc(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    with pytest.raises(ValueError, match="bcc must not contain a newline"):
        SmtpSender(_config()).send(
            EmailDraft("you@example.com", "Hi", "b", bcc="b@example.com\r\nTo: evil@x.test")
        )
    assert client.sent == []


def test_send_attaches_authored_text(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    line = SmtpSender(_config()).send(
        EmailDraft(
            "you@example.com",
            "Hi",
            "see attached",
            attachments=(EmailAttachment("notes.md", "# Notes\n\n- one\n", "markdown"),),
        )
    )
    (message,) = client.sent
    # One attachment wraps the body in a multipart/mixed; the body part is untouched.
    assert message.get_content_type() == "multipart/mixed"
    body, attached = message.iter_parts()
    assert body.get_content_type() == "text/plain"
    assert body.get_content().strip() == "see attached"
    assert attached.get_content_type() == "text/markdown"  # never anything but text/*
    assert attached.get_filename() == "notes.md"
    assert attached.get_content().strip() == "# Notes\n\n- one"
    assert attached.get_content_disposition() == "attachment"
    assert line == 'email sent to you@example.com (subject: "Hi")'


def test_an_attachment_keeps_the_html_alternative_intact(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    SmtpSender(_config()).send(
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
    # The alternative the richer-shapes addendum composes survives inside the mixed part, so a
    # reader still picks html over plain and the attachment is a sibling of the pair.
    assert alternative.get_content_type() == "multipart/alternative"
    plain, html = alternative.iter_parts()
    assert (plain.get_content_type(), html.get_content_type()) == ("text/plain", "text/html")
    assert attached.get_content_type() == "text/csv"
    assert attached.get_filename() == "data.csv"


def test_send_carries_the_maximum_attachment_count(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    SmtpSender(_config()).send(
        EmailDraft(
            "you@example.com",
            "Hi",
            "b",
            attachments=tuple(EmailAttachment(f"part{n}.txt", "x") for n in range(MAX_ATTACHMENTS)),
        )
    )
    (message,) = client.sent
    assert len(list(message.iter_parts())) == MAX_ATTACHMENTS + 1  # the body plus each file


def test_send_refuses_more_attachments_than_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    # Refused, not truncated: a dropped attachment is a send the user approved and did not get.
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    with pytest.raises(ValueError, match=f"at most {MAX_ATTACHMENTS} attachments"):
        SmtpSender(_config()).send(
            EmailDraft(
                "you@example.com",
                "Hi",
                "b",
                attachments=tuple(
                    EmailAttachment(f"part{n}.txt", "x") for n in range(MAX_ATTACHMENTS + 1)
                ),
            )
        )
    assert client.sent == []


def test_send_carries_attachments_up_to_the_character_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    half = MAX_ATTACHMENT_CHARS // 2
    SmtpSender(_config()).send(
        EmailDraft(
            "you@example.com",
            "Hi",
            "b",
            # Two parts summing to exactly the cap: the budget is the send's, not each file's.
            attachments=(
                EmailAttachment("a.txt", "a" * half),
                EmailAttachment("b.txt", "b" * half),
            ),
        )
    )
    assert len(client.sent) == 1


def test_the_character_budget_counts_characters_not_encoded_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A cap in bytes would make the same visible draft fit or not fit depending on its accents;
    # what the card shows and the history budget both count characters, so this does too.
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    SmtpSender(_config()).send(
        EmailDraft(
            "you@example.com",
            "Hi",
            "b",
            attachments=(EmailAttachment("accents.txt", "é" * MAX_ATTACHMENT_CHARS),),
        )
    )
    assert len(client.sent) == 1


def test_send_refuses_attachments_over_the_character_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    with pytest.raises(ValueError, match=f"at most {MAX_ATTACHMENT_CHARS} characters"):
        SmtpSender(_config()).send(
            EmailDraft(
                "you@example.com",
                "Hi",
                "b",
                attachments=(EmailAttachment("big.txt", "x" * (MAX_ATTACHMENT_CHARS + 1)),),
            )
        )
    assert client.sent == []


def test_send_rejects_a_newline_in_an_attachment_filename(monkeypatch: pytest.MonkeyPatch) -> None:
    # A filename rides Content-Disposition, so it gets the same header treatment as a recipient.
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    with pytest.raises(ValueError, match="attachment filename must not contain a newline"):
        SmtpSender(_config()).send(
            EmailDraft(
                "you@example.com",
                "Hi",
                "b",
                attachments=(EmailAttachment("n.txt\r\nBcc: evil@x.test", "x"),),
            )
        )
    assert client.sent == []


def test_send_rejects_a_nameless_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    with pytest.raises(ValueError, match="filename must not be empty"):
        SmtpSender(_config()).send(
            EmailDraft("you@example.com", "Hi", "b", attachments=(EmailAttachment("", "x"),))
        )
    assert client.sent == []


def test_send_rejects_an_oversized_attachment_filename(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    with pytest.raises(ValueError, match=f"at most {MAX_FILENAME_CHARS} characters"):
        SmtpSender(_config()).send(
            EmailDraft(
                "you@example.com",
                "Hi",
                "b",
                attachments=(EmailAttachment("n" * (MAX_FILENAME_CHARS + 1), "x"),),
            )
        )
    assert client.sent == []


@pytest.mark.parametrize(
    "subtype",
    [
        "text/csv",  # a maintype the caller does not get to choose
        "plain; boundary=x",  # a parameter smuggled into the Content-Type
        "plain\r\nX-Evil: y",  # header injection through the type
        "",  # no type at all
        "-plain",  # a token never starts with punctuation
    ],
)
def test_send_rejects_a_subtype_that_is_not_a_mime_token(
    monkeypatch: pytest.MonkeyPatch, subtype: str
) -> None:
    client = _FakeSmtp()
    _patch(monkeypatch, client, "starttls")
    with pytest.raises(ValueError, match="is not a MIME subtype token"):
        SmtpSender(_config()).send(
            EmailDraft(
                "you@example.com", "Hi", "b", attachments=(EmailAttachment("n.txt", "x", subtype),)
            )
        )
    assert client.sent == []
