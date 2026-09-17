"""A stand-in for smtplib's two client classes, shared by every suite driving `SmtpSender`."""

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import getaddresses
from typing import Self

import pytest
from pydantic import SecretStr

from cortex_email import SmtpConfig
from cortex_email.config import TlsSecurity

CREDENTIAL = "bridge-pass"
REFUSAL: tuple[int, bytes] = (550, b"5.1.1 mailbox unavailable")


class FakeSmtp:
    """Stands in for smtplib.SMTP / SMTP_SSL: context-manager, starttls, login, send."""

    def __init__(self) -> None:
        self.starttls_contexts: list[ssl.SSLContext] = []
        self.login_calls: list[tuple[str, str]] = []
        self.sent: list[EmailMessage] = []
        self.refused: set[str] = set()
        self.login_error: smtplib.SMTPException | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def starttls(self, context: ssl.SSLContext) -> None:
        self.starttls_contexts.append(context)

    def login(self, user: str, password: str) -> None:
        self.login_calls.append((user, password))
        if self.login_error is not None:
            raise self.login_error

    def send_message(self, message: EmailMessage) -> dict[str, tuple[int, bytes]]:
        fields = [value for name in ("To", "Bcc", "Cc") for value in message.get_all(name, [])]
        recipients = [address for _, address in getaddresses(fields)]
        refused = {address: REFUSAL for address in recipients if address in self.refused}
        if len(refused) == len(recipients):
            raise smtplib.SMTPRecipientsRefused(refused)
        self.sent.append(message)
        return refused


def config(*, security: TlsSecurity = "starttls", tls_insecure: bool = False) -> SmtpConfig:
    """A send configuration pointing at a server nothing listens on."""
    return SmtpConfig(
        host="mail.local",
        port=1025,
        user="me@example.com",
        password=SecretStr(CREDENTIAL),
        security=security,
        tls_insecure=tls_insecure,
    )


def patch_smtp(
    monkeypatch: pytest.MonkeyPatch,
    client: FakeSmtp,
    security: TlsSecurity = "starttls",
    connect_error: OSError | None = None,
) -> dict[str, object]:
    """Route smtplib's client class for ``security`` to ``client``; return its build arguments."""
    captured: dict[str, object] = {}

    def connect() -> FakeSmtp:
        if connect_error is not None:
            raise connect_error
        return client

    if security == "starttls":

        def plain_factory(host: str, port: int) -> FakeSmtp:
            captured["host"], captured["port"] = host, port
            return connect()

        monkeypatch.setattr(smtplib, "SMTP", plain_factory)
    else:

        def ssl_factory(host: str, port: int, context: ssl.SSLContext) -> FakeSmtp:
            captured["host"], captured["port"], captured["ssl"] = host, port, context
            return connect()

        monkeypatch.setattr(smtplib, "SMTP_SSL", ssl_factory)
    return captured
