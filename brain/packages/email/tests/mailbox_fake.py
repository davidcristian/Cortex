"""The fake `Mailbox`: canned messages, no IMAP, and the port's error paths on demand.

One fake serves the reader tests, the server tests and the contract driver, which keeps the part
most likely to drift across three copies in one place: what an implementation of the port does
when it cannot answer the call as asked. It holds a folder list and answers from it the way a
real server does, so a folder no mailbox has needs no knob at all; `refuse`,
`break_folder_opening` and `decline_reads` are the three failures no ordinary call can produce,
and each raises exactly what `ImapMailbox` raises when a real server produces it.

`nodes` is another such case and is not a knob either: the names a real server's LIST answers
with that are only points in the hierarchy. A real server offers them and returns an error when
asked to open one, so this fake holds them without listing them, which is what the port requires
of every implementation.

The canned mail lives in the first folder listed and every other folder holds none, and a fetch
answers by the uid it was given, so a uid no message has is ``None`` in either kind of folder
without a knob, which is the answer the port owes for it.
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
        self._declining = False
        self.searched: list[tuple[str, str, int]] = []

    def refuse(self) -> None:
        """Make every later search raise ``SearchRefusedError``, as a server answering BAD does."""
        self._refusing = True

    def break_folder_opening(self) -> None:
        """Make every later call fail to open its folder for a reason that is not the name.

        This is the contrast case the classification exists for: a folder that is listed, so it
        really is there, and still cannot be examined right now.
        """
        self._unopenable = True

    def decline_reads(self) -> None:
        """Make every later fetch fail for a reason that is not the uid, as a NO to the read does.

        The contrast case for the not-there answer: the server would not read the message, and
        nothing about that says the message is absent.
        """
        self._declining = True

    def _open(self, folder: str) -> None:
        if self._unopenable:
            msg = "the mailbox could not open that folder"
            raise MailboxError(msg)
        if folder not in self._folders:
            raise FolderUnknownError(folder)

    def _holds_mail(self, folder: str) -> bool:
        return folder == self._folders[0]

    def list_folders(self) -> Sequence[str]:
        """Everything the server lists, less the nodes, which is the filtering the port requires."""
        return [name for name in self._listed if name not in self._nodes]

    def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]:
        self._open(folder)
        self.searched.append((folder, query, limit))
        if self._refusing:
            raise SearchRefusedError(query)
        return self._found if self._holds_mail(folder) else ()

    def fetch(self, folder: str, uid: str) -> RawEmail | None:
        self._open(folder)
        if self._declining:
            msg = "the mailbox could not read that message"
            raise MailboxError(msg)
        held = (*self._found, self._one) if self._holds_mail(folder) else ()
        return next((item for item in held if item is not None and item.uid == uid), None)
