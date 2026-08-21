"""The fake `Mailbox`: canned messages, no IMAP, and the port's two corrections on demand.

One fake for the reader tests, the server tests and the contract driver, because the thing that
would drift if there were three is the one that matters: what an implementation of the port does
when it cannot answer the call as asked. It holds a folder list and honours it, the way a real
server does, so a folder no mailbox has needs no knob at all; `refuse` and `break_folder_opening`
are the two conditions of the world no method can create, and each raises exactly what
`ImapMailbox` raises when a real server produces it.

`nodes` is the third condition of a real server, and not a knob either: the names its LIST
answers with that are only points in the hierarchy. A real server offers them and refuses to
open them, so this fake holds them without listing them, which is what the port requires of
every implementation.
"""

from collections.abc import Sequence

from cortex_email import FolderUnknownError, MailboxError, RawEmail, SearchRefusedError


class FakeMailbox:
    """A fake Mailbox returning canned raw messages, recording the search it was asked."""

    def __init__(
        self,
        *,
        folders: Sequence[str] = ("INBOX",),
        nodes: Sequence[str] = (),
        found: Sequence[RawEmail] = (),
        one: RawEmail | None = None,
    ) -> None:
        self._folders = folders
        self._listed = (*folders, *nodes)
        self._nodes = nodes
        self._found = found
        self._one = one
        self._refusing = False
        self._unopenable = False
        self.searched: list[tuple[str, str, int]] = []

    def refuse(self) -> None:
        """Make every later search come back refused, as a server answering BAD would."""
        self._refusing = True

    def break_folder_opening(self) -> None:
        """Make every later call fail to open its folder for a reason that is not the name.

        The contrast case the classification exists for: a folder that is listed, so it is really
        there, and still cannot be examined right now.
        """
        self._unopenable = True

    def _open(self, folder: str) -> None:
        if self._unopenable:
            msg = "the mailbox could not open that folder"
            raise MailboxError(msg)
        if folder not in self._folders:
            raise FolderUnknownError(folder)

    def list_folders(self) -> Sequence[str]:
        """Everything the server lists, less the nodes: the filtering the port owes a caller."""
        return [name for name in self._listed if name not in self._nodes]

    def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]:
        self._open(folder)
        self.searched.append((folder, query, limit))
        if self._refusing:
            raise SearchRefusedError(query)
        return self._found

    def fetch(self, folder: str, uid: str) -> RawEmail | None:
        del uid
        self._open(folder)
        return self._one
