"""Brain-generated session titles: build the prompt, run the model, clean the reply."""

from collections.abc import Sequence
from datetime import datetime

from cortex_core.conversation import Message, Role
from cortex_core.drain import drain_text
from cortex_core.inference import GenerationBounds
from cortex_core.ports import InferenceBackend
from cortex_core.sessions import TITLE_MAX

# Eight times the four tokens a title costs. Thinking is off for this pass, and the two go
# together: the same prompt capped with thinking on came back empty three times in three,
# because the deliberation before a four-token title is hundreds of tokens.
TITLE_MAX_TOKENS = 32
TITLE_BOUNDS = GenerationBounds(max_tokens=TITLE_MAX_TOKENS, thinking=False, trace_tokens=0)

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
    """One line, wrapping quotes stripped, cut to ``TITLE_MAX``."""
    collapsed = " ".join(raw.split())
    return collapsed.strip("\"'")[:TITLE_MAX]


async def generate_title(backend: InferenceBackend, model: str, messages: Sequence[Message]) -> str:
    """Run one tool-less completion and return its cleaned title."""
    return clean_title(await drain_text(backend, model, messages, bounds=TITLE_BOUNDS))
