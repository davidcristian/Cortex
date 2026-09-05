"""One message by uid: what a uid is, the FETCH that reads it, and how absence is read off it.

`ImapMailbox.fetch` sends its ``UID FETCH`` through here rather than through imap-tools' own
``fetch``, which searches for the uid before fetching it. RFC 3501 defines what a ``UID FETCH``
answers for a uid no message has, an ``OK`` carrying no data, and both servers this repo talks
to answer exactly that, in a folder holding mail and in one holding none. The search has no such
definition, and a ProtonMail Bridge answers a ``UID`` search key in a folder holding no mail with
``NO no such message`` for every uid, which reached the model as a mailbox that could not answer
(ADR-0022 fetch-by-uid addendum).

A ``NO`` to the FETCH is not read at all. It is a read the server declined for a reason of its
own, and a message that cannot be shown absent is not reported absent, so it stays a
`MailboxError` carrying the server's text: the folder classification's fail-safe direction,
applied to the message.
"""

import re

from imap_tools import BaseMailBox, MailboxFetchError, MailMessage

from cortex_email.reader import RawEmail

# RFC 3501's ``uniqueid``: a decimal number with no leading zero, in the unsigned 32-bit range. A
# uid reaches the server exactly as the caller spelled it, so the spelling is checked first, and
# anything else is answered as a message that is not there without a command being sent: no
# message has a uid that is not a uid. Both servers were measured on the shapes a model writes
# (ADR-0022 fetch-by-uid addendum). The Bridge reads ``01`` as 1, and ``2,1`` and ``1:*`` as sets
# that fetch messages the caller never named; it rejects ``abc`` and ``0`` as syntax errors and
# answers ``4294967296`` with no data, where Dovecot 2.3.21 rejects that one as an invalid set.
# Asking would answer each shape differently on each server; not asking answers them all alike.
_UNIQUEID = re.compile(r"[1-9][0-9]*")
_UNIQUEID_CEILING = 4294967295

# The FETCH imap-tools composes for a whole, unseen read (``BaseMailBox.fetch`` with
# ``mark_seen=False`` and ``headers_only=False``), spelled here because this module sends it
# itself: ``BODY.PEEK[]`` is the whole message without the Seen flag being set, and ``UID`` is
# where `MailMessage` reads the uid back from.
_WHOLE_MESSAGE_UNSEEN = "(BODY.PEEK[] UID FLAGS RFC822.SIZE)"


def is_uid(uid: str) -> bool:
    """Whether ``uid`` is spelled as RFC 3501 spells a uid, so that a message could have it."""
    return _UNIQUEID.fullmatch(uid) is not None and int(uid) <= _UNIQUEID_CEILING


def fetch_by_uid(box: BaseMailBox, uid: str) -> RawEmail | None:
    """Read the whole message ``uid`` from the folder ``box`` has open, or None when none has it.

    Absence is the FETCH's own ``OK`` with no data, which RFC 3501 defines as a uid no message
    has. Any other status is raised as imap-tools raises it out of its own fetch, so a declined
    read reaches `ImapMailbox` in the words every other refusal does.
    """
    if not is_uid(uid):
        return None
    answer = box.client.uid("FETCH", uid, _WHOLE_MESSAGE_UNSEEN)
    status, data = answer
    if status != "OK":
        raise MailboxFetchError(answer, "OK")
    if not any(data):  # imaplib hands back ``[None]`` when the server sent no FETCH line at all
        return None
    message = MailMessage(data)
    return RawEmail(uid=message.uid or "", raw=message.obj.as_bytes())
