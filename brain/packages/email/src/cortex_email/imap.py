"""ImapMailbox: the read-only Mailbox port over imap-tools (ADR-0009).

Read-only by construction: folders are opened with EXAMINE (``readonly=True`` → the IMAP
server never marks the folder touched) and fetches never set the Seen flag
(``mark_seen=False``); no send/delete/flag/move is exposed. Each call opens a fresh
connection (the Bridge is local) so the server holds no IMAP state. Real network I/O means the
live test hits a real Bridge; CI covers the mapping over a fake imap-tools ``MailBox``.
"""

import ssl
from collections.abc import Sequence

from imap_tools import A, BaseMailBox, MailBox, MailBoxStartTls

from cortex_email.config import EmailConfig
from cortex_email.reader import RawEmail


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
        with self._open() as box:
            return [folder.name for folder in box.folder.list()]

    def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]:
        """Fetch message headers for the folder's messages matching ``query`` (read-only)."""
        with self._open() as box:
            box.folder.set(folder, readonly=True)  # pyright: ignore[reportUnknownMemberType]
            messages = box.fetch(query, limit=limit, headers_only=True, mark_seen=False)
            return [
                RawEmail(uid=message.uid or "", raw=message.obj.as_bytes()) for message in messages
            ]

    def fetch(self, folder: str, uid: str) -> RawEmail | None:
        """Fetch one full message by uid, or None when it does not exist (read-only)."""
        with self._open() as box:
            box.folder.set(folder, readonly=True)  # pyright: ignore[reportUnknownMemberType]
            messages = list(box.fetch(A(uid=uid), limit=1, mark_seen=False))
            if not messages:
                return None
            return RawEmail(uid=messages[0].uid or "", raw=messages[0].obj.as_bytes())
