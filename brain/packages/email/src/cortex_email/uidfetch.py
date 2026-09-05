"""One message by uid: what a uid is, the FETCH that reads it, and how absence is read off it."""

import re

from imap_tools import BaseMailBox, MailboxFetchError, MailMessage

from cortex_email.reader import RawEmail

# RFC 3501's uniqueid: a decimal number with no leading zero, in the unsigned 32-bit range.
# A string that is not one is reported as a message that is not there and no command is sent,
# because the two servers read a set, a range or an out-of-range number differently.
_UNIQUEID = re.compile(r"[1-9][0-9]*")
_UNIQUEID_CEILING = 4294967295

# The FETCH imap-tools composes for a whole, unseen read. BODY.PEEK[] leaves the Seen flag
# alone, and UID is where `MailMessage` reads the uid back from.
_WHOLE_MESSAGE_UNSEEN = "(BODY.PEEK[] UID FLAGS RFC822.SIZE)"


def is_uid(uid: str) -> bool:
    """Whether ``uid`` is written the way RFC 3501 defines one, so a message could have it."""
    return _UNIQUEID.fullmatch(uid) is not None and int(uid) <= _UNIQUEID_CEILING


def fetch_by_uid(box: BaseMailBox, uid: str) -> RawEmail | None:
    """Read the whole message ``uid`` from the folder ``box`` has open, or None when none has it."""
    if not is_uid(uid):
        return None
    answer = box.client.uid("FETCH", uid, _WHOLE_MESSAGE_UNSEEN)
    status, data = answer
    if status != "OK":
        raise MailboxFetchError(answer, "OK")
    # imaplib hands back [None] when the server sent no FETCH line at all.
    if not any(data):
        return None
    message = MailMessage(data)
    return RawEmail(uid=message.uid or "", raw=message.obj.as_bytes())
