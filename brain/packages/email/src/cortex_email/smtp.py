"""SmtpSender: the send twin of ImapMailbox, over ProtonMail Bridge SMTP (ADR-0022).

One plain-text message per call, connecting per call (the sidecar holds no SMTP state, matching
the `ImapMailbox` discipline). The sender authenticates as the Bridge user and sends **as
that user**: `From` is the authenticated address, never a parameter, so the tool cannot
spoof a sender. `{to, subject, body}` is exactly the draft the user approves brain-side
(ADR-0022 puts the gate and confirmation in the brain's dispatcher, not here). Real
network I/O lives only in `send`; CI covers the composition and TLS selection over a fake
smtplib, and the live round-trip is `test_email_live.py`.
"""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from cortex_email.config import SmtpConfig


class EmailSender(Protocol):
    """What the server's send tool needs: one blocking send, returning a readable line."""

    def send(self, to: str, subject: str, body: str) -> str: ...


class SmtpSender:
    """Send one message per call over SMTP with STARTTLS or implicit TLS."""

    def __init__(self, config: SmtpConfig) -> None:
        self._config = config

    def _ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(cafile=self._config.ca_cert or None)
        if self._config.tls_insecure:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context

    def _compose(self, to: str, subject: str, body: str) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self._config.user  # the authenticated identity, never a parameter
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        return message

    def send(self, to: str, subject: str, body: str) -> str:
        """Send the message and report one human-readable confirmation line."""
        message = self._compose(to, subject, body)
        config = self._config
        context = self._ssl_context()
        if config.security == "starttls":
            with smtplib.SMTP(config.host, config.port) as client:
                client.starttls(context=context)
                client.login(config.user, config.password.get_secret_value())
                client.send_message(message)
        else:
            with smtplib.SMTP_SSL(config.host, config.port, context=context) as client:
                client.login(config.user, config.password.get_secret_value())
                client.send_message(message)
        return f'email sent to {to} (subject: "{subject}")'
