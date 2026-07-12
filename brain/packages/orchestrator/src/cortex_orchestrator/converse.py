"""The Converse use-case: ClientEvents in, turn-engine runs, ServerEvents out.

This module holds NOTHING beyond the in-flight turn and its not-yet-started queue:
every turn is a stateless pass of `cortex_core.TurnEngine` over the session store
(the one hard rule), so killing the process mid-stream loses at most the partial
reply of the turn in flight and never the conversation.

Stream contract (proto/body.proto `BrainService.Converse`):

- `UserTurn` runs one core turn; domain events map onto `ServerEvent`: one
  `TextDelta` per streamed reply delta, a `StatusUpdate` per reasoning delta
  (ADR-0020, `state="thinking"`), a `ToolActivity` per audited tool dispatch
  (ADR-0009 addendum), then `TurnComplete{turn_id}`. `UserTurn.images`
  are ignored in this slice. Multimodal input arrives with vision (Slice 10).
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
- Engine/store failures become exactly one terminal `SeamError{code, message}`
  event, after which the stream ends cleanly. No exception ever escapes to gRPC.
"""

import asyncio
import logging
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator, Callable

from cortex_core import (
    Confirmer,
    InferenceError,
    SessionStoreError,
    TurnEngine,
    TurnEvent,
)
from cortex_core import StatusUpdate as DomainStatusUpdate
from cortex_core import TextDelta as DomainTextDelta
from cortex_core import ToolActivity as DomainToolActivity
from cortex_orchestrator.confirm import SeamConfirmer
from cortex_seam import ClientEvent, SeamError, ServerEvent, TurnComplete
from cortex_seam import StatusUpdate as WireStatusUpdate
from cortex_seam import TextDelta as WireTextDelta
from cortex_seam import ToolActivity as WireToolActivity

# How the servicer builds one stream's engine (ADR-0022): a closure over the shared
# adapters that wires THIS stream's confirmer into the dispatcher. Engines are stateless
# functions over the store, so per-stream construction costs nothing.
EngineFactory = Callable[[Confirmer], TurnEngine]

# SeamError.code values are part of the seam contract (the overlay switches on these).
ERROR_CODE_SESSION_STORE_UNAVAILABLE = "session_store_unavailable"
ERROR_CODE_INFERENCE_FAILED = "inference_failed"
ERROR_CODE_INTERNAL = "internal"

# Default bound on buffered-but-unread ServerEvents per stream: generous for a live
# consumer (a whole short reply fits), small enough that a stalled one caps the brain's
# memory at a few tens of KB of deltas. Env override: CORTEX_SEAM_CONVERSE_BUFFER.
DEFAULT_MAX_BUFFERED_EVENTS = 256

# Default wait for the user's answer to a ConfirmRequest before the gated call is denied
# (fail-closed, ADR-0022). Env override: CORTEX_SEAM_CONFIRM_TIMEOUT_S.
DEFAULT_CONFIRM_TIMEOUT_S = 120.0

_logger = logging.getLogger(__name__)


def _to_server_event(event: TurnEvent) -> ServerEvent:
    """Map one core domain event onto the wire (the core never imports wire code)."""
    if isinstance(event, DomainTextDelta):
        return ServerEvent(text_delta=WireTextDelta(text=event.text))
    if isinstance(event, DomainStatusUpdate):
        return ServerEvent(status=WireStatusUpdate(state=event.state, detail=event.detail))
    if isinstance(event, DomainToolActivity):
        return ServerEvent(
            tool_activity=WireToolActivity(tool_name=event.tool_name, summary=event.summary)
        )
    return ServerEvent(turn_complete=TurnComplete(turn_id=event.turn_id))


class _ConverseStream:
    """One Converse stream: a pump task dispatches client events into turn tasks.

    The pump and the consumer are decoupled by an output queue so a `Cancel` can be
    acted on while a turn is still generating; `None` on the queue ends the stream.
    The queue is bounded by a credit semaphore (`max_buffered_events`, the Slice-3
    backpressure deferral, landed 2026-07-06): the turn's data path acquires one
    credit per event and the consumer returns it on dequeue, so a consumer that stops
    reading stalls generation at the bound instead of buffering an unbounded reply.
    Control events (the terminal `SeamError` and the `None` sentinel) bypass the
    credits (`put_nowait` on the still-unbounded queue): failure reporting and stream
    teardown must never block behind a full buffer, whatever the consumer does.

    Turn scheduling: at most one turn task runs; `UserTurn`s arriving mid-turn wait
    in `_pending` and the finishing turn's own cleanup starts the next one, so the
    pump never blocks on a running turn and stays free to act on a `Cancel`.

    Cancellation discipline: child tasks are awaited via `asyncio.wait`, which
    propagates the WAITER'S cancellation and never the child's outcome. A bare
    `await task` under `suppress(CancelledError)` must not come back: when stream
    teardown raced a client `Cancel`, it swallowed the pump's own cancellation, the
    pump resumed reading the client iterator, and `aclose()` hung the RPC handler.
    """

    def __init__(
        self,
        make_engine: EngineFactory,
        *,
        max_buffered_events: int = DEFAULT_MAX_BUFFERED_EVENTS,
        confirm_timeout_s: float = DEFAULT_CONFIRM_TIMEOUT_S,
    ) -> None:
        if max_buffered_events < 1:
            msg = "max_buffered_events must be at least 1"
            raise ValueError(msg)
        self._out: asyncio.Queue[ServerEvent | None] = asyncio.Queue()
        self._credits = asyncio.Semaphore(max_buffered_events)
        # This stream's confirmer rides the control path via put_nowait (see the class
        # docstring on credits); the factory wires it into the stream's own engine.
        self._confirmer = SeamConfirmer(self._out.put_nowait, timeout_s=confirm_timeout_s)
        self._engine = make_engine(self._confirmer)
        self._pending: deque[tuple[str, str]] = deque()
        self._turn: asyncio.Task[None] | None = None
        self._failed = False

    async def events(
        self, client_events: AsyncIterator[ClientEvent]
    ) -> AsyncGenerator[ServerEvent, None]:
        """Yield ServerEvents until input ends, a SeamError fires, or the consumer closes."""
        pump = asyncio.create_task(self._pump(client_events))
        try:
            while (event := await self._out.get()) is not None:
                # Return the data credit on dequeue. Control events never acquired one, so
                # this over-credits: by one terminally for a SeamError (harmless, as no
                # further turn starts), and by one per ConfirmRequest on a live stream
                # (accepted because at most one is outstanding at a time, so the buffer bound
                # drifts by single digits over a session, never unbounded; ADR-0022).
                self._credits.release()
                yield event
        finally:
            # Runs on normal end, RPC cancellation, and client disconnect alike:
            # neither the pump, the in-flight turn, nor anything queued may outlive
            # this stream (see the class docstring for why asyncio.wait, not await).
            pump.cancel()
            await asyncio.wait([pump])
            await self._cancel_turn()

    async def _pump(self, client_events: AsyncIterator[ClientEvent]) -> None:
        """Dispatch client events; when input ends, let the queued turns finish."""
        try:
            async for event in client_events:
                kind = event.WhichOneof("event")
                if kind == "user_turn":
                    self._enqueue_turn(event.session_id, event.user_turn.text)
                elif kind == "cancel":
                    await self._cancel_turn()
                elif kind == "confirm_response":
                    self._confirmer.resolve(
                        event.confirm_response.confirm_id,
                        approved=event.confirm_response.approved,
                    )
                else:
                    _logger.debug("ignoring client event without a known payload")
            # Input ended (half-close): no answer can ever arrive, so anything awaiting
            # confirmation is denied NOW. A draining turn must not hang out the timeout.
            # This is the ONLY place we close (decline): on teardown/failure the in-flight
            # turn is *cancelled* by events()'s finally instead, so a client disconnect
            # cancels a pending confirm rather than auditing a spurious "user declined".
            self._confirmer.close()
            await self._drain_turns()
        except Exception as err:  # deliberately broad: nothing may escape the seam unhandled
            _logger.exception("Converse client stream failed")
            self._fail(ERROR_CODE_INTERNAL, str(err))
        finally:
            self._out.put_nowait(None)

    def _enqueue_turn(self, session_id: str, text: str) -> None:
        """Queue one turn; it starts immediately when nothing is running."""
        self._pending.append((session_id, text))
        self._start_next_turn()

    def _start_next_turn(self) -> None:
        """Start the oldest queued turn unless one runs already or the stream failed."""
        if self._turn is not None or self._failed or not self._pending:
            return
        session_id, text = self._pending.popleft()
        self._turn = asyncio.create_task(self._turn_task(session_id, text))

    async def _drain_turns(self) -> None:
        """Client input ended: wait until the in-flight turn and the queue are done."""
        while (turn := self._turn) is not None:
            # The finishing turn's cleanup chains the next queued one before the
            # task completes, so each wait observes either None or a fresh task.
            await asyncio.wait([turn])

    async def _cancel_turn(self) -> None:
        """Stop the in-flight turn and drop the queued ones; the stream stays open."""
        self._pending.clear()  # the user asked to stop: nothing not-yet-started runs
        turn = self._turn
        if turn is None:
            return
        turn.cancel()
        await asyncio.wait([turn])

    async def _turn_task(self, session_id: str, text: str) -> None:
        """One turn task: typed failures become SeamError; completion chains the queue."""
        try:
            await self._run_turn(session_id, text)
        except SessionStoreError as err:
            _logger.exception("session store failed mid-turn")
            self._fail(ERROR_CODE_SESSION_STORE_UNAVAILABLE, str(err))
        except InferenceError as err:
            _logger.exception("inference failed mid-turn")
            self._fail(ERROR_CODE_INFERENCE_FAILED, str(err))
        except Exception as err:  # deliberately broad: nothing may escape the seam unhandled
            _logger.exception("unexpected failure handling a turn")
            self._fail(ERROR_CODE_INTERNAL, str(err))
        finally:
            # Synchronous, so it runs even under cancellation and completes before
            # the task reads as done: whoever awaits the task sees exact bookkeeping,
            # and the next queued turn starts (after a Cancel the queue is already
            # empty; after a failure _start_next_turn refuses).
            self._turn = None
            self._start_next_turn()

    async def _run_turn(self, session_id: str, text: str) -> None:
        """One stateless turn over the store, streamed onto the output queue."""
        events = self._engine.handle_turn(session_id, text)
        try:
            async for event in events:
                # Backpressure: block here (suspending generation) until the consumer
                # frees a credit; cancellation while blocked tears down cleanly below.
                await self._credits.acquire()
                self._out.put_nowait(_to_server_event(event))
        finally:
            # Cancellation lands while suspended inside handle_turn; closing the
            # engine's generator keeps its cleanup guarantees (partial reply dropped).
            await events.aclose()

    def _fail(self, code: str, message: str) -> None:
        """Emit the terminal SeamError and mark the stream dead (no further turns)."""
        self._failed = True
        self._out.put_nowait(ServerEvent(error=SeamError(code=code, message=message)))
        self._out.put_nowait(None)


def converse(
    make_engine: EngineFactory,
    client_events: AsyncIterator[ClientEvent],
    *,
    max_buffered_events: int = DEFAULT_MAX_BUFFERED_EVENTS,
    confirm_timeout_s: float = DEFAULT_CONFIRM_TIMEOUT_S,
) -> AsyncGenerator[ServerEvent, None]:
    """The Converse conversation loop as a server-event stream (see module docstring).

    `make_engine` receives this stream's confirmer and returns its engine (ADR-0022, and
    a bare engine wraps as `lambda _confirmer: engine`, leaving gated calls fail-closed).
    `max_buffered_events` bounds how many events may sit unread before generation
    stalls (must be positive); `confirm_timeout_s` bounds how long a gated call awaits
    the user before denial. Close the returned generator to tear everything down
    (in-flight turn included). That is what the servicer does when the RPC ends or
    the client disconnects.
    """
    stream = _ConverseStream(
        make_engine,
        max_buffered_events=max_buffered_events,
        confirm_timeout_s=confirm_timeout_s,
    )
    return stream.events(client_events)
