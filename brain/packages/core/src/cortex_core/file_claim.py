"""Close a reply that lists folders on a file question no tool output answered."""

import re
from collections.abc import Sequence

from cortex_core.file_request import asks_files
from cortex_core.untrusted import TaintLedger

UNREAD_FOLDERS_NOTE = (
    "\n\n(No file was read in this turn, so the folders and files named above were not checked "
    "and may not exist. Ask again to have them listed.)"
)

# A fence, or a span holding a space, is a command: its paths say nothing of what the cortex reads.
_CODE = re.compile(r"```.*?(?:```|\Z)|`[^`\n]*\s[^`\n]*`", re.DOTALL)
# Written with no negative form, since "I can't read /srv" says the opposite.
_REACH = re.compile(
    r"\bI\s+(?:also\s+)?(?:(?:can|could)\s+(?:also\s+)?(?:read|access|see|reach|list|view|open)\b"
    r"|have\s+(?:access|permission)\b)"
    r"|\b(?:I\s+am|I['\u2019]m|you\s+are|you['\u2019]re)\s+(?:allowed|permitted|able)\s+to\b",
    re.IGNORECASE,
)
_HEDGED = re.compile(r"\b(?:if|once|when|unless|for\s+example|such\s+as|e\.g\.)", re.IGNORECASE)
_FOLDERS = re.compile(
    r"\b(?:director(?:y|ies)|folders?|paths?|locations?|files?)\b"
    r"(?!\s+(?:types?|formats?|extensions?))",
    re.IGNORECASE,
)
_PATH = re.compile(r"(?<![\w/.~:-])(?:~|[A-Za-z]:)?[/\\]\w[\w.-]*(?:[/\\][\w.-]*)*")
_ITEM = re.compile(r"^\s*(?:[-*+\u2022]|\d+[.)])\s+(.*\S)")
_WRAPPING = " `*_\"'.,"
# The mark of a numbered list item ends no sentence.
_SENTENCE_END = re.compile(r"(?<=[.!?])(?<!\b\d\.)(?<!\b\d\d\.)\s+|\n+")


def _untyped(name: str, query: str) -> bool:
    """Whether ``name`` is text the person's ``query`` does not hold."""
    return name.strip(_WRAPPING).casefold() not in query.casefold()


def _entries(lines: Sequence[str]) -> list[str]:
    """The list items or lone paths ``lines`` open with, each without its list mark."""
    found: list[str] = []
    for line in lines:
        item = _ITEM.match(line)
        if item is None and _PATH.fullmatch(line.strip(_WRAPPING)) is None:
            break
        found.append(line if item is None else item.group(1))
    return found


def _names_one(sentence: str, following: Sequence[str], query: str) -> bool:
    """Whether ``sentence``, or the list under it, names a path or folder ``query`` does not."""
    if any(_untyped(path, query) for path in _PATH.findall(sentence)):
        return True
    heading, colon, rest = sentence.partition(":")
    if not colon:
        return False
    listed = [rest] if rest.strip() else _entries(following)
    folders = _FOLDERS.search(heading) is not None
    return any(
        (folders or _PATH.search(entry) is not None) and _untyped(entry, query) for entry in listed
    )


def _says_it_reaches(sentence: str) -> bool:
    """Whether ``sentence`` is a statement, with no condition, that a folder can be reached."""
    return (
        not sentence.rstrip().endswith("?")
        and _REACH.search(sentence) is not None
        and _HEDGED.search(sentence) is None
    )


def claims_folders(reply: str, *, query: str) -> bool:
    """Whether a statement in ``reply`` says it reaches a folder ``query`` does not name."""
    lines = [line for line in _SENTENCE_END.split(_CODE.sub("", reply)) if line.strip()]
    return any(
        _says_it_reaches(line) and _names_one(line, lines[index + 1 :], query)
        for index, line in enumerate(lines)
    )


def unread_folders_claim(taint: TaintLedger, query: str, reply: str) -> bool:
    """Whether ``reply`` lists folders on a turn that asks about files and read no tool output."""
    return not taint.tainted and asks_files(query) and claims_folders(reply, query=query)
