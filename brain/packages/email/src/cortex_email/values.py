"""Email domain values: a search hit, a full message, and the outbound draft (no I/O).

``EmailAttachment`` is also the schema a model composes against, which is why pydantic appears in
a module that is otherwise plain dataclasses. Pydantic has been lifting this class's docstring
into the ``send_email`` tool's ``$defs`` entry since attachments landed, so the prose here has
been prompt-facing all along and only the per-field descriptions were missing (ADR-0022 per-field
addendum). Keeping the schema here rather than mirroring the three fields into a second
schema-facing type in ``server.py`` keeps the tool contract from being written twice.

The bounds those descriptions quote live here for the same reason: ``SmtpSender`` raises when a
send exceeds them and the descriptions state the same numbers to the model, so each bound is one
value read twice rather than a number in prose that can drift from the number in the check.
"""

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field

# How many attachments one send may carry. Going over rejects the send rather than truncating it:
# an attachment dropped without a word is a send the user approved and did not get (ADR-0010's
# batch-cap argument).
MAX_ATTACHMENTS = 8
# Characters summed across every attachment's content. The bound comes from the authoring side
# rather than from SMTP: 32K is already half the cortex's 16K-token context, so past it an
# attachment competes with the conversation that wrote it (ADR-0022 attachments addendum).
MAX_ATTACHMENT_CHARS = 32768
# A filename travels in a Content-Disposition header rather than in the payload, so it is bounded
# at a header line's length.
MAX_FILENAME_CHARS = 128

# The three per-field descriptions are written as instruction rather than as documentation,
# following the `capture_screen` target precedent: each sentence removes one guess a model would
# otherwise make, and each names what is rejected because the check runs in the sidecar, after the
# user has already approved the confirmation card.
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
# entries, the other sums their content. Used by the tool signature in `server.py`.
ATTACHMENTS_HELP = (
    "Files to attach, each of them text you have written. At most "
    f"{MAX_ATTACHMENTS} of them, and their content totals at most {MAX_ATTACHMENT_CHARS} "
    "characters across the whole message; past either bound the send is refused outright "
    "rather than shortened, so put long material in the body instead of splitting it here."
)

# The description of the search query, which is where a wrong guess costs a whole dispatch.
# `query` reaches the IMAP server unaltered, so the dialect is raw IMAP SEARCH criteria, while the
# syntax a model reaches for is the `key:value` of every mail client it has seen, and the server
# answers that with a parse error nothing downstream can repair. Every criterion named below was
# run against a real Bridge before it was named (ADR-0022 search-dialect addendum): naming a
# criterion the server rejects costs a dispatch, while omitting one it accepts costs nothing.
SEARCH_QUERY_HELP = (
    "Raw IMAP SEARCH criteria. It is not a mail client's search box: "
    "from:someone@example.com is refused by the server rather than understood, and that "
    'search is written FROM "someone@example.com". Write ALL to match everything. These take '
    'a quoted argument: SUBJECT, FROM, TO, CC, BCC, BODY, TEXT, and HEADER "Name" "value"; '
    "the quotes are what hold a multi-word argument together. These take a bare date written "
    "dd-Mon-yyyy with an English month, never 2026-01-01: SINCE, BEFORE and ON for the day a "
    "message arrived, SENTSINCE, SENTBEFORE and SENTON for the day it says it was sent. These "
    "stand alone: SEEN, UNSEEN, ANSWERED, UNANSWERED, FLAGGED, UNFLAGGED, DRAFT, UNDRAFT, "
    "DELETED, UNDELETED. LARGER and SMALLER take a size in bytes. Criteria written one after "
    "another must all match, OR takes exactly the two criteria after it, NOT negates the one "
    "after it, and parentheses group. So unread mail from this year about either of two things "
    'is: UNSEEN SINCE 01-Jan-2026 OR SUBJECT "invoice" SUBJECT "receipt".'
)
# The same dialect, stated after a rejection. `SEARCH_QUERY_HELP` above is what a model reads
# before it writes a query; this is what it reads once the server has rejected the one it wrote.
# The two live together because this text points at that description by name, so a rename there
# that left this behind would send a model to a field that no longer says anything. It
# deliberately carries nothing of the server's own answer: the wire fragment IMAP sends back is an
# offset into a command the model never saw (`SearchRefusedError` gives the full argument).
SEARCH_REFUSED = (
    "The mail server refused this search as malformed, so nothing was searched and no message "
    "was read. The query is raw IMAP SEARCH criteria, and the query field's own description "
    "spells that dialect out in full, criterion by criterion: write the search again from it "
    "rather than sending this one a second time, which is refused again. The refused query was "
)
FOLDER_HELP = (
    "One folder name spelled exactly as list_folders returned it, such as INBOX or All Mail. A "
    "folder inside another carries its parent and a '/' between them, as in Folders/Jobs. "
    "Nothing is normalised or guessed at, and a name no folder has is an error rather than an "
    "empty result, so read the list rather than inventing a likely name."
)
# The folder name, stated after a failed lookup. `FOLDER_HELP` above is what a model reads before
# it names a folder; this is what it reads once the server has answered that no mailbox has that
# name. Both `search_emails` and `read_email` take a folder, so it names neither searching nor
# reading in particular. It states the correction outright, because here the correction is one
# call away: `list_folders` returns the exact names, so the next attempt can be a lookup rather
# than a second likely-looking guess.
FOLDER_UNKNOWN = (
    "The mail server has no folder by that name, so nothing was searched and no message was "
    "read. Folder names are matched exactly and are never normalised or guessed at: call "
    "list_folders and use a name spelled exactly as that list returns it, rather than trying "
    "another name that looks likely. The folder name that was refused was "
)
# The uid, the other argument `read_email` takes and the one a model cannot look up: a folder
# name comes off `list_folders`, and a uid comes off one line of a `search_emails` answer, where
# it stands in square brackets. The not-found answer is composed from the `None` the port gives
# for a uid no message has and for a string that is not a uid alike, with no command sent for the
# second (ADR-0022 fetch-by-uid addendum), so this says where the number comes from and that the
# answer is final, which is what stops a model trying a likelier number next.
UID_HELP = (
    "The uid of one message: the number search_emails writes in square brackets at the start of "
    "each line, such as 4711 for a line beginning [4711]. Copy it digit for digit from a search "
    "of the same folder, since a uid names a message only within the folder it was listed in, "
    "and a number that is guessed, rounded, or taken from another folder's listing reads a "
    "different message or none. A not-found answer is final for that folder, so search again "
    "rather than trying a nearby number."
)
SEARCH_LIMIT_HELP = (
    "How many matches to return at most. They are the first matches in the folder's own uid "
    "order, which is not the same as the newest: narrow the search with the criteria above "
    "rather than raising this to go looking for a recent message."
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
    """One attached file the assistant authored: a ``text/<subtype>`` part named ``filename``.

    The maintype is not a parameter, exactly as ``From`` is not (ADR-0022 attachments
    addendum): what can be attached is what the assistant can write, so ``subtype`` picks the
    text flavour (``plain``, ``markdown``, ``csv``, ``calendar``, ...) and ``content`` is the
    file itself. Bytes the assistant did not author (a file on disk) are deliberately out of
    reach here: they would put a name on the confirmation card where the payload belongs.
    """

    filename: Annotated[str, Field(description=_FILENAME_HELP)]
    content: Annotated[str, Field(description=_CONTENT_HELP)]
    subtype: Annotated[str, Field(description=_SUBTYPE_HELP)] = "plain"


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
