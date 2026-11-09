"""The texts a ``forget_memories`` call returns, which the model reads before it replies."""

from cortex_core.errors import MemoryStoreError

FORGET_CHOSEN_LIMIT = 20

NONE_FOUND = (
    "nothing was forgotten: no remembered exchange contains that text, so tell the user that "
    "nothing about it was stored, and do not ask the user for the value"
)
ALREADY_DELETED = (
    "nothing more was forgotten: no remembered exchange contains that text, and an earlier call "
    "in this turn already deleted what the user asked to forget, so tell the user it was deleted "
    "and do not say that it was not stored or could not be found"
)
TOO_MANY = (
    f"nothing was forgotten: more than {FORGET_CHOSEN_LIMIT} remembered exchanges "
    "contain that text, so ask the user for a longer, more exact text"
)
LEFT_OUT_LINE = (
    f"More than {FORGET_CHOSEN_LIMIT} exchanges also hold a value of these, so they stay."
)

FORGET_NOT_KEPT_NOTE = (
    "Nothing in this message is kept in memory, because it asked to forget something, so do not "
    "say that anything in it was noted, saved or remembered. If it also asked you to remember "
    "anything else, say that it was not kept and ask the user to send it again in a message of "
    "its own."
)


def unavailable(err: MemoryStoreError) -> str:
    """The result of a call whose card could not read the store."""
    return f"the memory store is unavailable, so nothing was forgotten: {err}"


def outlasted(removed: int, left: int) -> str:
    """The result of a delete that ``left`` rows written since its card still match."""
    return (
        f"forgot {removed} remembered exchanges, but {left} written since the "
        "card was shown still contain that text, so it is not forgotten"
    )


def unlisted(removed: int) -> str:
    """The result of a delete whose card left out rows holding its value."""
    return (
        f"forgot {removed} remembered exchanges that contain that text, but more exchanges "
        "also hold its value and were not listed, since a card lists at most "
        f"{FORGET_CHOSEN_LIMIT}, so the value is not forgotten"
    )
