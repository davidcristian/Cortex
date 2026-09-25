"""One Converse stream's machinery: pump, bounded output queue, turns, heartbeat, teardown."""

import asyncio
import logging
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator, Callable

from cortex_core import (
    AsyncioSleeper,
    AttachmentError,
    Confirmer,
    ImagePart,
    InferenceError,
    ProgressSink,
    SessionStoreError,
    Sleeper,
    TurnEvent,
    TurnRunner,
    new_turn_id,
)
from cortex_core import StatusUpdate as DomainStatusUpdate
from cortex_core import TextDelta as DomainTextDelta
from cortex_core import ToolActivity as DomainToolActivity
from cortex_core import ToolOutcome as DomainToolOutcome
from cortex_orchestrator.attached import ERROR_CODE_ATTACHMENT_REFUSED, read_attachments
from cortex_orchestrator.confirm import RpcConfirmer
from cortex_orchestrator.progress import RpcProgressSink
from cortex_seam import ClientEvent, Heartbeat, SeamError, ServerEvent, TurnComplete
from cortex_seam import StatusUpdate as WireStatusUpdate
from cortex_seam import TextDelta as WireTextDelta
from cortex_seam import ToolActivity as WireToolActivity
from cortex_seam import ToolOutcome as WireToolOutcome

EngineFactory = Callable[[Confirmer, ProgressSink], TurnRunner]
QueuedTurn = tuple[str, str, tuple[ImagePart, ...]]

ERROR_CODE_SESSION_STORE_UNAVAILABLE = "session_store_unavailable"
ERROR_CODE_INFERENCE_FAILED = "inference_failed"
ERROR_CODE_INTERNAL = "internal"

DEFAULT_MAX_BUFFERED_EVENTS = 256

DEFAULT_CONFIRM_TIMEOUT_S = 120.0

HEARTBEAT_PERIOD_MS = 30_000

TurnIdFactory = Callable[[], str]

_logger = logging.getLogger(__name__)


def to_server_event(event: TurnEvent) -> ServerEvent:
    """Map one core domain event onto the wire (the core never imports wire code)."""
    if isinstance(event, DomainTextDelta):
        return ServerEvent(text_delta=WireTextDelta(text=event.text))
    if isinstance(event, DomainStatusUpdate):
        return ServerEvent(status=WireStatusUpdate(state=event.state, detail=event.detail))
    if isinstance(event, DomainToolActivity):
        return ServerEvent(
            tool_activity=WireToolActivity(tool_name=event.tool_name, summary=event.summary)
        )
    if isinstance(event, DomainToolOutcome):
        return ServerEvent(tool_outcome=WireToolOutcome(tool_name=event.tool_name, ok=event.ok))
    return ServerEvent(turn_complete=TurnComplete(turn_id=event.turn_id))


class ConverseStream:
    """One Converse stream: a pump task dispatches client events into turn tasks.

    Child tasks are awaited with ``asyncio.wait``, never a bare ``await`` under a suppressed
    ``CancelledError``: that swallowed the pump's own cancellation and hung ``aclose()``.
    """

    def __init__(
        self,
        make_engine: EngineFactory,
        *,
        max_buffered_events: int = DEFAULT_MAX_BUFFERED_EVENTS,
        confirm_timeout_s: float = DEFAULT_CONFIRM_TIMEOUT_S,
        turn_id_factory: TurnIdFactory = new_turn_id,
        sleeper: Sleeper | None = None,
    ) -> None:
        if max_buffered_events < 1:
            msg = "max_buffered_events must be at least 1"
            raise ValueError(msg)
        self._out: asyncio.Queue[ServerEvent | None] = asyncio.Queue()
        self._credits = asyncio.Semaphore(max_buffered_events)
        self._confirmer = RpcConfirmer(self._out.put_nowait, timeout_s=confirm_timeout_s)
        self._progress = RpcProgressSink(
            self._out.put_nowait, self._credits, to_wire=to_server_event
        )
        self._engine = make_engine(self._confirmer, self._progress)
        self._new_turn_id = turn_id_factory
        self._sleeper = sleeper if sleeper is not None else AsyncioSleeper()
        self._pending: deque[QueuedTurn] = deque()
        self._turn: asyncio.Task[None] | None = None
        self._failed = False

    async def events(
        self, client_events: AsyncIterator[ClientEvent]
    ) -> AsyncGenerator[ServerEvent, None]:
        """Yield ServerEvents until input ends, a SeamError fires, or the consumer closes."""
        pump = asyncio.create_task(self._pump(client_events))
        beat = asyncio.create_task(self._beat())
        try:
            while (event := await self._out.get()) is not None:
                self._credits.release()
                yield event
        finally:
            pump.cancel()
            beat.cancel()
            await asyncio.wait([pump, beat])
            await self._cancel_turn()

    async def _beat(self) -> None:
        """Send a heartbeat, with the turn's wait, once a period while nothing waits to be sent."""
        while True:
            await self._sleeper.sleep(HEARTBEAT_PERIOD_MS / 1000)
            if self._turn is not None and self._out.empty():
                # An empty queue means every credit is free, so this acquire never waits.
                await self._credits.acquire()
                self._out.put_nowait(ServerEvent(heartbeat=self._heartbeat()))

    def _heartbeat(self) -> Heartbeat:
        """The heartbeat for the current wait, which is empty when the turn waits on nothing."""
        wait = self._progress.current()
        if wait is None:
            return Heartbeat()
        return Heartbeat(wait=wait.key, detail=wait.detail)

    async def _pump(self, client_events: AsyncIterator[ClientEvent]) -> None:
        """Dispatch client events; when input ends, let the queued turns finish."""
        try:
            async for event in client_events:
                kind = event.WhichOneof("event")
                if kind == "user_turn":
                    try:
                        images = read_attachments(event.user_turn.images)
                    except AttachmentError as err:
                        _logger.warning(
                            "refusing a turn whose attachment the brain cannot use",
                            extra={"session_id": event.session_id},
                        )
                        self._fail(ERROR_CODE_ATTACHMENT_REFUSED, str(err))
                        return
                    self._enqueue_turn((event.session_id, event.user_turn.text, images))
                elif kind == "cancel":
                    await self._cancel_turn()
                elif kind == "confirm_response":
                    self._confirmer.resolve(
                        event.confirm_response.confirm_id,
                        approved=event.confirm_response.approved,
                    )
                else:
                    _logger.debug(
                        "ignoring client event without a known payload",
                        extra={"session_id": event.session_id, "kind": kind},
                    )
            # Input ended, so no answer can ever arrive and anything awaiting confirmation is
            # denied at once. The only place that closes the confirmer: on teardown the
            # in-flight turn is cancelled instead, so a disconnect audits no spurious decline.
            self._confirmer.close()
            await self._drain_turns()
        except Exception as err:  # deliberately broad: nothing may escape this stream unhandled
            _logger.exception("Converse client stream failed")
            self._fail(ERROR_CODE_INTERNAL, str(err))
        finally:
            self._out.put_nowait(None)

    def _enqueue_turn(self, turn: QueuedTurn) -> None:
        """Queue one turn; it starts immediately when nothing is running."""
        self._pending.append(turn)
        self._start_next_turn()

    def _start_next_turn(self) -> None:
        """Start the oldest queued turn unless one runs already or the stream failed."""
        if self._turn is not None or self._failed or not self._pending:
            return
        self._turn = asyncio.create_task(self._turn_task(self._pending.popleft()))

    async def _drain_turns(self) -> None:
        """Client input ended: wait until the in-flight turn and the queue are done."""
        while (turn := self._turn) is not None:
            await asyncio.wait([turn])

    async def _cancel_turn(self) -> None:
        """Stop the in-flight turn and drop the queued ones; the stream stays open."""
        self._pending.clear()
        turn = self._turn
        if turn is None:
            return
        turn.cancel()
        await asyncio.wait([turn])

    async def _turn_task(self, turn: QueuedTurn) -> None:
        """One turn task: typed failures become SeamError; completion chains the queue."""
        turn_id = self._new_turn_id()
        fields = {"session_id": turn[0], "turn_id": turn_id}
        try:
            await self._run_turn(turn, turn_id)
        except SessionStoreError as err:
            _logger.exception("session store failed mid-turn", extra=fields)
            self._fail(ERROR_CODE_SESSION_STORE_UNAVAILABLE, str(err))
        except InferenceError as err:
            _logger.exception("inference failed mid-turn", extra=fields)
            self._fail(ERROR_CODE_INFERENCE_FAILED, str(err))
        except Exception as err:  # deliberately broad: nothing may escape this stream unhandled
            _logger.exception("unexpected failure handling a turn", extra=fields)
            self._fail(ERROR_CODE_INTERNAL, str(err))
        finally:
            # Synchronous, so it runs under cancellation and completes before the task reads as
            # done: whoever awaits the task sees exact bookkeeping.
            self._turn = None
            self._start_next_turn()

    async def _run_turn(self, turn: QueuedTurn, turn_id: str) -> None:
        """One stateless turn over the store, streamed onto the output queue."""
        session_id, text, images = turn
        events = self._engine.handle_turn(session_id, text, turn_id=turn_id, images=images)
        try:
            async for event in events:
                # Backpressure: suspends generation here until the consumer frees a credit.
                await self._credits.acquire()
                self._out.put_nowait(to_server_event(event))
        finally:
            await events.aclose()

    def _fail(self, code: str, message: str) -> None:
        """Emit the terminal SeamError and mark the stream dead (no further turns)."""
        self._failed = True
        self._out.put_nowait(ServerEvent(error=SeamError(code=code, message=message)))
        self._out.put_nowait(None)
