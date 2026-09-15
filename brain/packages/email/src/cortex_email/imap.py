"""ImapMailbox: the read-only Mailbox port over imap-tools."""

import ssl
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from imaplib import IMAP4

from imap_tools import (
    BaseMailBox,
    ImapToolsError,
    MailBox,
    MailBoxStartTls,
    MailboxUidsError,
)

from cortex_email.config import EmailConfig
from cortex_email.errors import MailboxError, SearchRefusedError
from cortex_email.folders import flagged_unselectable, kept_after_opening, select
from cortex_email.reader import RawEmail
from cortex_email.uidfetch import fetch_by_uid

# What the IMAP stack raises: imap-tools' own errors, imaplib's protocol errors, and the socket
# and TLS failures of reaching the Bridge at all, since ssl.SSLError is an OSError.
_LIBRARY_FAILURES = (ImapToolsError, IMAP4.error, OSError)

# The count an EXAMINE reports for a folder holding no mail. A search refused in such a folder
# is answered from it: no message is there, so no criteria match.
_NO_MAIL = 0


@contextmanager
def _translated(action: str) -> Generator[None, None, None]:
    """Wrap whatever the IMAP stack raises while ``action`` runs as a `MailboxError`."""
    try:
        yield
    except _LIBRARY_FAILURES as err:
        msg = f"the mailbox could not {action}: {err}"
        raise MailboxError(msg) from err


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
                if not flagged_unselectable(folder.flags) or kept_after_opening(box, folder.name)
            ]

    def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]:
        """Fetch message headers for the folder's messages matching ``query`` (read-only)."""
        with _translated("run that search"), self._open() as box:
            held = select(box, folder)
            try:
                found = list(box.fetch(query, limit=limit, headers_only=True, mark_seen=False))
            except IMAP4.error as err:
                raise _search_failure(query, err) from err
            except MailboxUidsError:
                if held != _NO_MAIL:
                    raise
                return ()
            return [
                RawEmail(uid=message.uid or "", raw=message.obj.as_bytes()) for message in found
            ]

    def fetch(self, folder: str, uid: str) -> RawEmail | None:
        """Fetch one whole message by uid, or None when no message has that uid (read-only)."""
        with _translated("read that message"), self._open() as box:
            select(box, folder)
            return fetch_by_uid(box, uid)
