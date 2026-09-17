"""SmtpSender: the send twin of ImapMailbox, over ProtonMail Bridge SMTP."""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from cortex_email.config import SmtpConfig
from cortex_email.drafts import confirmation, refuse_unsendable
from cortex_email.errors import SendError
from cortex_email.values import EmailDraft

_TRANSPORT_FAILURES = (smtplib.SMTPException, OSError)


class EmailSender(Protocol):
    """What the server's send tool needs: one blocking send, returning a readable line."""

    def send(self, draft: EmailDraft) -> str: ...


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

    def _compose(self, draft: EmailDraft) -> EmailMessage:
        refuse_unsendable(draft)
        message = EmailMessage()
        # The authenticated identity, never a parameter, so a draft cannot forge a sender.
        message["From"] = self._config.user
        message["To"] = draft.to
        message["Subject"] = draft.subject
        if draft.cc:
            message["Cc"] = draft.cc
        if draft.bcc:
            message["Bcc"] = draft.bcc
        message.set_content(draft.body)
        if draft.html:
            message.add_alternative(draft.html, subtype="html")
        # A str payload keeps this a text/<subtype> part: add_attachment takes no maintype for
        # a string, so only text the assistant wrote can be attached.
        for attachment in draft.attachments:
            message.add_attachment(
                attachment.content, subtype=attachment.subtype, filename=attachment.filename
            )
        return message

    def send(self, draft: EmailDraft) -> str:
        """Send the message and report one human-readable confirmation line."""
        message = self._compose(draft)
        try:
            refused = self._deliver(message)
        except _TRANSPORT_FAILURES as err:
            msg = f"the email was not sent: {err}"
            raise SendError(msg) from err
        return confirmation(draft, tuple(refused))

    def _deliver(self, message: EmailMessage) -> dict[str, tuple[int, bytes]]:
        """Connect, authenticate and hand over ``message``; return the recipients refused."""
        # send_message reads To, Cc and Bcc for the envelope recipients and then deletes Bcc
        # from the transmitted copy, so a Bcc address stays hidden from the other readers.
        config = self._config
        context = self._ssl_context()
        if config.security == "starttls":
            with smtplib.SMTP(config.host, config.port) as client:
                client.starttls(context=context)
                client.login(config.user, config.password.get_secret_value())
                return client.send_message(message)
        with smtplib.SMTP_SSL(config.host, config.port, context=context) as client:
            client.login(config.user, config.password.get_secret_value())
            return client.send_message(message)
