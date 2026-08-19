"""Typed errors of the `Mailbox` port: the IMAP library's own exceptions never cross it."""

from cortex_email.values import SEARCH_REFUSED


class MailboxError(Exception):
    """A `Mailbox` operation failed; the adapter wraps its library's errors into this."""


class SearchRefusedError(MailboxError):
    """The server read the search and refused it: the query is malformed (a `BAD` answer)."""

    def __init__(self, query: str) -> None:
        super().__init__(f"{SEARCH_REFUSED}{query!r}")
        self.query = query
