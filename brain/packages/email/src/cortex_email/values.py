"""Email domain values: a search hit, a full message, and the outbound draft (no I/O)."""

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field

# How many attachments one send may carry. Refused, never truncated: a silently dropped
# attachment is a send the user approved and did not get (ADR-0010's batch-cap argument).
MAX_ATTACHMENTS = 8
# Characters summed across every attachment's content. The bound comes from the authoring
# side, not from SMTP: 32K is already half the cortex's 16K-token context, so past it an
# attachment competes with the conversation that wrote it (ADR-0022 attachments addendum).
MAX_ATTACHMENT_CHARS = 32768
# A filename rides a Content-Disposition header, and a header line is not a payload.
MAX_FILENAME_CHARS = 128

# Written as instruction rather than as documentation, the `capture_screen` target precedent:
# each sentence exists to remove one guess a model would otherwise make, and every refusal is
# named because the check runs in the sidecar, which is *after* the user approved the card.
_FILENAME_HELP = (
    "The name the recipient sees on the attached file. Give it an extension matching the "
    "subtype, such as notes.md for markdown. It rides a header rather than the payload, so "
    "the send is refused, not trimmed, if the name is empty, holds a line break, or runs "
    f"past {MAX_FILENAME_CHARS} characters."
)
_CONTENT_HELP = (
    "The entire text of the file, written out here. This field is the file itself, never a "
    "path to one and never a URL: nothing is read from disk, so the only thing that can be "
    "attached is text you wrote yourself."
)
_SUBTYPE_HELP = (
    "The text flavour, meaning the part after 'text/' in the MIME type: plain, markdown, csv, "
    "calendar, and so on. Write that bare word only, never 'text/markdown' and never anything "
    "holding a slash, a space or a semicolon, or the send is refused. Leave it out for plain."
)
# The two bounds that belong to the array rather than to any one attachment: one counts the
# entries, the other sums their content. Spent by the tool signature in `server.py`.
ATTACHMENTS_HELP = (
    "Files to attach, each of them text you have written. At most "
    f"{MAX_ATTACHMENTS} of them, and their content totals at most {MAX_ATTACHMENT_CHARS} "
    "characters across the whole message; past either bound the send is refused outright "
    "rather than shortened, so put long material in the body instead of splitting it here."
)


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
    """One attached file the assistant authored: a ``text/<subtype>`` part named ``filename``."""

    filename: Annotated[str, Field(description=_FILENAME_HELP)]
    content: Annotated[str, Field(description=_CONTENT_HELP)]
    subtype: Annotated[str, Field(description=_SUBTYPE_HELP)] = "plain"


@dataclass(frozen=True, slots=True)
class EmailDraft:
    """One outbound message the user approves: recipients, subject, body, and attachments."""

    to: str
    subject: str
    body: str
    cc: str = ""
    bcc: str = ""
    html: str = ""
    attachments: tuple[EmailAttachment, ...] = ()
