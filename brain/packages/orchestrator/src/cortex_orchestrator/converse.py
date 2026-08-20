"""The Converse use-case: ClientEvents in, turn-engine runs, ServerEvents out.

This module owns the contract below and the entry point the servicer calls; one stream's
machinery (the pump, the credit-bounded output queue, turn scheduling, the domain-event to
wire-event mapping, and teardown) lives in `converse_stream.py`, which this re-exports from
so every existing `from cortex_orchestrator.converse import ...` keeps resolving.

Nothing is held beyond the in-flight turn and its not-yet-started queue: every turn is a
stateless pass of `cortex_core.TurnEngine` over the session store (the one hard rule), so
killing the process mid-stream loses at most the partial reply of the turn in flight and
never the conversation.

Stream contract (proto/body.proto `BrainService.Converse`):

- `UserTurn` runs one core turn; domain events map onto `ServerEvent`: one
  `TextDelta` per streamed reply delta, a `StatusUpdate` per reasoning delta
  (ADR-0020, `state="thinking"`), a `ToolActivity` per audited tool dispatch
  (ADR-0009 addendum) and the `ToolOutcome` settling it once that dispatch resolves
  (ADR-0029 outcome addendum), then `TurnComplete{turn_id}`, carrying the id this
  stream minted for the turn before it started it. `UserTurn.images`
  are still ignored: vision arrived as a model-initiated capture (ADR-0029), and the
  user-attached image path is a recorded deferral rather than a coming slice.
  A turn that spawns subagents also surfaces their progress on the same stream,
  through this stream's `SeamProgressSink`: a `StatusUpdate{state="delegating"}`
  for the batch's scale and a `ToolActivity` per subagent tool step (ADR-0010).
  Those ride while the turn is suspended inside the spawn dispatch (its generator
  cannot yield), best-effort and credit-balanced, so a stalled consumer drops them.
  A delegated step carries no outcome: the outcome exists for a consent surface over
  a cortex-only built-in, so pairing holds for the turn's own dispatches and a
  subagent's step stays activity-only.
- Turns run one at a time, but dispatch never blocks on the running turn: a
  `UserTurn` arriving mid-turn is queued and starts when the in-flight turn
  finishes, and later client events (a `Cancel` above all) are still acted on
  immediately.
- `Cancel` stops the in-flight turn (if any) AND drops every queued-but-not-started
  turn. The user asked to stop, so nothing not-yet-started runs; a dropped turn's
  user message is never persisted. A `Cancel` with nothing running is a no-op. The
  stream stays open for the next `UserTurn` either way. Core semantics apply to the
  stopped turn: its user message stays persisted, the partial reply is dropped.
- A gated tool call mid-turn emits `ConfirmRequest` and suspends until the matching
  `ConfirmResponse` arrives (ADR-0022, `confirm.py`); timeout, half-close, `Cancel`,
  and stream teardown all resolve it as a denial. Fail-closed in every direction.
  The two denials the client cannot see coming (timeout, half-close) also emit a
  `ConfirmResolved`, so the overlay closes a card that can no longer be answered.
- Engine/store failures become exactly one terminal `SeamError{code, message}`
  event, after which the stream ends cleanly. No exception ever escapes to gRPC.
"""

from collections.abc import AsyncGenerator, AsyncIterator

from cortex_core import new_turn_id
from cortex_orchestrator.converse_stream import (
    DEFAULT_CONFIRM_TIMEOUT_S,
    DEFAULT_MAX_BUFFERED_EVENTS,
    ERROR_CODE_INFERENCE_FAILED,
    ERROR_CODE_INTERNAL,
    ERROR_CODE_SESSION_STORE_UNAVAILABLE,
    ConverseStream,
    EngineFactory,
    TurnIdFactory,
)
from cortex_seam import ClientEvent, ServerEvent

__all__ = [
    "DEFAULT_CONFIRM_TIMEOUT_S",
    "DEFAULT_MAX_BUFFERED_EVENTS",
    "ERROR_CODE_INFERENCE_FAILED",
    "ERROR_CODE_INTERNAL",
    "ERROR_CODE_SESSION_STORE_UNAVAILABLE",
    "EngineFactory",
    "TurnIdFactory",
    "converse",
]


def converse(
    make_engine: EngineFactory,
    client_events: AsyncIterator[ClientEvent],
    *,
    max_buffered_events: int = DEFAULT_MAX_BUFFERED_EVENTS,
    confirm_timeout_s: float = DEFAULT_CONFIRM_TIMEOUT_S,
    turn_id_factory: TurnIdFactory = new_turn_id,
) -> AsyncGenerator[ServerEvent, None]:
    """The Converse conversation loop as a server-event stream (see module docstring).

    `make_engine` receives this stream's confirmer and progress sink and returns its engine
    (ADR-0022/0010, and a bare engine wraps as `lambda _confirmer, _progress: engine`, leaving
    gated calls fail-closed and delegated work unsurfaced).
    `max_buffered_events` bounds how many events may sit unread before generation
    stalls (must be positive); `confirm_timeout_s` bounds how long a gated call awaits
    the user before denial; `turn_id_factory` names each turn this stream runs, which is
    what its failures are reported under (ADR-0038 named-turn addendum) and what the client
    is told on `TurnComplete`. Close the returned generator to tear everything down
    (in-flight turn included). That is what the servicer does when the RPC ends or
    the client disconnects.
    """
    stream = ConverseStream(
        make_engine,
        max_buffered_events=max_buffered_events,
        confirm_timeout_s=confirm_timeout_s,
        turn_id_factory=turn_id_factory,
    )
    return stream.events(client_events)
