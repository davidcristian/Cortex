"""Email MCP server: read-only IMAP + opt-in SMTP send (docs/modules/brain-email.md)."""

from cortex_email.config import EmailConfig, SmtpConfig
from cortex_email.imap import ImapMailbox
from cortex_email.reader import EmailReader, Mailbox, RawEmail
from cortex_email.server import build_server, main
from cortex_email.smtp import EmailSender, SmtpSender
from cortex_email.values import EmailDetail, EmailDraft, EmailSummary

__all__ = [
    "EmailConfig",
    "EmailDetail",
    "EmailDraft",
    "EmailReader",
    "EmailSender",
    "EmailSummary",
    "ImapMailbox",
    "Mailbox",
    "RawEmail",
    "SmtpConfig",
    "SmtpSender",
    "build_server",
    "main",
]
