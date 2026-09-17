"""What every `EmailSender` checks on a draft before it sends, and reports afterwards."""

import re
from collections.abc import Sequence

from cortex_email.values import (
    MAX_ATTACHMENT_CHARS,
    MAX_ATTACHMENTS,
    MAX_FILENAME_CHARS,
    EmailAttachment,
    EmailDraft,
)

# A MIME subtype token: no "/", so "text/" stays a prefix the caller cannot escape, no space,
# no ";" that could open a parameter, and nothing a header value must not hold.
_SUBTYPE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,62}$")


def _reject_header_injection(field: str, value: str) -> None:
    """Raise when ``value`` contains a CR or LF that could inject an extra email header."""
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


def refuse_unsendable(draft: EmailDraft) -> None:
    """Raise `ValueError` for a draft no sender may put on the wire, before anything is sent."""
    _reject_header_injection("recipient", draft.to)
    _reject_header_injection("subject", draft.subject)
    _reject_header_injection("cc", draft.cc)
    _reject_header_injection("bcc", draft.bcc)
    _reject_bad_attachments(draft.attachments)


def confirmation(draft: EmailDraft, refused: Sequence[str] = ()) -> str:
    """The one line a send answers: who it went to, its subject, and any address refused."""
    line = f'email sent to {draft.to} (subject: "{draft.subject}")'
    if refused:
        return f"{line}; the server refused {', '.join(refused)}"
    return line
