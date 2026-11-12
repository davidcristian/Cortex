"""The texts a ``forget_memories`` call returns, which the model reads before it replies."""

from cortex_core.errors import MemoryStoreError
from cortex_core.forget_inside import forgot_within
from cortex_core.memory_values import whole_values

FORGET_CHOSEN_LIMIT = 20

NONE_FOUND = (
    "nothing was forgotten: no remembered exchange contains that exact text, so tell the user "
    "that no remembered exchange contains that exact text, and do not ask the user for the value"
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


def failed_during(removed: int, err: MemoryStoreError) -> str:
    """The result of a delete the store failed during, after ``removed`` rows were deleted."""
    if not removed:
        return f"the memory store failed during the forget: {err}"
    return (
        f"forgot {removed} remembered exchanges, but the memory store then failed, so it is not "
        f"known whether other remembered exchanges still contain that text or its value: {err}"
    )


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


def _flat(text: str) -> str:
    """``text`` in lower case with every run of white space one space."""
    return " ".join(text.lower().split())


def about_deleted(text: str, deleted: tuple[str, ...]) -> bool:
    """Whether ``text`` names what a deleted row or the text that deleted it held."""
    asked, keys = _flat(text), whole_values(text).keys()
    return any(
        asked in _flat(held) or _flat(held) in asked or not keys.isdisjoint(whole_values(held))
        for held in deleted
    )


def forgot(removed: int, holding: int, kept: int, inner: int = 0) -> str:
    """What a delete that left no match forgot; ``holding`` rows hold its numbers, ``kept`` kept,
    ``inner`` hold its text only inside a longer value."""
    if kept:
        return (
            f"forgot {removed} remembered exchanges; {kept} other remembered exchanges hold the "
            "same value, and the user's message names none of their words or asks to keep them, "
            "so they were kept and the value is still remembered"
        )
    if not holding and inner:
        return forgot_within(removed, inner)
    if not holding:
        return (
            f"forgot {removed} remembered exchanges; no remembered exchange contains that text now"
        )
    return (
        f"forgot {removed} remembered exchanges that contain that text, but {holding} other "
        "remembered exchanges still hold a number a deleted one held, so that number is still "
        "remembered; a forget of the number itself would remove them"
    )
