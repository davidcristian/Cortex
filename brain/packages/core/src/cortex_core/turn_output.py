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

# What a user is told when their own answer stopped at a token limit rather than at its own end
# (ADR-0005 capped-reply addendum). App-authored like every swap note, so it needs no guardrail
# pass, and phrased without naming which limit: a request's ``max_tokens`` and the server's
# context window are indistinguishable on the wire and equally cut (ADR-0005 decision that a stop
# says a token limit ended it and nothing finer). It leads with the same blank line the swap notes
# do, so it reads as a note under the reply rather than as its last sentence.
REPLY_CAPPED_NOTE = (
    "\n\n(This answer stopped at the machine's length limit, so it is cut off rather than "
    "finished. Ask again, or ask for a shorter answer.)"
)

# What a user is told when the model broke its own tool-call grammar and no token limit explains
# it (ADR-0005 cortex-cut addendum). The sibling of the note above, app-authored and persisted for
# the same reason, and worded for the one thing the reader can act on: nothing ran, so whatever
# they asked for did not happen, and asking again is worth a try because this is the model
# misspeaking rather than a bound they have to work around.
UNREADABLE_CALL_NOTE = (
    "\n\n(I tried to use a tool and wrote the request in a way I could not read back, so nothing "
    "ran and this answer is unfinished. The text above is everything I produced. Ask again.)"
)


def cap_note(stops: StopLedger, parts: list[str]) -> Iterator[TurnEvent]:
    """Say so when one of this turn's completions was cut, appending the note to ``parts``.

    The user-facing half of a bounded reply: a truncated answer that says nothing about being
    truncated is read as a short answer, which is the same misreading ``StopLedger`` exists to
    stop on the delegated path. The delegated path can refuse outright, because a delegated reply
    is read whole by a model; a user is already watching the text arrive, so this appends a
    sentence under the reply instead of refusing.

    It joins ``parts``, so the note is persisted with the reply exactly as ``BRAIN_FAILED_NOTE``
    is and for the same reason: it explains text the user can still see in their history. A turn
    whose backend reported no stop at all emits nothing, an absent report never being read as a
    cap.
    """
    if not stops.capped:
        return
    parts.append(REPLY_CAPPED_NOTE)
    yield TextDelta(text=REPLY_CAPPED_NOTE)


def unreadable_call_note(stops: StopLedger, parts: list[str]) -> Iterator[TurnEvent]:
    """Say so when a tool call would not parse, unless a token limit already explains it.

    The user-facing half of the pairing ``MalformedToolCallError`` exists for (ADR-0005
    tool-call-cut addendum): the error says the unparsable fragment came from the model rather
    than from the transport, and the ledger says whether a completion of this turn stopped at a
    limit. The two facts pick between two different sentences, which is why the ledger is read
    here and not the error alone. Capped, the truthful note is the one every capped reply gets,
    so this yields nothing and ``cap_note`` appends it a moment later; uncapped, no limit explains
    the fragment and this note is the only one written. Exactly one note either way, so a reader
    is never handed two explanations for one cut-off reply.

    An absent report is still not a cap, so a backend that reported no reason at all takes this
    note rather than the other: nothing explains the fragment, and pointing a reader at a token
    budget nothing reported would invent the fact the ledger declines to invent.
    """
    if stops.capped:
        return
    parts.append(UNREADABLE_CALL_NOTE)
    yield TextDelta(text=UNREADABLE_CALL_NOTE)


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
    loop: AsyncGenerator[str | ReasoningDelta | ToolStep | StepOutcome, None],
    channels: OutputChannels,
    parts: list[str],
) -> AsyncGenerator[TurnEvent, None]:
    """Map one tool loop's deltas onto turn events, accumulating the reply into ``parts``.

    A ``ReasoningDelta`` is a reasoning model's live thinking (ADR-0020): ephemeral status,
    never the reply, so it skips ``parts`` and persistence, and a wholly-carried delta emits
    nothing. A ``ToolStep`` is an audited dispatch about to run (ADR-0009 addendum), surfaced as
    the overlay's activity chip with the same non-reply treatment, and the ``StepOutcome`` that
    settles it becomes the ``ToolOutcome`` a consent surface reads (ADR-0029 outcome addendum);
    the pairing the loop guarantees survives this mapping, since neither is ever dropped here.
    Everything else is reply text, passed through the guardrail (ADR-0015) so what is persisted
    is what was shown.

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
    """Record the completed exchange to memory under the turn's taint policy (ADR-0013/0019).

    A turn that read untrusted content is dropped from memory by default, so every stored
    memory comes from an untainted turn; with ``record_tainted_memory`` on (ADR-0019) it is
    recorded instead with the untrusted-provenance marker, so recall fences it as data. One
    policy, applied identically by the cortex phase and by the brain phase after a swap.

    An opaque turn is never recorded, whatever that setting says (ADR-0029). The licence for
    recording a tainted turn rested on the raw untrusted payload never being persisted, and that
    is false for vision: a capture turn's assistant reply is a transcription of the screen. A user
    who switched recording on did not ask for their password manager to be summarized into
    Postgres.

    A write the memory backend rejects is logged and not raised (ADR-0008 unavailable-memory
    addendum), for a different reason than the read's. Raising here saves nothing: the reply has
    already streamed and the assistant message is already in the session store by the time this
    runs, so the embedding or the insert has already failed, and raising would only replace a turn
    the user has read with an error while losing the memory just the same. What is lost is a
    derived index entry rather than the exchange, which stays in the conversation the user can
    scroll to, so this logs at ``error`` rather than breaking the turn. The read's line is a
    ``warning`` instead, marking the difference between a turn that answered thinly and durable
    state that no longer matches the conversation beside it.
    """
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
