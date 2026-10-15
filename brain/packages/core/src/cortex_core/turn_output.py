"""What a turn does with the text it produced: surface it, flush it, remember it."""

import asyncio
import logging
from collections.abc import AsyncGenerator, Iterator, Sequence

from cortex_core.conversation import ToolRun
from cortex_core.errors import EmbedderError, MemoryStoreError
from cortex_core.events import TextDelta, ToolActivity, ToolOutcome, TurnEvent
from cortex_core.guardrail import OutputFilter
from cortex_core.loop_events import ReasoningDelta, StepOutcome, ToolStep
from cortex_core.memory_forget import FORGET_UNTRUSTED_TOOL_NAME
from cortex_core.output_channels import ThinkingChannel
from cortex_core.repeat_watch import REPEATED_LINE_NOTE, RepeatWatch
from cortex_core.schedule_claim import UNSCHEDULED_CLAIM_NOTE, unscheduled_claim
from cortex_core.stops import StopLedger
from cortex_core.tool_loop import MAX_TOOL_STEPS
from cortex_core.tool_replay import runs_line
from cortex_core.turn_context import TurnCapabilities
from cortex_core.untrusted import TaintLedger

_logger = logging.getLogger(__name__)

type OutputChannels = tuple[OutputFilter | None, ThinkingChannel]

_REDACTED_LOG_MSG = "the output guardrail removed links from this reply"

REPLY_CAPPED_NOTE = (
    "\n\n(This answer stopped at the machine's length limit, so it is cut off rather than "
    "finished. Ask again, or ask for a shorter answer.)"
)

ROUNDS_SPENT_NOTE = (
    "\n\n(I stopped after {rounds} rounds of tool calls, the most one answer may use, and did not "
    "reply to what the last calls returned. {runs} Ask again to continue.)"
)
NO_TOOL_RAN = "No tool ran."

UNREADABLE_CALL_NOTE = (
    "\n\n(I tried to use a tool and wrote the request in a way I could not read back, so nothing "
    "ran and this answer is unfinished. The text above is everything I produced. Ask again.)"
)
UNREADABLE_CALL_NO_TEXT_NOTE = (
    "(I tried to use a tool and wrote the request in a way I could not read back, so nothing "
    "ran and I wrote no answer. Ask again.)"
)

CONTEXT_OVERFLOW_NOTE = (
    "\n\n(This conversation and what this turn has read so far are longer than my context, so I "
    "stopped here. The text above is everything I produced. Start a new conversation, or send a "
    "shorter message.)"
)
CONTEXT_OVERFLOW_NO_TEXT_NOTE = (
    "(This conversation and what this turn has read so far are longer than my context, so I "
    "stopped before writing an answer. Start a new conversation, or send a shorter message.)"
)

MESSAGE_OVERFLOW_NOTE = (
    "\n\n(Your message is longer than my context, so I could not read it. Send a shorter part "
    "of it, such as the lines your question is about.)"
)


def _has_text(parts: Sequence[str]) -> bool:
    """Whether the reply so far holds anything but white space."""
    return any(part.strip() for part in parts)


def place_note(parts: Sequence[str], note: str) -> str:
    """``note`` set one blank line below the reply in ``parts``, or with no line break first."""
    reply = "".join(parts)
    breaks = len(reply) - len(reply.rstrip("\n"))
    lead = "\n" * max(0, 2 - breaks) if _has_text(parts) else ""
    return lead + note.lstrip("\n")


def append_note(parts: list[str], note: str) -> Iterator[TurnEvent]:
    """Append ``note`` to ``parts`` where ``place_note`` sets it."""
    placed = place_note(parts, note)
    parts.append(placed)
    yield TextDelta(text=placed)


def cap_note(stops: StopLedger, parts: list[str]) -> Iterator[TurnEvent]:
    """Say so when one of this turn's completions was cut, appending the note to ``parts``."""
    if not stops.capped:
        return
    yield from append_note(parts, REPLY_CAPPED_NOTE)


def rounds_note(
    stops: StopLedger, runs: Sequence[ToolRun], parts: list[str]
) -> Iterator[TurnEvent]:
    """Say so when the tool loop ran out of rounds, naming each tool the turn ran."""
    if not stops.out_of_rounds:
        return
    listed = f"{runs_line(runs)}." if runs else NO_TOOL_RAN
    yield from append_note(parts, ROUNDS_SPENT_NOTE.format(rounds=MAX_TOOL_STEPS, runs=listed))


def repeat_note(stops: StopLedger, parts: list[str]) -> Iterator[TurnEvent]:
    """Say so when the turn ended its reply because the reply repeated one line."""
    if not stops.repeated:
        return
    yield from append_note(parts, REPEATED_LINE_NOTE)


def limit_notes(
    stops: StopLedger,
    runs: Sequence[ToolRun],
    parts: list[str],
    *,
    earlier: Sequence[ToolRun] = (),
    said: Sequence[str] = (),
) -> Iterator[TurnEvent]:
    """The notes a turn that ended without an error closes with, in the order it shows them.

    ``earlier`` (runs of an earlier phase) and ``said`` (the person's messages) are for the claim.
    """
    claimed = unscheduled_claim((*earlier, *runs), "".join(parts), said)
    yield from cap_note(stops, parts)
    yield from rounds_note(stops, runs, parts)
    yield from repeat_note(stops, parts)
    if claimed:
        yield from append_note(parts, UNSCHEDULED_CLAIM_NOTE)


def unreadable_call_note(stops: StopLedger, parts: list[str]) -> Iterator[TurnEvent]:
    """Say so when a tool call would not parse, unless a token limit already explains it."""
    # Nothing when a limit already explains the fragment: ``cap_note`` appends its own note a
    # moment later, so a reader is never handed two explanations for one cut-off reply.
    if stops.capped:
        return
    yield from append_note(
        parts, UNREADABLE_CALL_NOTE if _has_text(parts) else UNREADABLE_CALL_NO_TEXT_NOTE
    )


def overflow_note(parts: list[str], *, alone: bool) -> Iterator[TurnEvent]:
    """Say so when the engine refused the prompt as longer than the context.

    ``alone`` says the newest message did not fit even with every older turn dropped.
    """
    if alone:
        note = MESSAGE_OVERFLOW_NOTE
    else:
        note = CONTEXT_OVERFLOW_NOTE if _has_text(parts) else CONTEXT_OVERFLOW_NO_TEXT_NOTE
    yield from append_note(parts, note)


def render_exchange(user_text: str, assistant_text: str, runs: Sequence[ToolRun] = ()) -> str:
    """Render one completed turn, with the tool calls it ran, as the memory recorded at turn end."""
    if not runs:
        return f"User: {user_text}\nAssistant: {assistant_text}"
    return f"User: {user_text}\n{runs_line(runs)}\nAssistant: {assistant_text}"


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
    stops: StopLedger,
    query: str,
) -> AsyncGenerator[TurnEvent, None]:
    """Map one tool loop's deltas onto turn events, accumulating the reply into ``parts``.

    A reply that repeats one block of lines ``query`` does not hold is ended there, and ``stops``
    records it for its note.
    """
    watch = RepeatWatch(query)
    try:
        async for delta in loop:
            if isinstance(delta, ReasoningDelta):
                if (status := channels[1].feed(delta.text)) is not None:
                    yield status
                continue
            if isinstance(delta, ToolStep):
                channels[1].next_round()
                # Text on each side of a tool call is not one stretch of reply, so a line each
                # round opens with is not a repeat; the round limit bounds those lines.
                watch = RepeatWatch(query)
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
            if watch.feed(shown):
                stops.observe_repeat()
                break
    finally:
        await loop.aclose()
    for event in flush_channels(channels, parts):
        yield event


async def record_exchange(
    caps: TurnCapabilities,
    taint: TaintLedger,
    *,
    session_id: str,
    query: str,
    reply: str,
    runs: Sequence[ToolRun],
) -> None:
    """Record the completed exchange to memory under the turn's taint policy."""
    # A turn that holds a picture (a screen capture, an MCP image or an attachment) is never
    # recorded, whatever the deployment's taint policy says: its reply may transcribe it.
    if taint.opaque:
        return
    # Recording a tainted turn that forgot the untrusted memories would store a new one.
    if taint.tainted and any(run.ok and run.name == FORGET_UNTRUSTED_TOOL_NAME for run in runs):
        return
    if caps.memory is not None and (not taint.tainted or caps.record_tainted_memory):
        try:
            async with asyncio.timeout(caps.memory_write_timeout_s):
                await caps.memory.record(
                    render_exchange(query, reply, runs),
                    session_id=session_id,
                    tainted=taint.tainted,
                )
        except (EmbedderError, MemoryStoreError, TimeoutError):
            _logger.exception(
                "memory write unavailable; this exchange was not recorded to memory",
                extra={"session_id": session_id},
            )
