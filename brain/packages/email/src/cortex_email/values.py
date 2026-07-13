"""Email domain values: a search summary and a full message (pure data, no I/O)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmailSummary:
    """One search hit: enough to decide whether to read the full message."""

    uid: str
    sender: str
    subject: str
    date: str


@dataclass(frozen=True, slots=True)
class EmailDetail:
    """One full message: headers plus the plain-text body."""

    uid: str
    sender: str
    recipients: str
    subject: str
    date: str
    body: str


@dataclass(frozen=True, slots=True)
class EmailDraft:
    """One outbound message the user approves: recipients, subject, and body shapes.

    ``to``/``cc``/``bcc`` are RFC 5322 address-list header values (comma-separated); ``body``
    is the plain-text part, and ``html``, when non-empty, adds a ``text/html`` alternative so a
    capable client renders the rich body while a plain client keeps the fallback. An empty
    string means "omit this field". Extensible by construction: a further shape (attachments)
    is a new field here, never a change to the ``EmailSender.send`` signature.
    """

    to: str
    subject: str
    body: str
    cc: str = ""
    bcc: str = ""
    html: str = ""
