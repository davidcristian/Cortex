"""What a turn does with the text it produced: surface it, flush it, remember it.

The output half of a turn, shared by the two callers that run the bounded infer/tool loop for a
user: ``TurnEngine`` (the cortex phase) and ``BrainPhase`` (the deep model's phase after a swap,
ADR-0030 decision 4). Both map the same loop's deltas onto the same domain events, both drain
the same guarded channels at the end, and both record the same exchange to memory under the
same taint policy, so it is written once here rather than twice with a chance to diverge.

The loop itself lives in ``tool_loop.py`` (what runs), the context assembly in
``turn_context.py`` (what the model sees); this module owns what comes back out. Pure: the only
I/O is through the ports its callers hand in.
"""

from collections.abc import AsyncGenerator, Iterator

from cortex_core.events import TextDelta, ToolActivity, TurnEvent
from cortex_core.guardrail import OutputFilter
from cortex_core.loop_events import ReasoningDelta, ToolStep
from cortex_core.output_channels import ThinkingChannel
from cortex_core.turn_context import TurnCapabilities
from cortex_core.untrusted import TaintLedger

# One turn's two guarded output channels: the reply filter (``None`` when unguarded) and the
# thinking status channel, as ``open_output_channels`` returns them.
type OutputChannels = tuple[OutputFilter | None, ThinkingChannel]


def render_exchange(user_text: str, assistant_text: str) -> str:
    """Render one completed turn as the memory recorded at turn end (ADR-0008)."""
    return f"User: {user_text}\nAssistant: {assistant_text}"


def flush_channels(channels: OutputChannels, parts: list[str]) -> Iterator[TurnEvent]:
    """Drain what the guarded channels still hold, appending reply text to ``parts``.

    The thinking trace's one flush (its carry deliberately survives tool steps, so it is
    released exactly once at end of stream) and then the reply filter's, whose tail IS reply
    text and so joins the persisted message. Called at the end of a completed stream, and by a
    caller that has to persist a partial reply after a failure mid-stream.
    """
    if (status := channels[1].release()) is not None:
        yield status
    guard = channels[0]
    if guard is not None and (tail := guard.flush()):
        parts.append(tail)
        yield TextDelta(text=tail)


async def stream_turn_events(
    loop: AsyncGenerator[str | ReasoningDelta | ToolStep, None],
    channels: OutputChannels,
    parts: list[str],
) -> AsyncGenerator[TurnEvent, None]:
    """Map one tool loop's deltas onto turn events, accumulating the reply into ``parts``.

    A ``ReasoningDelta`` is a reasoning model's live thinking (ADR-0020): ephemeral status,
    never the reply, so it skips ``parts`` and persistence, and a wholly-carried delta emits
    nothing. A ``ToolStep`` is an audited dispatch about to run (ADR-0009 addendum), surfaced as
    the overlay's activity chip with the same non-reply treatment. Everything else is reply
    text, passed through the guardrail (ADR-0015) so what is persisted is what was shown.

    The loop is closed deterministically in a ``finally``: a consumer that closes this
    generator mid-turn must not leave the loop (and the backend stream it holds) half
    suspended. On a clean end the channels are flushed; on an exception they are not, and the
    caller decides whether a partial reply is worth keeping.
    """
    try:
        async for delta in loop:
            if isinstance(delta, ReasoningDelta):
                if (status := channels[1].feed(delta.text)) is not None:
                    yield status
                continue
            if isinstance(delta, ToolStep):
                yield ToolActivity(tool_name=delta.tool_name, summary=delta.summary)
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
    """Record the completed exchange to memory under the turn's taint policy (ADR-0013/0019).

    A turn that read untrusted content is dropped from memory by default, so every stored
    memory comes from an untainted turn; with ``record_tainted_memory`` on (ADR-0019) it is
    recorded instead with the untrusted-provenance marker, so recall fences it as data. One
    policy, applied identically by the cortex phase and by the brain phase after a swap.
    """
    if caps.memory is not None and (not taint.tainted or caps.record_tainted_memory):
        await caps.memory.record(
            render_exchange(query, reply), session_id=session_id, tainted=taint.tainted
        )
