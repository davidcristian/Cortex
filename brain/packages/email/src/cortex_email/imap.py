"""ImapMailbox: the read-only Mailbox port over imap-tools (ADR-0009).

Read-only by construction: folders are opened with EXAMINE (``readonly=True`` → the IMAP
server never marks the folder touched) and fetches never set the Seen flag
(``mark_seen=False``); no send/delete/flag/move is exposed. Each call opens a fresh
connection (the Bridge is local) so the server holds no IMAP state. Real network I/O means the
live test hits a real Bridge; CI covers the mapping over a fake imap-tools ``MailBox``.

No exception of the IMAP stack crosses the port (ADR-0022 refused-search addendum): whatever
imap-tools, imaplib or the socket raises is wrapped as `MailboxError`, and the two failures a
model can act on get their own types, a search the server answered ``BAD`` as
`SearchRefusedError` and a folder no mailbox has as `FolderUnknownError`.
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


# What a refused SELECT must itself say for the folder to be *known* missing. Measured against
# two real servers, which agree on the fact and share no word of how they say it (ADR-0022
# two-server addendum): a ProtonMail Bridge answers every name no mailbox has with
# ``('NO', [b'no such mailbox'])``, and Dovecot 2.3.21 answers the same names with
# ``('NO', [b"Mailbox doesn't exist: <name>"])``. Neither sends a response code with it, so
# there is no machine-readable signal to read instead of the words; the RFC 5530 code is listed
# beside them because it is the standard's own spelling of the same fact, so a server that does
# send it is saying exactly this. Anything else a ``NO`` can carry is not proof, and what cannot
# be proved missing is not reported missing: the same Dovecot refuses a mailbox that exists and
# is shut with ``[NOPERM] Permission denied``, which is none of these.
_FOLDER_MISSING_ANSWERS = ("no such mailbox", "mailbox doesn't exist", "[nonexistent]")


def _select(box: BaseMailBox, folder: str) -> None:
    """Open ``folder`` read-only (EXAMINE), saying which of the two things a refusal means.

    A ``NO`` to `SELECT` is not by itself a missing folder: the same status covers a mailbox that
    exists and could not be opened, so the name is called wrong only when the server's own answer
    says no mailbox has it. That is the fail-safe direction. Sending a model to `list_folders`
    over a folder that is really there would have it hunt for a name it already had, while the
    base error it gets instead says the mailbox could not answer, which is true either way.

    imap-tools renders the refused command's status and data into its exception message, so the
    server's words are read from there rather than from a wire the adapter never sees.
    """
    try:
        box.folder.set(folder, readonly=True)  # pyright: ignore[reportUnknownMemberType]
    except MailboxFolderSelectError as err:
        answer = str(err).lower()
        if any(said in answer for said in _FOLDER_MISSING_ANSWERS):
            raise FolderUnknownError(folder) from err
        raise


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
        """List the mailbox folder names."""
        with _translated("list the folders"), self._open() as box:
            return [folder.name for folder in box.folder.list()]

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
