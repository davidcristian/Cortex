"""SmtpSender: the send twin of ImapMailbox, over ProtonMail Bridge SMTP (ADR-0022).

One message per call, connecting per call (the sidecar holds no SMTP state, matching the
`ImapMailbox` discipline). The sender authenticates as the Bridge user and sends as that user:
`From` is the authenticated address, never a parameter, so the tool cannot spoof a sender. The
`EmailDraft` (to/subject/body plus optional cc/bcc and an html alternative) is exactly what the
user approves brain-side (ADR-0022 puts the gate and confirmation in the brain's dispatcher, not
here); cc/bcc get the same CR/LF header-injection check as the recipient, and a Bcc travels in the
envelope but is stripped from the transmitted message by `send_message`. Real network I/O lives
only in `send`; CI covers the composition and TLS selection over a fake smtplib, and the live
round-trip is `test_email_live.py`.
"""

import re
import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from cortex_email.config import SmtpConfig
from cortex_email.values import (
    MAX_ATTACHMENT_CHARS,
    MAX_ATTACHMENTS,
    MAX_FILENAME_CHARS,
    EmailAttachment,
    EmailDraft,
)

# A MIME subtype token: no "/" (so "text/" stays a prefix the caller cannot escape), no
# space, no ";" that could open a parameter, and nothing a header value must not hold.
_SUBTYPE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,62}$")


def _reject_header_injection(field: str, value: str) -> None:
    """Raise if ``value`` carries a CR/LF that could inject an extra email header."""
    if "\r" in value or "\n" in value:
        msg = f"{field} must not contain a newline (header-injection attempt)"
        raise ValueError(msg)


def _reject_bad_attachments(attachments: tuple[EmailAttachment, ...]) -> None:
    """Raise unless every attachment has a usable filename and subtype and fits the bounds."""
    if len(attachments) > MAX_ATTACHMENTS:
        msg = f"a message may carry at most {MAX_ATTACHMENTS} attachments"
        raise ValueError(msg)
    total = sum(len(attachment.content) for attachment in attachments)
    if total > MAX_ATTACHMENT_CHARS:
        msg = f"attachments must total at most {MAX_ATTACHMENT_CHARS} characters, not {total}"
        raise ValueError(msg)
    for attachment in attachments:
        # The filename is a header value and gets header treatment; the content is a payload.
        _reject_header_injection("attachment filename", attachment.filename)
        if not attachment.filename:
            msg = "attachment filename must not be empty"
            raise ValueError(msg)
        if len(attachment.filename) > MAX_FILENAME_CHARS:
            msg = f"attachment filename must be at most {MAX_FILENAME_CHARS} characters"
            raise ValueError(msg)
        if not _SUBTYPE_TOKEN.match(attachment.subtype):
            msg = f"attachment subtype {attachment.subtype!r} is not a MIME subtype token"
            raise ValueError(msg)


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
        # Reject header injection explicitly rather than trust the interpreter: a CR/LF in a
        # header value can smuggle extra headers (a Bcc exfil) on some CPython patch levels
        # (the 3.12.0-3.12.4 window). `body`/`html` are payload, not headers, so unrestricted.
        _reject_header_injection("recipient", draft.to)
        _reject_header_injection("subject", draft.subject)
        _reject_header_injection("cc", draft.cc)
        _reject_header_injection("bcc", draft.bcc)
        _reject_bad_attachments(draft.attachments)
        message = EmailMessage()
        message["From"] = self._config.user  # the authenticated identity, never a parameter
        message["To"] = draft.to
        message["Subject"] = draft.subject
        if draft.cc:
            message["Cc"] = draft.cc
        if draft.bcc:
            # send_message reads To+Cc+Bcc for the envelope recipients, then deletes Bcc from
            # the transmitted copy, so a Bcc address stays hidden from the To/Cc readers (stdlib).
            message["Bcc"] = draft.bcc
        message.set_content(draft.body)
        if draft.html:
            message.add_alternative(draft.html, subtype="html")
        for attachment in draft.attachments:
            # The str payload keeps this a text/<subtype> part: add_attachment takes no
            # maintype for a string, which is how "the assistant attaches what it wrote"
            # stays true by construction rather than by a check. Adding one wraps whatever
            # the body shapes built into a multipart/mixed, alternative and all (stdlib).
            message.add_attachment(
                attachment.content, subtype=attachment.subtype, filename=attachment.filename
            )
        return message

    def send(self, draft: EmailDraft) -> str:
        """Send the message and report one human-readable confirmation line."""
        message = self._compose(draft)
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
        return f'email sent to {draft.to} (subject: "{draft.subject}")'
