"""Per-session values the store holds beside a chat's messages: its summary row, its recap."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from cortex_core.conversation import Message

# The overlay declares the same number in ``sessionState.ts`` for the titles it derives
# before the brain has listed a chat; ``scripts/crosscheck.py`` keeps the two equal.
TITLE_MAX = 48
PREVIEW_MAX = 96


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """One recent chat as the switcher shows it."""

    session_id: str
    title: str
    preview: str
    last_activity: datetime
    pinned: bool = False


# A stored recap is prepended to every windowed turn, so it is bounded to about one turn's
# worth of the 48K character budget it would otherwise eat into.
RECAP_MAX = 2_000


@dataclass(frozen=True, slots=True)
class HistoryRecap:
    """What the turns that fell out of a session's history window said."""

    text: str
    covers: int

    def __post_init__(self) -> None:
        if not self.text.strip():
            msg = "a recap with no text is not worth storing"
            raise ValueError(msg)
        if self.covers < 1:
            msg = "a recap must cover at least one message"
            raise ValueError(msg)


def _one_line(text: str, limit: int) -> str:
    """Collapse runs of whitespace to single spaces and truncate to ``limit`` with an ellipsis."""
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else f"{collapsed[:limit]}…"


def _title(override: str | None, first_text: str) -> str:
    """The switcher title: a stored ``override`` when one is set and non-blank, else the first
    message's text.
    """
    if override is not None:
        collapsed = _one_line(override, TITLE_MAX)
        if collapsed:
            return collapsed
    return _one_line(first_text, TITLE_MAX)


def summarize_ends(
    session_id: str,
    first: Message,
    last: Message,
    *,
    title_override: str | None = None,
    pinned: bool = False,
) -> SessionSummary:
    """Derive a chat's summary from its two end messages."""
    return SessionSummary(
        session_id=session_id,
        title=_title(title_override, first.text),
        preview=_one_line(last.text, PREVIEW_MAX),
        last_activity=last.at,
        pinned=pinned,
    )


def summarize_session(
    session_id: str,
    messages: Sequence[Message],
    *,
    title_override: str | None = None,
    pinned: bool = False,
) -> SessionSummary:
    """Derive a chat's summary from its persisted messages."""
    return summarize_ends(
        session_id, messages[0], messages[-1], title_override=title_override, pinned=pinned
    )


def merge_pinned(summaries: Iterable[SessionSummary]) -> tuple[SessionSummary, ...]:
    """Order a listing: `pinned` chats first, then newest first within each group."""
    by_recency = sorted(summaries, key=lambda summary: summary.last_activity, reverse=True)
    by_recency.sort(key=lambda summary: not summary.pinned)
    return tuple(by_recency)
