"""What a turn does with the text it produced: surface it, flush it, remember it."""

import logging
from collections.abc import AsyncGenerator, Iterator

from cortex_core.errors import EmbedderError, MemoryStoreError
from cortex_core.events import TextDelta, ToolActivity, ToolOutcome, TurnEvent
from cortex_core.guardrail import OutputFilter
from cortex_core.loop_events import ReasoningDelta, StepOutcome, ToolStep
from cortex_core.output_channels import ThinkingChannel
from cortex_core.stops import StopLedger
from cortex_core.turn_context import TurnCapabilities
from cortex_core.untrusted import TaintLedger

_logger = logging.getLogger(__name__)

# One turn's two guarded output channels: the reply filter (``None`` when unguarded) and the
# thinking status channel, as ``open_output_channels`` returns them.
type OutputChannels = tuple[OutputFilter | None, ThinkingChannel]

REPLY_CAPPED_NOTE = (
    "\n\n(This answer stopped at the machine's length limit, so it is cut off rather than "
    "finished. Ask again, or ask for a shorter answer.)"
)


def cap_note(stops: StopLedger, parts: list[str]) -> Iterator[TurnEvent]:
    """Say so when one of this turn's completions was cut, appending the note to ``parts``."""
    if not stops.capped:
        return
    parts.append(REPLY_CAPPED_NOTE)
    yield TextDelta(text=REPLY_CAPPED_NOTE)


def render_exchange(user_text: str, assistant_text: str) -> str:
    """Render one completed turn as the memory recorded at turn end (ADR-0008)."""
    return f"User: {user_text}\nAssistant: {assistant_text}"


def flush_channels(channels: OutputChannels, parts: list[str]) -> Iterator[TurnEvent]:
    """Drain what the guarded channels still hold, appending reply text to ``parts``."""
    if (status := channels[1].release()) is not None:
        yield status
    guard = channels[0]
    if guard is not None and (tail := guard.flush()):
        parts.append(tail)
        yield TextDelta(text=tail)


async def stream_turn_events(
    loop: AsyncGenerator[str | ReasoningDelta | ToolStep | StepOutcome, None],
    channels: OutputChannels,
    parts: list[str],
) -> AsyncGenerator[TurnEvent, None]:
    """Map one tool loop's deltas onto turn events, accumulating the reply into ``parts``."""
    try:
        async for delta in loop:
            if isinstance(delta, ReasoningDelta):
                if (status := channels[1].feed(delta.text)) is not None:
                    yield status
                continue
            if isinstance(delta, ToolStep):
                yield ToolActivity(tool_name=delta.tool_name, summary=delta.summary)
                continue
            if isinstance(delta, StepOutcome):
                yield ToolOutcome(tool_name=delta.tool_name, ok=delta.ok)
                continue
            shown = delta if channels[0] is None else channels[0].feed(delta)
            if not shown:
                continue
            parts.append(shown)
            yield TextDelta(text=shown)
    finally:
        await loop.aclose()
    for event in flush_channels(channels, parts):
        yield event


async def record_exchange(
    caps: TurnCapabilities, taint: TaintLedger, *, session_id: str, query: str, reply: str
) -> None:
    """Record the completed exchange to memory under the turn's taint policy (ADR-0013/0019)."""
    if taint.opaque:
        return
    if caps.memory is not None and (not taint.tainted or caps.record_tainted_memory):
        try:
            await caps.memory.record(
                render_exchange(query, reply), session_id=session_id, tainted=taint.tainted
            )
        except (EmbedderError, MemoryStoreError):
            _logger.exception(
                "memory write unavailable; this exchange was not recorded to memory",
                extra={"session_id": session_id},
            )
