"""How much of one loop's tool results reaches the context, and which end of each is kept."""

# 3,640 tokens at the 1.65 characters a token measured on a pasted log: what the fixed prompt, a
# full history window and 2,860 tokens to reply leave of the cortex's 16,384-token context.
RESULT_ROOM_CHARS = 6_000

RESULT_CUT_NOTE = (
    "\n\n(This result is {total:,} characters long and only its first {shown:,} fit in the "
    "context. {advice})"
)
TAIL_CUT_NOTE = (
    "\n\n(This result is {total:,} characters long and only its last {shown:,} fit in the "
    "context, so the first {dropped:,} of its {lines:,} lines are left out. {advice})"
)
NO_ROOM_NOTE = (
    "(This result is {total:,} characters long and none of it fits, because the results already "
    "read in this turn fill the room the context has for results. Answer from what you have "
    "read, or tell the person the rest did not fit.)"
)
SMALLER_PART = (
    "Ask the tool for a smaller part where it offers one, such as the `head` or `tail` lines of "
    "a file, or tell the person the result is too long to read whole."
)
SMALLER_TAIL = (
    "Ask for a `tail` of at most {fit:,} lines to read them whole, or tell the person the rest "
    "is too long to read."
)
ROOM_SHARED = (
    "The results of this turn share one room in the context, so read fewer or smaller parts, "
    "or answer from what you have read."
)


def _head(content: str, limit: int) -> str:
    """The first ``limit`` characters, ending at the last line break in their second half."""
    kept = content[:limit]
    if (end := kept.rfind("\n")) >= limit // 2:
        return kept[:end]
    return kept


def _tail(content: str, limit: int) -> str:
    """The last ``limit`` characters, starting after the first line break in their first half."""
    kept = content[-limit:]
    if (start := kept.find("\n")) < limit // 2:
        return kept[start + 1 :]
    return kept


class ResultRoom:
    """The characters of tool results one loop's context still has room for."""

    def __init__(self, chars: int = RESULT_ROOM_CHARS, *, spent: int = 0) -> None:
        self._chars = chars
        self._left = max(chars - spent, 0)

    @property
    def left(self) -> int:
        """The characters no result has taken yet."""
        return self._left

    def cut(self, content: str, *, share: int = 1, keep_end: bool = False) -> tuple[str, str]:
        """``content`` cut to a ``share``-th of the room left, and the note to put after it."""
        limit = self._left // share
        if len(content) <= limit:
            self._left -= len(content)
            return content, ""
        kept = ((_tail if keep_end else _head)(content, limit)) if limit else ""
        self._left -= len(kept)
        return kept, self._note(content, kept, limit, keep_end=keep_end)

    def whole(self, content: str) -> tuple[str, str]:
        """``content`` uncut, for a note the brain wrote, taken from the room left."""
        self._left = max(self._left - len(content), 0)
        return content, ""

    def _note(self, content: str, kept: str, limit: int, *, keep_end: bool) -> str:
        """What the model is told about a cut result, and what it can ask for instead."""
        if not kept:
            return NO_ROOM_NOTE.format(total=len(content))
        shared = limit < self._chars
        if not keep_end:
            advice = ROOM_SHARED if shared else SMALLER_PART
            return RESULT_CUT_NOTE.format(total=len(content), shown=len(kept), advice=advice)
        lines = content.count("\n") + 1
        fit = kept.count("\n") + int(content[-len(kept) - 1] == "\n")
        advice = ROOM_SHARED if shared else SMALLER_TAIL.format(fit=fit) if fit else SMALLER_PART
        return TAIL_CUT_NOTE.format(
            total=len(content), shown=len(kept), dropped=lines - fit, lines=lines, advice=advice
        )
