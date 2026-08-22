"""Typed errors of the `Mailbox` port: the IMAP library's own exceptions never cross it.

The sidecar cannot import the brain's core (it is deployed on its own, ADR-0009), so the port's
failure channel is declared here rather than in `cortex_core.errors`, in the same shape that
module established: one base for every way the mailbox could not answer, and beneath it the
narrower types for the failures a caller can act on. There are two, one per guess the read tools
invite: the query and the folder.
"""

from cortex_email.values import FOLDER_UNKNOWN, SEARCH_REFUSED


class MailboxError(Exception):
    """A `Mailbox` operation failed; the adapter wraps its library's errors into this.

    Says the mailbox could not answer: the Bridge was not reachable, TLS or the login was
    refused, the folder could not be examined, the connection went away mid-command. All of
    them are conditions of the machine rather than of the request, so none of them is fixed by
    writing a different query, and the honest thing to tell a caller is that email is not
    working right now.
    """


class SearchRefusedError(MailboxError):
    """The server read the search and refused it: the query is malformed (a `BAD` answer).

    The first of the two narrower failures, and the distinction is between **a mailbox that could
    not answer** and **a request the server understood well enough to reject** (ADR-0022
    refused-search addendum). Every other `MailboxError` heals on its own once the Bridge, the
    network, or the credentials are fixed, and nothing about the query changes it. This one heals
    only when the query is rewritten, which is something the model reading the result can do, so
    it carries the `query` it refused and its message points at the dialect the tool's own field
    description spells out.

    It carries no part of the server's answer. What imaplib raises here reads
    ``UID command error: BAD [b'[Error offset=38]: expected space']``, an offset into a wire
    command the model never saw, from a library it is not told about; that stays on the chained
    cause, where an operator reading a traceback finds it.

    It is a subclass rather than a sibling so every existing ``except MailboxError`` keeps
    catching it, the `MemoryDataError` and `ModelNotHostedError` precedent: a caller with no use
    for the distinction goes on failing exactly as it did.
    """

    def __init__(self, query: str) -> None:
        super().__init__(f"{SEARCH_REFUSED}{query!r}")
        self.query = query


class FolderUnknownError(MailboxError):
    """No mailbox has the folder that was named: it was guessed rather than read off the list.

    `SearchRefusedError`'s sibling, on the same line and for the same reason: the mailbox
    answered, and what it said is something the caller can fix rather than something the machine
    has to. Both read tools take a folder, `FOLDER_HELP` tells a model outright that the name is
    spelled exactly as `list_folders` returned it and that an invented one is an error rather than
    an empty result, and this is what that promise costs when it goes unkept. The correction is
    cheaper than the query's: one call, not a rewrite. So it carries the `folder` it was given and
    sends the caller to `list_folders` rather than to a second likely name.

    It carries no part of the server's answer, for `SearchRefusedError`'s reason. What imap-tools
    raises here reads ``Response status "OK" expected, but "NO" received. Data:
    [b'no such mailbox']``, a command status reported to a caller that never sent a command; that
    stays on the chained cause, where an operator reading a traceback finds it.

    Raised only for a refusal whose own answer says so, in the words two servers were measured
    using or in the response code a server sends instead of them. A `NO` to `SELECT` also covers
    a folder that is really there and could not be opened, and a folder that cannot be proved
    missing must not be reported missing (ADR-0022 unknown-folder addendum), so every other
    refusal stays a plain `MailboxError`.

    A name no mailbox *could* have is raised here too, rather than as a third type. One server
    answers the empty name ``[CANNOT] Invalid mailbox name`` and the other answers it
    ``no such mailbox``, so the two disagree about which fact it is; what they cannot disagree
    about is the correction, since `list_folders` never offered such a name and never will
    (ADR-0022 refused-name addendum).
    """

    def __init__(self, folder: str) -> None:
        super().__init__(f"{FOLDER_UNKNOWN}{folder!r}")
        self.folder = folder
