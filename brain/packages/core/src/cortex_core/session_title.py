"""Brain-generated session titles: build the prompt, run the model, clean the reply (ADR-0021).

A session's switcher title derives from its first user message by default (``sessions.py``).
When title generation is enabled, a turn engine instead asks the resident model for a short
title from the opening exchange and persists it via ``SessionStore.set_title``, so the switcher
shows what a chat is about rather than its opening words. Generating a title is inference, so it
runs where inference already runs: inside a turn, sequentially, after the reply's own stream has
released the GPU lease (no re-entrant acquire) and never on the read/list path (which would make
listing block on the model). The generated title lives in the store like every other piece of
conversation state, so it survives a model swap (the one hard rule). These are the pure pieces
(the prompt and the cleanup) plus the thin accumulation over the ``InferenceBackend`` port; the
engine owns the decision of when to call them (``TurnCapabilities.generate_titles``).
"""

from collections.abc import Sequence
from datetime import datetime

from cortex_core.conversation import Message, Role
from cortex_core.inference import TextChunk
from cortex_core.ports import InferenceBackend
from cortex_core.sessions import TITLE_MAX

# The opening exchange follows this instruction as the model's only context. Kept short and
# deterministic; the reply is cleaned to one bounded line regardless of how the model answers.
_INSTRUCTION = (
    "Give this conversation a short title of a few words. Reply with only the title, "
    "with no quotation marks and no closing punctuation."
)


def build_title_messages(
    user_text: str, assistant_text: str, *, at: datetime, turn_id: str
) -> list[Message]:
    """The one-message prompt for a title: the instruction, then the session's opening exchange."""
    body = f"{_INSTRUCTION}\n\nUser: {user_text}\nAssistant: {assistant_text}"
    return [Message(role=Role.USER, text=body, at=at, turn_id=turn_id)]


def clean_title(raw: str) -> str:
    """Collapse the model's reply to one line, strip wrapping quotes, and bound it to ``TITLE_MAX``.

    A model may wrap a title in quotes or spread it over lines; this normalizes both. The result
    is bounded here and re-bounded by ``summarize_ends`` at read time, so a stored title can never
    exceed the switcher's width however the model replied. An empty result (the model said nothing
    usable) comes back as ``""`` for the caller to reject rather than persist.
    """
    collapsed = " ".join(raw.split())
    return collapsed.strip("\"'")[:TITLE_MAX]


async def generate_title(backend: InferenceBackend, model: str, messages: Sequence[Message]) -> str:
    """Run one tool-less completion and return its cleaned title.

    Only assistant text (``TextChunk``) contributes; a reasoning model's ``ReasoningChunk`` and
    any ``ToolCall`` are ignored, so the title is the reply and never the private thinking.
    ``InferenceError`` propagates for the caller to absorb: a failed title falls back to the
    first-message derivation and is not worth failing a turn over.
    """
    parts = [
        event.text
        async for event in backend.stream(model, messages)
        if isinstance(event, TextChunk)
    ]
    return clean_title("".join(parts))
