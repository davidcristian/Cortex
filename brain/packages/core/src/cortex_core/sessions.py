"""Session summaries for the chat list (ADR-0021): a pure value plus its derivation.

The session-read seam lists recent chats with a derived title and one-line preview.
Deriving those is domain logic, so it lives here in the core and never in an adapter
(the hexagonal invariant). Both the in-memory fake and the Redis ``SessionStore``
build their summaries here, so the rule cannot drift between the fake and the real
adapter, and the shared contract test pins it once. ``summarize_ends`` is the rule
itself (a summary is derived from a chat's two ends and nothing between them, which is
what lets the Redis adapter read only those two records); ``summarize_session`` is the
whole-history form the in-memory fake uses, delegating to it.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from cortex_core.conversation import Message

# Title/preview are collapsed to one line and truncated for the switcher (ADR-0021).
# The overlay's own live-title derivation (for a chat not yet persisted) applies the
# same rule and is kept documented in step, since neither side can see the other's constant.
TITLE_MAX = 48
PREVIEW_MAX = 96


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """One recent chat as the switcher shows it (ADR-0021).

    ``title`` and ``preview`` are already derived (one line, truncated); ``last_activity``
    is tz-aware (the orchestrator maps it to unix-milliseconds at the seam edge). ``pinned``
    is whether the user pinned this chat (ADR-0021 pinning addendum): a pinned chat is unioned
    into a listing regardless of recency and sorts above the recency group (``merge_pinned``).
    A pure value (no I/O, immutable).
    """

    session_id: str
    title: str
    preview: str
    last_activity: datetime
    pinned: bool = False


def _one_line(text: str, limit: int) -> str:
    """Collapse runs of whitespace to single spaces and truncate to ``limit`` with an ellipsis."""
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else f"{collapsed[:limit]}…"


def _title(override: str | None, first_text: str) -> str:
    """The switcher title: a stored ``override`` when one is set and non-blank, else the first
    message's text. Both are collapsed and truncated the same way, so a brain-generated title
    (ADR-0021 titles addendum) can never exceed the switcher width however the model replied,
    and a blank override falls back rather than blanking the row.
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
    """Derive a chat's summary from its two end messages (ADR-0021).

    A summary needs nothing between the ends, and saying so here (rather than leaving it
    implicit in the indexing below) is what lets a store read only those two records
    instead of a whole history. ``first`` and ``last`` are the same message for a
    one-message session. ``title_override``, when a store holds a brain-generated title
    (ADR-0021 titles addendum), replaces the first-message title; the preview and last-activity
    are always derived from the messages. ``pinned`` (ADR-0021 pinning addendum) marks a chat
    the user pinned; a store passes it from its pinned set, and it drives ``merge_pinned``.
    """
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
    """Derive a chat's summary from its persisted messages (ADR-0021).

    ``title`` comes from ``title_override`` when set (a brain-generated title, ADR-0021 titles
    addendum), else the first message's text. The engine appends the user turn first and only
    ``USER``/``ASSISTANT`` messages persist, so index 0 is that first user message; ``preview``
    from the last message's text; ``last_activity`` from the last message's timestamp. ``pinned``
    rides through to the summary (ADR-0021 pinning addendum). Called only with a non-empty history
    (a session exists only once a turn has been appended), so the indexing is total.
    """
    return summarize_ends(
        session_id, messages[0], messages[-1], title_override=title_override, pinned=pinned
    )


def merge_pinned(summaries: Iterable[SessionSummary]) -> tuple[SessionSummary, ...]:
    """Order a listing's candidate summaries: pinned chats first, recency-descending in each group.

    The one shared read-path rule for pinning (ADR-0021 pinning addendum), so the in-memory fake
    and the Redis adapter cannot drift. Each store builds the SAME deduplicated candidate set (the
    recency window unioned with the pinned set) and hands it here; this decides only the order. The
    sort is stable, so sorting by recency first and then by ``not pinned`` yields pinned chats above
    the recency group with each group still newest-active first. Deduplication is the caller's job
    (a chat both pinned and inside the recency window must appear once, so a store unions ids before
    fetching); this function reorders whatever set it is given and never adds or drops a member.
    """
    by_recency = sorted(summaries, key=lambda summary: summary.last_activity, reverse=True)
    by_recency.sort(key=lambda summary: not summary.pinned)
    return tuple(by_recency)
