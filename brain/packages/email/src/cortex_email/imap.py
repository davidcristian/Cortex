"""ImapMailbox: the read-only Mailbox port over imap-tools (ADR-0009).

Read-only by construction: folders are opened with EXAMINE (``readonly=True`` → the IMAP
server never marks the folder touched) and fetches never set the Seen flag
(``mark_seen=False``); no send/delete/flag/move is exposed. Each call opens a fresh
connection (the Bridge is local) so the server holds no IMAP state. Real network I/O means the
live test hits a real Bridge; CI covers the mapping over a fake imap-tools ``MailBox``.

No exception of the IMAP stack crosses the port (ADR-0022 refused-search addendum): whatever
imap-tools, imaplib or the socket raises is wrapped as `MailboxError`, and the one failure a
model can act on, a search the server answered ``BAD``, as `SearchRefusedError`.
"""

import ssl
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from imaplib import IMAP4

from imap_tools import A, BaseMailBox, ImapToolsError, MailBox, MailBoxStartTls

from cortex_email.config import EmailConfig
from cortex_email.errors import MailboxError, SearchRefusedError
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

        A query the server refuses as malformed raises `SearchRefusedError`; every other way
        this can fail raises `MailboxError`.
        """
        with _translated("run that search"), self._open() as box:
            box.folder.set(folder, readonly=True)  # pyright: ignore[reportUnknownMemberType]
            try:
                found = list(box.fetch(query, limit=limit, headers_only=True, mark_seen=False))
            except IMAP4.error as err:
                raise _search_failure(query, err) from err
            return [
                RawEmail(uid=message.uid or "", raw=message.obj.as_bytes()) for message in found
            ]

    def fetch(self, folder: str, uid: str) -> RawEmail | None:
        """Fetch one full message by uid, or None when it does not exist (read-only)."""
        with _translated("read that message"), self._open() as box:
            box.folder.set(folder, readonly=True)  # pyright: ignore[reportUnknownMemberType]
            messages = list(box.fetch(A(uid=uid), limit=1, mark_seen=False))
            if not messages:
                return None
            return RawEmail(uid=messages[0].uid or "", raw=messages[0].obj.as_bytes())
