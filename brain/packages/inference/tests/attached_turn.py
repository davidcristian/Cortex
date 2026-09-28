"""The request a turn with one attached picture sends, as the core builds it and unframed."""

from dataclasses import replace

from system_led import RecordingBackend

from cortex_core import (
    EchoInferenceBackend,
    ImagePart,
    InMemorySessionStore,
    Message,
    SystemClock,
    TurnEngine,
)
from cortex_core.attachments import ATTACHMENT_FRAME

_MODEL = "cortex"


class FrameMissingError(Exception):
    """The turn's messages hold no user message that ends with the attachment frame."""


async def engine_messages(ask: str, picture: ImagePart) -> tuple[Message, ...]:
    """The messages ``TurnEngine`` hands its backend for ``ask`` with ``picture`` attached."""
    backend = RecordingBackend(EchoInferenceBackend())
    engine = TurnEngine(InMemorySessionStore(), backend, SystemClock(), cortex_model=_MODEL)
    async for _ in engine.handle_turn("attached", ask, turn_id="attached-row", images=(picture,)):
        pass
    return backend.sent[0]


def unframed(messages: tuple[Message, ...]) -> tuple[Message, ...]:
    """``messages`` with the frame cut from the one user message holding pictures."""
    framed = [m for m in messages if m.images and m.text.endswith(ATTACHMENT_FRAME)]
    if len(framed) != 1:
        msg = f"expected one framed message with pictures, found {len(framed)}"
        raise FrameMissingError(msg)
    bare = replace(framed[0], text=framed[0].text.removesuffix(ATTACHMENT_FRAME))
    return tuple(bare if m is framed[0] else m for m in messages)
