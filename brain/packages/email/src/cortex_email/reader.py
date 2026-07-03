"""EmailReader: parse raw RFC822 into email values over a read-only Mailbox port (ADR-0009).

The `Mailbox` port is the slice of IMAP the reader needs, returning raw message bytes; the
reader parses them with the stdlib ``email`` package into `EmailSummary`/`EmailDetail`. This
keeps the parsing (the real logic) pure and fully testable with canned RFC822, while the IMAP
I/O lives behind the port (the imap-tools adapter in ``imap.py``, or a fake in tests).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import Protocol, cast

from cortex_email.html import html_to_text
from cortex_email.values import EmailDetail, EmailSummary


@dataclass(frozen=True, slots=True)
class RawEmail:
    """A message as fetched: its IMAP uid and raw RFC822 bytes (headers-only or full)."""

    uid: str
    raw: bytes


class Mailbox(Protocol):
    """Read-only slice of IMAP the reader needs; the imap-tools adapter and a fake both match."""

    def list_folders(self) -> Sequence[str]: ...

    def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]: ...

    def fetch(self, folder: str, uid: str) -> RawEmail | None: ...


def _parse(raw: bytes) -> EmailMessage:
    return message_from_bytes(raw, EmailMessage, policy=policy.default)


def _header(msg: EmailMessage, name: str) -> str:
    return str(msg.get(name, ""))


def _body_text(msg: EmailMessage) -> str:
    # Prefer text/plain; fall back to text/html (most real mail is HTML-only) so the body is
    # not empty. An HTML body goes through the readable-text extraction, keeping the raw HTML
    # only when there is no prose to extract (e.g. an image-only body).
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is None:
        return ""
    part = cast("EmailMessage", body)
    content = str(part.get_content()).strip()
    if part.get_content_type() == "text/html":
        return html_to_text(content) or content
    return content


def _summary(item: RawEmail) -> EmailSummary:
    msg = _parse(item.raw)
    return EmailSummary(
        uid=item.uid,
        sender=_header(msg, "From"),
        subject=_header(msg, "Subject"),
        date=_header(msg, "Date"),
    )


def _detail(item: RawEmail) -> EmailDetail:
    msg = _parse(item.raw)
    return EmailDetail(
        uid=item.uid,
        sender=_header(msg, "From"),
        recipients=_header(msg, "To"),
        subject=_header(msg, "Subject"),
        date=_header(msg, "Date"),
        body=_body_text(msg),
    )


class EmailReader:
    """Read-only email use-case: folders, search-to-summaries, read-one-to-detail."""

    def __init__(self, mailbox: Mailbox) -> None:
        self._mailbox = mailbox

    def folders(self) -> Sequence[str]:
        """The mailbox folders available to read."""
        return self._mailbox.list_folders()

    def search(self, folder: str, query: str, limit: int) -> Sequence[EmailSummary]:
        """Summaries of the messages in ``folder`` matching the IMAP ``query`` (up to limit)."""
        return [_summary(item) for item in self._mailbox.search(folder, query, limit)]

    def read(self, folder: str, uid: str) -> EmailDetail | None:
        """The full message ``uid`` in ``folder``, or None when it does not exist."""
        item = self._mailbox.fetch(folder, uid)
        return _detail(item) if item is not None else None
