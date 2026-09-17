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

type OutputChannels = tuple[OutputFilter | None, ThinkingChannel]

_REDACTED_LOG_MSG = "the output guardrail removed links from this reply"

REPLY_CAPPED_NOTE = (
    "\n\n(This answer stopped at the machine's length limit, so it is cut off rather than "
    "finished. Ask again, or ask for a shorter answer.)"
)

UNREADABLE_CALL_NOTE = (
    "\n\n(I tried to use a tool and wrote the request in a way I could not read back, so nothing "
    "ran and this answer is unfinished. The text above is everything I produced. Ask again.)"
)


def cap_note(stops: StopLedger, parts: list[str]) -> Iterator[TurnEvent]:
    """Say so when one of this turn's completions was cut, appending the note to ``parts``."""
    if not stops.capped:
        return
    parts.append(REPLY_CAPPED_NOTE)
    yield TextDelta(text=REPLY_CAPPED_NOTE)


def unreadable_call_note(stops: StopLedger, parts: list[str]) -> Iterator[TurnEvent]:
    """Say so when a tool call would not parse, unless a token limit already explains it."""
    # Nothing when a limit already explains the fragment: ``cap_note`` appends its own note a
    # moment later, so a reader is never handed two explanations for one cut-off reply.
    if stops.capped:
        return
    parts.append(UNREADABLE_CALL_NOTE)
    yield TextDelta(text=UNREADABLE_CALL_NOTE)


def render_exchange(user_text: str, assistant_text: str) -> str:
    """Render one completed turn as the memory recorded at turn end."""
    return f"User: {user_text}\nAssistant: {assistant_text}"


def flush_channels(channels: OutputChannels, parts: list[str]) -> Iterator[TurnEvent]:
    """Drain what the guarded channels still hold, appending reply text to ``parts``."""
    if (status := channels[1].release()) is not None:
        yield status
    guard = channels[0]
    if guard is None:
        return
    tail = guard.flush()
    removed = guard.redactions()
    if any(removed.values()):
        # The counts are the whole line: a removed URL and its host are the untrusted text
        # itself, so neither is written to the log.
        _logger.info(
            _REDACTED_LOG_MSG,
            extra={
                "policy": guard.policy,
                "collected": removed["collected"],
                "link": removed["link"],
                "lookalike": removed["lookalike"],
            },
        )
    if tail:
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
    """Record the completed exchange to memory under the turn's taint policy."""
    # A turn that read the screen is never recorded, whatever the deployment's taint policy
    # says: its reply is a transcription of whatever was on the screen.
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
