"""The email sidecar's own texts, restated brain-side for the own-text overlay."""

from collections.abc import Mapping
from typing import Any

from cortex_core import OwnText

# Each string restates the sidecar's own text word for word, because the overlay re-stamps a
# result trusted only when its bytes match one of these; `crosscheck.py` holds the two equal.
SEARCH_REFUSED = (
    "The mail server refused this search as malformed, so nothing was searched and no message "
    "was read. The query is raw IMAP SEARCH criteria, and the query field's own description "
    "spells that dialect out in full, criterion by criterion: write the search again from it "
    "rather than sending this one a second time, which is refused again. The refused query was "
)
FOLDER_UNKNOWN = (
    "The mail server has no folder by that name, so nothing was searched and no message was "
    "read. Folder names are matched exactly and are never normalised or guessed at: call "
    "list_folders and use a name spelled exactly as that list returns it, rather than trying "
    "another name that looks likely. The folder name that was refused was "
)
NO_MATCHES = "(no matching messages)"
NOT_FOUND = (
    "No message with uid {uid} is in {folder}, so nothing was read. A uid names a message only "
    "within the folder it was listed in, and this folder holds none under that number: a nearby "
    "number and a uid off another folder's listing each name a different message here or none at "
    "all. Search {folder} again with search_emails and copy a uid from one line of that answer, "
    "rather than trying another number that looks likely."
)


def _string(arguments: Mapping[str, Any], name: str) -> str | None:
    """The named argument when the brain sent a string, else ``None`` so nothing renders."""
    value = arguments.get(name)
    return value if isinstance(value, str) else None


def search_refused(arguments: Mapping[str, Any]) -> str | None:
    """`SearchRefusedError`'s text for the query this call sent."""
    query = _string(arguments, "query")
    return None if query is None else f"{SEARCH_REFUSED}{query!r}"


def folder_unknown(arguments: Mapping[str, Any]) -> str | None:
    """`FolderUnknownError`'s text for the folder this call named."""
    folder = _string(arguments, "folder")
    return None if folder is None else f"{FOLDER_UNKNOWN}{folder!r}"


def no_matches(arguments: Mapping[str, Any]) -> str | None:
    """The empty-search answer, the same for every call."""
    del arguments
    return NO_MATCHES


def not_found(arguments: Mapping[str, Any]) -> str | None:
    """The not-found answer for the uid and folder this call named."""
    uid, folder = _string(arguments, "uid"), _string(arguments, "folder")
    return None if uid is None or folder is None else NOT_FOUND.format(uid=uid, folder=folder)


EMAIL_OWN_TEXTS: tuple[OwnText, ...] = (
    OwnText("search_emails", search_refused),
    OwnText("search_emails", folder_unknown),
    OwnText("search_emails", no_matches),
    OwnText("read_email", folder_unknown),
    OwnText("read_email", not_found),
)
