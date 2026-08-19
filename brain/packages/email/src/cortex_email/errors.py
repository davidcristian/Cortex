"""Typed errors of the `Mailbox` port: the IMAP library's own exceptions never cross it."""

from cortex_email.values import FOLDER_UNKNOWN, SEARCH_REFUSED


class MailboxError(Exception):
    """A `Mailbox` operation failed; the adapter wraps its library's errors into this."""


class SearchRefusedError(MailboxError):
    """The server read the search and refused it: the query is malformed (a `BAD` answer)."""

    def __init__(self, query: str) -> None:
        super().__init__(f"{SEARCH_REFUSED}{query!r}")
        self.query = query


class FolderUnknownError(MailboxError):
    """No mailbox has the folder that was named: it was guessed rather than read off the list."""

    def __init__(self, folder: str) -> None:
        super().__init__(f"{FOLDER_UNKNOWN}{folder!r}")
        self.folder = folder
