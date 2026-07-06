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


def summarize_session(session_id: str, messages: Sequence[Message]) -> SessionSummary:
    """Derive a chat's summary from its persisted messages (ADR-0021)."""
    return SessionSummary(
        session_id=session_id,
        title=_one_line(messages[0].text, TITLE_MAX),
        preview=_one_line(messages[-1].text, PREVIEW_MAX),
        last_activity=messages[-1].at,
    )
