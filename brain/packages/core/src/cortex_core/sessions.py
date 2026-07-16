"""Session summaries for the chat list (ADR-0021): a pure value plus its derivation."""

from collections.abc import Sequence
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
    """One recent chat as the switcher shows it (ADR-0021)."""

    session_id: str
    title: str
    preview: str
    last_activity: datetime


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
    session_id: str, first: Message, last: Message, *, title_override: str | None = None
) -> SessionSummary:
    """Derive a chat's summary from its two end messages (ADR-0021)."""
    return SessionSummary(
        session_id=session_id,
        title=_title(title_override, first.text),
        preview=_one_line(last.text, PREVIEW_MAX),
        last_activity=last.at,
    )


def summarize_session(
    session_id: str, messages: Sequence[Message], *, title_override: str | None = None
) -> SessionSummary:
    """Derive a chat's summary from its persisted messages (ADR-0021)."""
    return summarize_ends(session_id, messages[0], messages[-1], title_override=title_override)
