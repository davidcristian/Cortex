"""Email domain values: a search hit, a full message, and the outbound draft (no I/O)."""

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
FOLDER_UNKNOWN = (
    "The mail server has no folder by that name, so nothing was searched and no message was "
    "read. Folder names are matched exactly and are never normalised or guessed at: call "
    "list_folders and use a name spelled exactly as that list returns it, rather than trying "
    "another name that looks likely. The folder name that was refused was "
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
