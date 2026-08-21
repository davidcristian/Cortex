"""ImapMailbox: the read-only Mailbox port over imap-tools (ADR-0009)."""

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
    """Cross whatever the IMAP stack raises while ``action`` runs into a `MailboxError`."""
    try:
        yield
    except _LIBRARY_FAILURES as err:
        msg = f"the mailbox could not {action}: {err}"
        raise MailboxError(msg) from err


_FOLDER_MISSING_ANSWERS = ("no such mailbox", "mailbox doesn't exist", "[nonexistent]")


def _select(box: BaseMailBox, folder: str) -> None:
    """Open ``folder`` read-only (EXAMINE), saying which of the two things a refusal means."""
    try:
        box.folder.set(folder, readonly=True)  # pyright: ignore[reportUnknownMemberType]
    except MailboxFolderSelectError as err:
        answer = str(err).lower()
        if any(said in answer for said in _FOLDER_MISSING_ANSWERS):
            raise FolderUnknownError(folder) from err
        raise


def _search_failure(query: str, err: IMAP4.error) -> MailboxError:
    """Say which of the two things imaplib means by an error raised out of a SEARCH."""
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
