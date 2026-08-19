"""The fake `Mailbox`: canned messages, no IMAP, and the port's two corrections on demand."""

from collections.abc import Sequence

from cortex_email import FolderUnknownError, MailboxError, RawEmail, SearchRefusedError


class FakeMailbox:
    """A fake Mailbox returning canned raw messages, recording the search it was asked."""

    def __init__(
        self,
        *,
        folders: Sequence[str] = ("INBOX",),
        found: Sequence[RawEmail] = (),
        one: RawEmail | None = None,
    ) -> None:
        self._folders = folders
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
        return self._folders

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
