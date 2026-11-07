"""Close a reply that says a fact is kept only for this chat on a turn memory stores."""

import re

KEPT_BEYOND_CHAT_NOTE = (
    "\n\n(This exchange is stored in memory and can be recalled in later chats too, not only in "
    "this one. Ask to forget it if you do not want it kept.)"
)

_KEEP = (
    r"\b(?:keep|keeping|kept|remember|remembering|remembered|note|noted|hold|holding|retain"
    r"|store|stored|save|saved|track)\b"
)
_CHAT = (
    r"\b(?:for|during|in|throughout|within)\s+(?:the\s+(?:rest|course|length)\s+of\s+)?"
    r"(?:this|our|the)\s+(?:current\s+)?(?:conversation|chat|session)\b(?!['\u2019]s\b)"
)
_CHAT_ONLY = re.compile(rf"{_KEEP}.*?{_CHAT}", re.IGNORECASE)
# "Not just for this chat" or "and in later ones" says the opposite of a limit.
_BEYOND = re.compile(
    r"\bnot\s+(?:just|only)\b|\b(?:beyond|future|later|next|other|every)\b", re.IGNORECASE
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def claims_chat_only(reply: str) -> bool:
    """Whether a statement in ``reply`` says something is kept for this chat and no longer."""
    return any(
        not sentence.rstrip().endswith("?")
        and _CHAT_ONLY.search(sentence) is not None
        and _BEYOND.search(sentence) is None
        for sentence in _SENTENCE_END.split(reply)
    )
