"""ImapMailbox: the read-only Mailbox port over imap-tools (ADR-0009).

Read-only by construction: folders are opened with EXAMINE (``readonly=True`` → the IMAP
server never marks the folder touched) and fetches never set the Seen flag
(``mark_seen=False``); no send/delete/flag/move is exposed. Each call opens a fresh
connection (the Bridge is local) so the server holds no IMAP state. Real network I/O means the
live test hits a real Bridge; CI covers the mapping over a fake imap-tools ``MailBox``.

`list_folders` answers with names that are mailboxes and not with every name the server lists:
a server may list a name that is only a node in the hierarchy, and a caller given one would be
refused in the words that prove a folder missing (ADR-0022 hierarchy-node addendum). The flag
that says so is a claim rather than a fact, and the two servers this repo talks to disagree
about it, so a flagged name is opened once and kept when it opens (ADR-0022 flagged-and-refused
addendum).

No exception of the IMAP stack crosses the port (ADR-0022 refused-search addendum): whatever
imap-tools, imaplib or the socket raises is wrapped as `MailboxError`, and the two failures a
model can act on get their own types, a search the server answered ``BAD`` as
`SearchRefusedError` and a folder no mailbox has as `FolderUnknownError`. A name the server
declines to read as a mailbox name at all is the second of those and not a third: it is a name
`list_folders` cannot have offered, so the correction is the same one call (ADR-0022
refused-name addendum).
"""

import ssl
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from imaplib import IMAP4

from imap_tools import (
    A,
    BaseMailBox,
    ImapToolsError,
    MailBox,
    MailboxFolderSelectError,
    MailBoxStartTls,
)

from cortex_email.config import EmailConfig
from cortex_email.errors import FolderUnknownError, MailboxError, SearchRefusedError
from cortex_email.reader import RawEmail

# What the IMAP stack raises: imap-tools' own errors (a NO where an OK was expected), imaplib's
# protocol errors (a BAD tagged response, a connection lost mid-command), and the socket and TLS
# failures of reaching the Bridge at all, ``ssl.SSLError`` being an ``OSError``.
_LIBRARY_FAILURES = (ImapToolsError, IMAP4.error, OSError)


@contextmanager
def _translated(action: str) -> Generator[None, None, None]:
    """Cross whatever the IMAP stack raises while ``action`` runs into a `MailboxError`.

    The library's text rides along, because for a mailbox that could not answer it is the only
    thing said about *why* and there is no second channel to say it on. The refusal is the
    opposite case and is classified before it reaches here.
    """
    try:
        yield
    except _LIBRARY_FAILURES as err:
        msg = f"the mailbox could not {action}: {err}"
        raise MailboxError(msg) from err


# What a refused SELECT must itself say in words for the folder to be *known* missing. Measured
# against two real servers, which agree on the fact and share no word of how they say it
# (ADR-0022 two-server addendum): a ProtonMail Bridge answers every name no mailbox has with
# ``('NO', [b'no such mailbox'])``, and Dovecot 2.3.21 answers the same names with
# ``('NO', [b"Mailbox doesn't exist: <name>"])``. Neither sends a response code with that one,
# so there the words really are all there is. Anything else a ``NO`` can carry is not proof, and
# what cannot be proved missing is not reported missing: the same Dovecot refuses a mailbox that
# exists and is shut with ``[NOPERM] Permission denied``, which is neither of these.
_FOLDER_MISSING_PHRASES = ("no such mailbox", "mailbox doesn't exist")

# The same conclusion drawn from a machine-readable code instead of from prose, for the servers
# that send one. ``[NONEXISTENT]`` is RFC 5530's own spelling of the phrases above, so a server
# that sends it is saying exactly what they say. ``[CANNOT]`` is a different fact reaching the
# same answer: the server declining to read the name as a mailbox name at all, measured on
# Dovecot 2.3.21 against the empty name as
# ``('NO', [b'[CANNOT] Invalid mailbox name: Name is empty (0.001 + 0.000 secs).'])``. It is
# classified with the missing folder because a name no mailbox could have is a name no mailbox
# has: `list_folders` never offered it, so the one-call correction is the right one, and the
# refusal the fail-safe direction exists to protect, a real mailbox that is merely shut, can
# never be answered ``[CANNOT]``, whose whole meaning in RFC 5530 is that the request can never
# succeed. The Bridge reaches the same answer through its words, refusing the empty name with
# the ordinary ``no such mailbox`` it gives every other wrong name, so the two servers disagree
# about which fact this is and correct the guess identically (ADR-0022 refused-name addendum).
_FOLDER_MISSING_CODES = ("[nonexistent]", "[cannot]")

# One tuple because `_select` asks one question of it: the halves differ in what kind of
# evidence they are, not in what a caller is owed once either of them appears.
_FOLDER_MISSING_ANSWERS = (*_FOLDER_MISSING_PHRASES, *_FOLDER_MISSING_CODES)

# The LIST attributes by which a server says the name it just listed is not a mailbox: RFC 3501's
# ``\Noselect`` for a name that exists only as a point in the hierarchy, and RFC 5258's
# ``\NonExistent`` for the newer spelling that LIST-EXTENDED introduced. Both are measured, and
# they are measured in different listings (ADR-0022 newer-spelling addendum). Dovecot 2.3.21
# sends ``('\\Noselect', '\\HasChildren')`` with its ``Parent`` node, and goes on sending exactly
# that when the LIST asks for return options; the newer word it keeps for a different fact, a
# subscribed name no mailbox has, and sends it only to a LIST that asks for subscriptions:
# ``(\Subscribed \NonExistent) "/" Ghost``, where it arrives instead of ``\Noselect`` rather than
# beside it, and where the name refuses to open in the same words the node does. So this set
# reads a spelling that the one call made here, imap-tools' plain ``LIST "" "*"``, is not the
# listing to carry it: RFC 5258 lets a server send ``\NonExistent`` only alongside a selection
# option, and the Bridge answers an extended LIST with ``BAD`` rather than a flag. It is kept
# because reading a word no server here sends costs one comparison, while not reading it costs a
# name offered to a model that cannot be opened.
#
# Being flagged is a question rather than an answer either way, because the two servers mean
# different things by it (ADR-0022 flagged-and-refused addendum): Dovecot lists that
# ``\Noselect`` parent and then refuses it with ``Mailbox doesn't exist: Parent``, the very words
# that prove a folder missing, while a ProtonMail Bridge flags the two parents of its own
# hierarchy, ``Folders`` and ``Labels``, and opens both. So the flag selects which names get
# asked, and the server's answer decides. The half that reads like one server's quirk is not one:
# RFC 3501 obliges any server to answer an ``LSUB`` of ``%`` with ``\Noselect`` for an
# unsubscribed name that has subscribed children, whatever that name really is, and the probe
# duly flags its ``Feigned`` mailbox there and then opens it (ADR-0022 flagged-name-that-opens
# addendum). Believing a flag is wrong against a standard, not just against a Bridge.
_NOT_A_MAILBOX = frozenset({"\\noselect", "\\nonexistent"})


def _select(box: BaseMailBox, folder: str) -> None:
    """Open ``folder`` read-only (EXAMINE), saying which thing a refusal of it means.

    A ``NO`` to `SELECT` is not by itself a missing folder: the same status covers a mailbox that
    exists and could not be opened, so the name is called wrong only when the server's own answer
    says so. That is the fail-safe direction. Sending a model to `list_folders` over a folder
    that is really there would have it hunt for a name it already had, while the base error it
    gets instead says the mailbox could not answer, which is true either way.

    The answer says so in one of two ways, and both are read: the words two servers were measured
    using, and the RFC 5530 response code a server sends instead of them. The codes are the
    stronger reading where they appear, being a machine-readable claim rather than a sentence
    somebody's server happens to phrase that way, which is why one of them settles a refusal
    whose prose says nothing about a mailbox at all.

    imap-tools renders the refused command's status and data into its exception message, so both
    are read from there rather than from a wire the adapter never sees.
    """
    try:
        box.folder.set(folder, readonly=True)  # pyright: ignore[reportUnknownMemberType]
    except MailboxFolderSelectError as err:
        answer = str(err).lower()
        if any(said in answer for said in _FOLDER_MISSING_ANSWERS):
            raise FolderUnknownError(folder) from err
        raise


def _flagged_unselectable(flags: Sequence[str]) -> bool:
    """Whether the LIST attributes a server sent with a name claim that name is not a mailbox.

    Case-folded because the attribute is an IMAP atom and no server's casing is promised, and
    read off the `FolderInfo` imap-tools already builds, which carries the server's own flags
    beside the name.
    """
    return any(flag.lower() in _NOT_A_MAILBOX for flag in flags)


def _opens(box: BaseMailBox, folder: str) -> bool:
    """Whether this server will really open ``folder``, asked only of a name it flagged.

    The flag is what a server says about a name and this is what it does with it, and a server
    that does both is trusted on the second. Every refusal counts the same, because the promise
    `list_folders` makes is about names that work rather than about names that exist: a flagged
    name refused for any reason is one a caller could not have used.

    Read-only like every other open here (EXAMINE), and paid once per flagged name rather than
    once per listed name, which is what keeps the check off the ordinary mailboxes: a Bridge
    flags two of nineteen names and the probe's Dovecot one of six.
    """
    try:
        box.folder.set(folder, readonly=True)  # pyright: ignore[reportUnknownMemberType]
    except MailboxFolderSelectError:
        return False
    return True


def _search_failure(query: str, err: IMAP4.error) -> MailboxError:
    """Say which of the two things imaplib means by an error raised out of a SEARCH.

    A ``BAD`` tagged response is the server saying it could not parse the command it was sent,
    and imaplib raises a plain ``IMAP4.error`` for it: the query is wrong, so rewriting it is
    the fix and the model reading the result is the one who can. Its ``IMAP4.abort`` subclass is
    the opposite fact, a connection that went away while the command was in flight, where the
    query may have been perfectly good, so it must never come back as a refusal.
    """
    if isinstance(err, IMAP4.abort):
        msg = "the mailbox connection dropped during that search"
        return MailboxError(msg)
    return SearchRefusedError(query)


class ImapMailbox:
    """Read-only Mailbox over imap-tools, connecting per call (stateless server)."""

    def __init__(self, config: EmailConfig) -> None:
        self._config = config

    def _ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(cafile=self._config.ca_cert or None)
        if self._config.tls_insecure:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context

    def _open(self) -> BaseMailBox:
        context = self._ssl_context()
        box: BaseMailBox = (
            MailBoxStartTls(self._config.host, self._config.port, ssl_context=context)
            if self._config.security == "starttls"
            else MailBox(self._config.host, self._config.port, ssl_context=context)
        )
        return box.login(self._config.user, self._config.password.get_secret_value())

    def list_folders(self) -> Sequence[str]:
        """List the names that really are mailboxes, dropping the hierarchy's bare nodes.

        Every name here is one `search` and `fetch` may be given, which is what `FOLDER_HELP`
        promises a model outright. A name the server flagged unselectable is asked before it is
        judged: it survives if it opens and is dropped if it is refused, so the list is neither
        short of a name that works nor padded with one that does not.
        """
        with _translated("list the folders"), self._open() as box:
            listed = box.folder.list()
            return [
                folder.name
                for folder in listed
                if not _flagged_unselectable(folder.flags) or _opens(box, folder.name)
            ]

    def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]:
        """Fetch message headers for the folder's messages matching ``query`` (read-only).

        A query the server refuses as malformed raises `SearchRefusedError` and a folder no
        mailbox has raises `FolderUnknownError`; every other way this can fail raises
        `MailboxError`.
        """
        with _translated("run that search"), self._open() as box:
            _select(box, folder)
            try:
                found = list(box.fetch(query, limit=limit, headers_only=True, mark_seen=False))
            except IMAP4.error as err:
                raise _search_failure(query, err) from err
            return [
                RawEmail(uid=message.uid or "", raw=message.obj.as_bytes()) for message in found
            ]

    def fetch(self, folder: str, uid: str) -> RawEmail | None:
        """Fetch one full message by uid, or None when it does not exist (read-only).

        A folder no mailbox has raises `FolderUnknownError`, the same as a search: the guess is
        the same guess, and it fails before any uid is looked at.
        """
        with _translated("read that message"), self._open() as box:
            _select(box, folder)
            messages = list(box.fetch(A(uid=uid), limit=1, mark_seen=False))
            if not messages:
                return None
            return RawEmail(uid=messages[0].uid or "", raw=messages[0].obj.as_bytes())
