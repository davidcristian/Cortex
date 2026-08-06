"""Brain-generated session titles: build the prompt, run the model, clean the reply (ADR-0021)."""

from collections.abc import Sequence
from datetime import datetime

from cortex_core.conversation import Message, Role
from cortex_core.drain import drain_text
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
    """
    collapsed = " ".join(raw.split())
    return collapsed.strip("\"'")[:TITLE_MAX]


async def generate_title(backend: InferenceBackend, model: str, messages: Sequence[Message]) -> str:
    """Run one tool-less completion and return its cleaned title."""
    return clean_title(await drain_text(backend, model, messages))
