"""The fake `Mailbox`: canned messages, no IMAP, and the port's refusal on demand.

One fake for the reader tests, the server tests and the contract driver, because the thing that
would drift if there were three is the one that matters: what an implementation of the port does
when the server refuses a query. `refuse` is that trigger, and it raises exactly what
`ImapMailbox` raises when a real server answers `BAD`.
"""

from collections.abc import Sequence

from cortex_email import RawEmail, SearchRefusedError


class FakeMailbox:
    """A fake Mailbox returning canned raw messages, recording the search it was asked."""

    def __init__(
        self,
        *,
        folders: Sequence[str] = (),
        found: Sequence[RawEmail] = (),
        one: RawEmail | None = None,
    ) -> None:
        self._folders = folders
        self._found = found
        self._one = one
        self._refusing = False
        self.searched: list[tuple[str, str, int]] = []

    def refuse(self) -> None:
        """Make every later search come back refused, as a server answering BAD would."""
        self._refusing = True

    def list_folders(self) -> Sequence[str]:
        return self._folders

    def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]:
        self.searched.append((folder, query, limit))
        if self._refusing:
            raise SearchRefusedError(query)
        return self._found

    def fetch(self, folder: str, uid: str) -> RawEmail | None:
        del folder, uid
        return self._one
