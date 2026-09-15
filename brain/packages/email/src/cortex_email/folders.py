"""Which names a server really offers as folders, and what its answer to an open says."""

from collections.abc import Sequence
from typing import cast

from imap_tools import BaseMailBox, MailboxFolderSelectError

from cortex_email.errors import FolderUnknownError

# Measured on two servers that agree on the fact and share no wording: a ProtonMail Bridge
# answers `NO no such mailbox` and Dovecot 2.3.21 answers `NO Mailbox doesn't exist: <name>`.
# Neither sends a response code with it, so the words are the only evidence.
_FOLDER_MISSING_PHRASES = ("no such mailbox", "mailbox doesn't exist")

# RFC 5530 codes for the same answer. `[CANNOT]` means the request can never succeed, so the
# name could never be a mailbox name and `list_folders` can never have offered it.
_FOLDER_MISSING_CODES = ("[nonexistent]", "[cannot]")

_FOLDER_MISSING_ANSWERS = (*_FOLDER_MISSING_PHRASES, *_FOLDER_MISSING_CODES)

# The LIST attributes by which a server says a listed name is not a mailbox. They only select
# which names are opened, never whether one is dropped: Dovecot refuses its `\Noselect` parent
# while a Bridge flags the parents of its own hierarchy and opens both.
_NOT_A_MAILBOX = frozenset({"\\noselect", "\\nonexistent"})


def _says_folder_missing(err: MailboxFolderSelectError) -> bool:
    """Whether a refused SELECT's own answer proves that no mailbox has the name it refused."""
    answer = str(err).lower()
    return any(said in answer for said in _FOLDER_MISSING_ANSWERS)


def _message_count(answer: tuple[str, list[bytes | None]]) -> int | None:
    """How many messages an accepted EXAMINE reported, or None when its reply had no count."""
    counted = answer[1][0] if answer[1] else None
    return int(counted) if isinstance(counted, bytes) and counted.isdigit() else None


def _opened(box: BaseMailBox, folder: str) -> tuple[str, list[bytes | None]]:
    """Open ``folder`` read-only (EXAMINE) and return the server's reply."""
    return cast(
        "tuple[str, list[bytes | None]]",
        box.folder.set(folder, readonly=True),  # pyright: ignore[reportUnknownMemberType]
    )


def select(box: BaseMailBox, folder: str) -> int | None:
    """Open ``folder`` read-only (EXAMINE) and return how much mail it holds."""
    try:
        answer = _opened(box, folder)
    except MailboxFolderSelectError as err:
        if _says_folder_missing(err):
            raise FolderUnknownError(folder) from err
        raise
    return _message_count(answer)


def flagged_unselectable(flags: Sequence[str]) -> bool:
    """Whether the LIST attributes sent with a name say that the name is not a mailbox."""
    return any(flag.lower() in _NOT_A_MAILBOX for flag in flags)


def kept_after_opening(box: BaseMailBox, folder: str) -> bool:
    """Whether a flagged name stays on the list, decided by opening it once."""
    try:
        box.folder.set(folder, readonly=True)  # pyright: ignore[reportUnknownMemberType]
    except MailboxFolderSelectError as err:
        return not _says_folder_missing(err)
    return True
