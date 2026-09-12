"""ImapMailbox: the read-only Mailbox port over imap-tools (ADR-0009)."""

import ssl
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from imaplib import IMAP4

from imap_tools import (
    BaseMailBox,
    ImapToolsError,
    MailBox,
    MailboxFolderSelectError,
    MailBoxStartTls,
)

from cortex_email.config import EmailConfig
from cortex_email.errors import FolderUnknownError, MailboxError, SearchRefusedError
from cortex_email.reader import RawEmail
from cortex_email.uidfetch import fetch_by_uid

# What the IMAP stack raises: imap-tools' own errors (a NO where an OK was expected), imaplib's
# protocol errors (a BAD tagged response, a connection lost mid-command), and the socket and TLS
# failures of reaching the Bridge at all, ``ssl.SSLError`` being an ``OSError``.
_LIBRARY_FAILURES = (ImapToolsError, IMAP4.error, OSError)


@contextmanager
def _translated(action: str) -> Generator[None, None, None]:
    """Wrap whatever the IMAP stack raises while ``action`` runs as a `MailboxError`."""
    try:
        yield
    except _LIBRARY_FAILURES as err:
        msg = f"the mailbox could not {action}: {err}"
        raise MailboxError(msg) from err


_FOLDER_MISSING_PHRASES = ("no such mailbox", "mailbox doesn't exist")

_FOLDER_MISSING_CODES = ("[nonexistent]", "[cannot]")

# One tuple because `_select` asks one question of it: the halves differ in what kind of evidence
# they are, but a caller gets the same answer once either of them appears.
_FOLDER_MISSING_ANSWERS = (*_FOLDER_MISSING_PHRASES, *_FOLDER_MISSING_CODES)

_NOT_A_MAILBOX = frozenset({"\\noselect", "\\nonexistent"})


def _says_folder_missing(err: MailboxFolderSelectError) -> bool:
    """Whether a refused SELECT's own answer proves that no mailbox has the name it refused."""
    answer = str(err).lower()
    return any(said in answer for said in _FOLDER_MISSING_ANSWERS)


def _select(box: BaseMailBox, folder: str) -> None:
    """Open ``folder`` read-only (EXAMINE), classifying which failure a rejection of it is."""
    try:
        box.folder.set(folder, readonly=True)  # pyright: ignore[reportUnknownMemberType]
    except MailboxFolderSelectError as err:
        if _says_folder_missing(err):
            raise FolderUnknownError(folder) from err
        raise


def _flagged_unselectable(flags: Sequence[str]) -> bool:
    """Whether the LIST attributes a server sent with a name claim that name is not a mailbox."""
    return any(flag.lower() in _NOT_A_MAILBOX for flag in flags)


def _kept_after_opening(box: BaseMailBox, folder: str) -> bool:
    """Whether a flagged name stays on the list, asked by opening it once."""
    try:
        box.folder.set(folder, readonly=True)  # pyright: ignore[reportUnknownMemberType]
    except MailboxFolderSelectError as err:
        return not _says_folder_missing(err)
    return True


def _search_failure(query: str, err: IMAP4.error) -> MailboxError:
    """Classify an error raised out of a SEARCH into the two things imaplib means by one."""
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
        """List the names that really are mailboxes, dropping the hierarchy's bare nodes."""
        with _translated("list the folders"), self._open() as box:
            listed = box.folder.list()
            return [
                folder.name
                for folder in listed
                if not _flagged_unselectable(folder.flags) or _kept_after_opening(box, folder.name)
            ]

    def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]:
        """Fetch message headers for the folder's messages matching ``query`` (read-only)."""
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
        """Fetch one whole message by uid, or None when no message has that uid (read-only)."""
        with _translated("read that message"), self._open() as box:
            _select(box, folder)
            return fetch_by_uid(box, uid)
