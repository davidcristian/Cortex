"""Read-only IMAP MCP server for email (docs/modules/brain-email.md)."""

from cortex_email.config import EmailConfig
from cortex_email.imap import ImapMailbox
from cortex_email.reader import EmailReader, Mailbox, RawEmail
from cortex_email.server import build_server, main
from cortex_email.values import EmailDetail, EmailSummary

__all__ = [
    "EmailConfig",
    "EmailDetail",
    "EmailReader",
    "EmailSummary",
    "ImapMailbox",
    "Mailbox",
    "RawEmail",
    "build_server",
    "main",
]
