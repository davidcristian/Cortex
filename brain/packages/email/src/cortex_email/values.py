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
class EmailAttachment:
    """One attached file the assistant authored: a ``text/<subtype>`` part named ``filename``.

    The maintype is not a parameter, exactly as ``From`` is not (ADR-0022 attachments
    addendum): what can be attached is what the assistant can write, so ``subtype`` picks the
    text flavour (``plain``, ``markdown``, ``csv``, ``calendar``, ...) and ``content`` is the
    file itself. Bytes the assistant did not author (a file on disk) are deliberately out of
    reach here: they would put a name on the confirmation card where the payload belongs.
    """

    filename: str
    content: str
    subtype: str = "plain"


@dataclass(frozen=True, slots=True)
class EmailDraft:
    """One outbound message the user approves: recipients, subject, body, and attachments.

    ``to``/``cc``/``bcc`` are RFC 5322 address-list header values (comma-separated); ``body``
    is the plain-text part, and ``html``, when non-empty, adds a ``text/html`` alternative so a
    capable client renders the rich body while a plain client keeps the fallback. An empty
    string means "omit this field". ``attachments`` composes one ``text/*`` part each, which
    makes the message ``multipart/mixed`` around whatever the body shapes built. Extensible by
    construction: a further shape is a new field here, never a change to the
    ``EmailSender.send`` signature.
    """

    to: str
    subject: str
    body: str
    cc: str = ""
    bcc: str = ""
    html: str = ""
    attachments: tuple[EmailAttachment, ...] = ()
