"""Does the history fold still let go of the GPU when several Converse streams overlap?

The summarizing window's safety case has always been a **sequencing argument** rather than a
measurement, and it is worth stating exactly before testing it. The GPU lease is one
non-reentrant ``asyncio.Lock`` per ``ModelManager``, and the composition root builds one backend
over one manager for the whole process, so every stream contends for the same lock. The lease is
taken inside the adapter's stream generator, on its FIRST ``__anext__``, and held until that
generator leaves the ``async with`` block. A fold takes it through ``drain_text``, which leaves
that block in a ``finally``, and ``SummarizingHistoryWindow.select`` awaits the fold to
completion, and ``assemble_inference_messages`` awaits ``select``, and ``handle_turn`` awaits the
whole assembly several statements before it first iterates the reply's generator. So within one
turn the fold's lease and the reply's lease are two acquisitions in sequence, never one nested
inside the other.

Concurrency is what tests that argument, and until this file nothing had ever run more than one
stream. Six things the runs below are designed to falsify, only the first of which the argument
actually claims:

* **Nesting.** A fold still holding the lease when the reply asks for it deadlocks the turn on
  its own lock. ``_sequencing_violations`` looks for exactly this shape.
* **A fold interleaving with a reply.** A fold and a reply are separate acquisitions, so
  ANOTHER stream's work is free to land between them. The argument never denied this; it is the
  load cost, and it is reported per stream as the wait each acquisition sat through.
* **Serialization behind a lease.** One resident model means one turn on the GPU at a time by
  design. What has never been measured is the price, so a solo turn is run first over the same
  corpus and the concurrent turns are reported against it.
* **A fold reading history a concurrent turn is still writing.** Every stream is a distinct
  session carrying a distinct planted fact, and each answer must carry its own and no other's.
* **A shared window serving several streams.** ``HistoryWindow.select`` takes its progress sink
  per CALL precisely so one window instance stays correct for every stream, so this harness
  shares ONE window deliberately and asserts each fold's chip landed on its own stream.
* **A stalled reader keeping the card.** The reply's lease covers its generator's whole
  lifetime, and the seam's credit bound suspends generation inside it, so a consumer that stops
  reading is a consumer holding the GPU. That predates the fold and is not caused by it; what is
  new is that a fold is now among the things queueing behind it, so it is timed rather than argued.

A seventh, a swap landing mid-fold, is deliberately NOT here: this stack runs with escalation off,
so there is no swap, and with it on the swapping manager takes the very same lock and waits for the
lease to fall free rather than preempting a mid-stream round. That is a reading of ``residency.py``
and it is labelled as one in the ADR rather than dressed up as a run.

**The measurement is built to be falsifiable, and a clean green here would otherwise mean
nothing.** Concurrent streams that never actually overlap would pass every assertion above while
measuring no contention at all, so ``_contentions`` finds the moments one stream asked for the
lease while a DIFFERENT stream held it, and the run fails when it finds none. Two further tests
break the system on purpose and show the same helpers catching it: one makes a fold hold the
lease across the reply, which must be NAMED as a leak rather than merely time out, the other runs
the streams one after another, which must report no contention at all.

Integration-marked, so CI and the coverage gate never see it. It drives the shipped ``converse``
use case (the same generator the servicer calls) over the real ``LlamaCppBackend`` and the real
``RedisSessionStore``, in this process rather than through the gRPC hop, because what is measured
is the lease, and the lease lives in the brain process on either side of that hop. Bring up the
base and gpu stacks (docs/runbooks/llamacpp-gpu.md), then:

    cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \\
      uv run pytest -m integration --no-cov -s \\
      packages/orchestrator/tests/test_fold_under_load_live.py
"""

import asyncio
import os
import time
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    Confirmer,
    HistoryWindow,
    InferenceEvent,
    JsonSchema,
    Message,
    ModelLease,
    ModelManager,
    ProgressSink,
    Role,
    SingleResidentModelManager,
    SystemClock,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
    TurnRunner,
)
from cortex_core.inference import GenerationBounds
from cortex_core.recap_prompt import RECAP_BOUNDS
from cortex_core.summarizing import RECAP_PROGRESS_STATE
from cortex_inference import LlamaCppBackend
from cortex_orchestrator import DEFAULT_MAX_BUFFERED_EVENTS, EngineFactory, converse
from cortex_orchestrator.config import BrainRuntimeConfig
from cortex_orchestrator.window_builders import build_history_window
from cortex_seam import ClientEvent, ServerEvent, UserTurn
from cortex_session import DEFAULT_REDIS_URL, RedisSessionStore

_MODEL = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
_ENDPOINT = os.environ.get("CORTEX_INFERENCE_ENDPOINT", "http://127.0.0.1:8080")
_REDIS = os.environ.get("CORTEX_REDIS_URL", DEFAULT_REDIS_URL)
_AT = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)

# Small on purpose, the way the single-stream recap measurement sizes it: what matters is the
# ratio of window to conversation, and a short corpus keeps each stream to one fold and one
# reply rather than a transcript's worth of generation. The fold floor is left at its shipped
# default and clamped to this budget by `build_history_window`, which is the production path.
_BUDGET = 350

# How many streams overlap. Two prove contention; three make the queue behind a held lease
# visible, which is what "under load" is actually asking about.
_STREAMS = 3

# One planted fact per stream, distinct enough that a reply carrying the wrong one is
# unmistakable. The question at the end depends on it and nothing after the opening repeats it.
_REFERENCES = ("QH7-4412", "ZB2-8830", "LM5-6017")
_QUESTION = "remind me of my booking reference"

_FILLER = [
    ("what is the weather usually like there in spring?", "Mild, with rain most weeks."),
    ("is the tap water fine to drink?", "Yes, it is treated and safe everywhere in the city."),
    ("do I need an adapter for the sockets?", "Yes, a type G adapter."),
    ("how far is the centre from the airport?", "About forty minutes by train."),
    ("are the museums open on Mondays?", "Most close on Mondays; the maritime one does not."),
    ("should I book restaurants ahead?", "For the weekend, yes."),
    ("is the transit card worth it?", "If you make more than three trips a day."),
    ("what plug voltage do they run?", "Two hundred and thirty volts."),
]

# Which acquisition a lease record belongs to. The fold is the only call in a turn carrying
# RECAP_BOUNDS, so the phase is read off the request rather than guessed from ordering.
_FOLD = "fold"
_REPLY = "reply"

# The stream a lease belongs to. Set once per driving coroutine; every task converse creates
# below it (the pump, then each turn) copies the context, so the backend reads the right label
# from inside handle_turn without anything being threaded through the ports.
_LABEL: ContextVar[str] = ContextVar("cortex_fold_load_stream", default="?")


@dataclass
class _Lease:
    """One model call's timeline on the GPU lease, in monotonic seconds.

    ``granted`` stays ``None`` for a call still queued when the run ended, and ``released``
    for one that took the lease and never gave it back. Both are shapes a broken sequencing
    produces, so they are recorded rather than asserted away.
    """

    stream: str
    phase: str
    requested: float
    granted: float | None = None
    released: float | None = None

    @property
    def wait(self) -> float:
        """Seconds this call spent queued for the lease (0.0 while it is still queued)."""
        return 0.0 if self.granted is None else self.granted - self.requested

    @property
    def held(self) -> float:
        """Seconds this call held the lease (0.0 while it holds it still, or never got it)."""
        if self.granted is None or self.released is None:
            return 0.0
        return self.released - self.granted


@dataclass(frozen=True)
class _Hold:
    """A completed lease interval: the same record with both ends known."""

    stream: str
    phase: str
    granted: float
    released: float


def _holds(log: Sequence[_Lease]) -> list[_Hold]:
    """Every acquisition that both got the lease and gave it back."""
    return [
        _Hold(record.stream, record.phase, record.granted, record.released)
        for record in log
        if record.granted is not None and record.released is not None
    ]


class _RecordingManager:
    """The real manager, timestamped for ONE call. Delegates the lock, so the lock is real."""

    def __init__(self, inner: ModelManager, record: _Lease, granted: asyncio.Event) -> None:
        self._inner = inner
        self._record = record
        self._granted = granted

    @asynccontextmanager
    async def acquire(self, model: str) -> AsyncGenerator[ModelLease, None]:
        self._record.requested = time.monotonic()
        async with self._inner.acquire(model) as lease:
            self._record.granted = time.monotonic()
            self._granted.set()
            try:
                yield lease
            finally:
                self._record.released = time.monotonic()


class _RecordingBackend:
    """The shipped adapter with a lease log around it, one record per model call.

    A fresh ``LlamaCppBackend`` per call is what makes the record per call: the adapter is two
    references and no state, and it is the only place a manager can be substituted without
    touching production code. Nothing about the request changes.
    """

    def __init__(self, manager: ModelManager, client: httpx.AsyncClient) -> None:
        self._manager = manager
        self._client = client
        self.log: list[_Lease] = []
        # Fires on every grant, so a test that must start one stream only once another is
        # really on the GPU waits for the lock rather than polling for it.
        self.granted = asyncio.Event()

    def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        record = _Lease(
            stream=_LABEL.get(),
            phase=_FOLD if bounds == RECAP_BOUNDS else _REPLY,
            requested=time.monotonic(),
        )
        self.log.append(record)
        leases = _RecordingManager(self._manager, record, self.granted)
        return LlamaCppBackend(leases, self._client).stream(
            model, messages, tools=tools, schema=schema, bounds=bounds
        )


@dataclass
class _Run:
    """What one stream did, as its client saw it."""

    label: str
    session_id: str
    started: float
    first_token: float | None = None
    completed: float | None = None
    answer: str = ""
    statuses: list[str] = field(default_factory=list[str])

    @property
    def ttft(self) -> float:
        """Seconds from sending the turn to its first reply token (-1.0 if none arrived)."""
        return -1.0 if self.first_token is None else self.first_token - self.started

    @property
    def wall(self) -> float:
        """Seconds from sending the turn to TurnComplete (-1.0 if it never completed)."""
        return -1.0 if self.completed is None else self.completed - self.started


def _corpus(reference: str) -> list[Message]:
    """A conversation whose opening carries ``reference`` and whose middle buries it."""
    opening = [
        (f"my booking reference is {reference} and the flight lands at 06:20", "Noted."),
        ("the hotel is the Marlow on Gilbert Street, checking in late", "The Marlow, late."),
        ("put the whole trip on the personal card, not the company one", "Personal card it is."),
    ]
    messages: list[Message] = []
    for index, (user, assistant) in enumerate([*opening, *_FILLER]):
        turn = f"t{index}"
        messages.append(Message(role=Role.USER, text=user, at=_AT, turn_id=turn))
        messages.append(Message(role=Role.ASSISTANT, text=assistant, at=_AT, turn_id=turn))
    return messages


async def _one_turn(session_id: str) -> AsyncIterator[ClientEvent]:
    """One UserTurn then half-close, which is what makes converse drain and end the stream."""
    yield ClientEvent(session_id=session_id, user_turn=UserTurn(text=_QUESTION))


def _absorb(run: _Run, event: ServerEvent) -> None:
    """Fold one wire event into the stream's record."""
    kind = event.WhichOneof("event")
    if kind == "text_delta":
        run.first_token = run.first_token if run.first_token is not None else time.monotonic()
        run.answer += event.text_delta.text
    elif kind == "status":
        run.statuses.append(event.status.state)
    elif kind == "turn_complete":
        run.completed = time.monotonic()
    elif kind == "error":
        msg = f"stream {run.label} failed: {event.error.code} {event.error.message}"
        raise AssertionError(msg)


async def _drive(
    label: str,
    session_id: str,
    make_engine: EngineFactory,
    *,
    stall_s: float = 0.0,
    buffer: int = DEFAULT_MAX_BUFFERED_EVENTS,
) -> _Run:
    """Open one Converse stream, ask the question, and time what comes back.

    ``stall_s`` makes this consumer stop reading for that long once the reply has started,
    and ``buffer`` is the stream's credit bound, so a small one turns the stall into real
    backpressure rather than into events piling up unread. Both default to what a live
    consumer does, which is read as fast as it can at the shipped bound.
    """
    _LABEL.set(label)
    run = _Run(label=label, session_id=session_id, started=time.monotonic())
    async for event in converse(make_engine, _one_turn(session_id), max_buffered_events=buffer):
        _absorb(run, event)
        if stall_s and run.first_token is not None:
            await asyncio.sleep(stall_s)
            stall_s = 0.0
    return run


def _contentions(log: Sequence[_Lease]) -> list[tuple[_Lease, _Hold]]:
    """Every moment one stream asked for the lease while a DIFFERENT stream held it.

    This is the overlap proof, and it is deliberately the strictest reading of overlap there
    is: not "the turns ran in the same minute" but "this acquisition was issued strictly
    inside that acquisition's hold". An empty list means the streams never really contended
    and the run measured nothing, which is a failure and not a clean result.
    """
    holds = _holds(log)
    return [
        (waiter, holder)
        for waiter in log
        for holder in holds
        if holder.stream != waiter.stream and holder.granted <= waiter.requested < holder.released
    ]


def _unfinished(log: Sequence[_Lease]) -> list[str]:
    """Acquisitions that never completed: the shape a leaked lease leaves behind."""
    problems: list[str] = []
    for record in log:
        if record.granted is None:
            problems.append(f"{record.stream}/{record.phase} waited for the lease and never got it")
        elif record.released is None:
            problems.append(f"{record.stream}/{record.phase} took the lease and never released it")
    return problems


def _sequencing_violations(log: Sequence[_Lease]) -> list[str]:
    """Every way the sequencing argument could be wrong, read off the recorded timeline.

    Three shapes. The unfinished acquisitions above are what a fold that never let go looks
    like from here. Two holds overlapping anywhere would mean the timeline is not measuring
    the lock at all, since a non-reentrant lock cannot have two holders. And the argument's
    own claim is the third: within one stream, a fold's hold ends before its reply's begins.
    """
    problems = _unfinished(log)
    holds = _holds(log)
    for first in holds:
        for second in holds:
            if first.granted < second.granted < first.released:
                problems.append(
                    f"{first.stream}/{first.phase} and {second.stream}/{second.phase} "
                    "held the lease at the same time"
                )
        if first.phase != _REPLY:
            continue
        folds = [f for f in holds if f.stream == first.stream and f.phase == _FOLD]
        if any(fold.released > first.granted for fold in folds):
            problems.append(f"{first.stream}: a fold still held the lease when the reply started")
    return problems


@dataclass
class _Harness:
    """The production wiring, with the lease log and one window shared by every stream."""

    store: RedisSessionStore
    backend: _RecordingBackend
    window: HistoryWindow

    def engine_factory(self, window: HistoryWindow | None = None) -> EngineFactory:
        """This stream's engine: the shared window, and only the progress sink per stream.

        Memory, tools, the guardrail and titles are all off. Each is another model call or
        another service, and none of them is what is being measured; leaving them on would put
        acquisitions in the timeline that say nothing about the fold.
        """
        chosen = self.window if window is None else window

        def make(confirmer: Confirmer, progress: ProgressSink) -> TurnRunner:
            del confirmer
            return TurnEngine(
                self.store,
                self.backend,
                SystemClock(),
                cortex_model=_MODEL,
                capabilities=TurnCapabilities(window=chosen, progress=progress),
            )

        return make

    async def seed(self, session_id: str, reference: str) -> None:
        """Plant a conversation long enough that the budget drops its opening."""
        await self.store.delete(session_id)
        for message in _corpus(reference):
            await self.store.append(session_id, message)


@asynccontextmanager
async def _harness() -> AsyncGenerator[_Harness, None]:
    """Build the real adapters through the real window builder, and release them afterwards."""
    client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=None))
    store = RedisSessionStore.from_url(_REDIS)
    backend = _RecordingBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
    runtime = BrainRuntimeConfig(history_char_budget=_BUDGET, history_summary=True)
    window = build_history_window(runtime, sessions=store, backend=backend, clock=SystemClock())
    assert window is not None, "the builder refused to build a window for this config"
    try:
        yield _Harness(store=store, backend=backend, window=window)
    finally:
        await client.aclose()
        await store.aclose()


def _blockers(record: _Lease, holds: Sequence[_Hold]) -> list[str]:
    """Whose holds this acquisition sat behind: the load cost, attributed rather than totalled.

    A reply naming another stream's FOLD here is the interleaving the argument never denied and
    nothing had ever measured, so it is printed by name instead of disappearing into a mean.
    """
    if record.granted is None:
        return []
    return [
        f"{hold.stream}/{hold.phase}"
        for hold in holds
        if hold.stream != record.stream
        and hold.granted < record.granted
        and hold.released > record.requested
    ]


def _report(runs: Sequence[_Run], log: Sequence[_Lease], origin: float) -> str:
    """The evidence, as one block: every lease interval and every stream's own timings."""
    holds = _holds(log)
    lines = ["lease timeline (seconds from the first acquisition request):"]
    for record in sorted(log, key=lambda r: r.requested):
        granted = "never" if record.granted is None else f"{record.granted - origin:.2f}"
        released = "never" if record.released is None else f"{record.released - origin:.2f}"
        behind = ", ".join(_blockers(record, holds)) or "nothing"
        lines.append(
            f"  {record.stream}/{record.phase}: asked {record.requested - origin:.2f},"
            f" granted {granted}, released {released},"
            f" waited {record.wait:.2f} behind {behind}, held {record.held:.2f}"
        )
    lines.extend(
        f"  {run.label}: first token {run.ttft:.1f}s, turn {run.wall:.1f}s,"
        f" folding chips {run.statuses.count(RECAP_PROGRESS_STATE)},"
        f" answer {run.answer.strip()!r}"
        for run in runs
    )
    return "\n".join(lines)


def _context_is_uncrossed(runs: Sequence[_Run]) -> None:
    """Every stream answered with its own planted reference and with nobody else's."""
    for run, reference in zip(runs, _REFERENCES, strict=True):
        assert reference in run.answer, f"{run.label} lost its own reference"
        assert all(other not in run.answer for other in _REFERENCES if other != reference)


@pytest.mark.integration
async def test_a_fold_keeps_letting_go_of_the_gpu_when_streams_overlap() -> None:
    """The measurement: concurrent Converse streams, each folding, over one real cortex.

    A solo turn runs first over the same corpus so the concurrent numbers have something to be
    read against; its lease log is then set aside and the concurrent run is measured on its own
    timeline. What is asserted is what must hold whatever the model says: the folds really
    happened, the streams really contended, no lease was ever nested or shared, every fold's
    chip landed on its own stream, and no answer carries another session's booking reference.
    """
    async with _harness() as harness:
        sessions = [f"fold-load-{index}" for index in range(_STREAMS)]
        solo_session = "fold-load-solo"
        try:
            await harness.seed(solo_session, _REFERENCES[0])
            solo = await _drive("solo", solo_session, harness.engine_factory())
            solo_log = list(harness.backend.log)
            harness.backend.log.clear()

            for session, reference in zip(sessions, _REFERENCES, strict=True):
                await harness.seed(session, reference)
            runs = list(
                await asyncio.gather(
                    *(
                        _drive(f"s{index}", session, harness.engine_factory())
                        for index, session in enumerate(sessions)
                    )
                )
            )
            log = list(harness.backend.log)
            origin = min(record.requested for record in log)
            print(  # noqa: T201 -- the measurement IS this test's output
                f"\nsolo turn over the same corpus: first token {solo.ttft:.1f}s,"
                f" turn {solo.wall:.1f}s,"
                f" fold held {sum(r.held for r in solo_log if r.phase == _FOLD):.1f}s"
                f"\n{_STREAMS} concurrent streams:\n{_report(runs, log, origin)}"
                f"\ncontentions (a stream asked while another held): {len(_contentions(log))}"
            )
            assert [record.phase for record in solo_log] == [_FOLD, _REPLY]
            # The folds really happened: one per stream, and each said so on its own stream.
            folded = sorted(record.stream for record in log if record.phase == _FOLD)
            assert folded == [f"s{index}" for index in range(_STREAMS)]
            for run in runs:
                assert run.statuses.count(RECAP_PROGRESS_STATE) == 1
            # The overlap really happened. Without this the run is a null result dressed green.
            assert _contentions(log), "the streams never contended; this run measured nothing"
            # And the argument held: no nesting, no shared lease, fold before reply.
            assert _sequencing_violations(log) == []
            _context_is_uncrossed(runs)
            for session, reference in zip(sessions, _REFERENCES, strict=True):
                recap = await harness.store.recap(session)
                assert recap is not None
                assert all(other not in recap.text for other in _REFERENCES if other != reference)
        finally:
            for session in [*sessions, solo_session]:
                await harness.store.delete(session)


@pytest.mark.integration
async def test_two_streams_on_one_session_do_not_hand_each_other_the_wrong_context() -> None:
    """The other concurrency: two turns of the SAME session in flight at once.

    One Converse stream runs its turns one at a time, so this shape needs two streams naming
    one session, and it is the case the fold's cache could plausibly get wrong: both turns
    append a user message, both read a history the other is still growing, both fold, and both
    write a recap under one key. Append-only history is what is supposed to make that safe, a
    recap of a prefix going stale-but-never-wrong, so what is asserted is that neither turn
    lost the session's own fact and the surviving recap still names a prefix of the history
    that is really there.
    """
    async with _harness() as harness:
        session = "fold-load-shared"
        try:
            await harness.seed(session, _REFERENCES[0])
            harness.backend.log.clear()
            runs = list(
                await asyncio.gather(
                    *(_drive(f"c{index}", session, harness.engine_factory()) for index in range(2))
                )
            )
            log = list(harness.backend.log)
            history = await harness.store.history(session)
            recap = await harness.store.recap(session)
            print(  # noqa: T201 -- the measurement IS this test's output
                f"\ntwo streams on one session:"
                f"\n{_report(runs, log, min(r.requested for r in log))}"
                f"\nhistory now {len(history)} messages,"
                f" recap covers {None if recap is None else recap.covers}"
                f"\ncontentions: {len(_contentions(log))}"
            )
            assert _contentions(log), "the two turns never overlapped; this run measured nothing"
            assert _sequencing_violations(log) == []
            # Both turns answered from their own session, and the reference is the session's.
            for run in runs:
                assert _REFERENCES[0] in run.answer, f"{run.label} lost the session's reference"
            # Both turns are on record, and the recap names a prefix that really exists.
            assert len(history) == len(_corpus(_REFERENCES[0])) + 4
            assert recap is not None
            assert 1 <= recap.covers <= len(history)
        finally:
            await harness.store.delete(session)


# How long the stalled consumer below stops reading for, and the bound its stream runs at. One
# credit so the stall becomes backpressure on the first event rather than 256 events later; the
# stall is several times a normal reply's hold, so a wait it causes cannot be read as one.
_STALL_S = 12.0
_STALL_BUFFER = 1


async def _wait_for_reply_lease(backend: _RecordingBackend, label: str) -> None:
    """Block until ``label`` is actually generating, so the next stream really queues behind it.

    The clear-then-wait is safe because nothing between the test and the clear awaits, so no
    grant can slip through the gap on a single-threaded loop.
    """
    while not any(
        record.stream == label and record.phase == _REPLY and record.granted is not None
        for record in backend.log
    ):
        backend.granted.clear()
        await backend.granted.wait()


@pytest.mark.integration
async def test_a_consumer_that_stops_reading_holds_the_gpu_a_later_fold_needs() -> None:
    """What a stalled reader costs every other stream, which is a number and not an argument.

    The reply's lease is held for the generator's whole lifetime, and the seam's credit bound
    suspends generation inside it when a consumer stops reading, so a stalled reader keeps the
    GPU. That is the shipped backpressure behaving as designed, and it predates the fold; what
    is new under load is who pays, because the next stream's FOLD is now among the things that
    queue behind it. This measures that rather than reasoning about it: one stream stalls
    mid-reply at a one-credit bound, a second starts once the first is really generating, and
    the second's fold is timed against the stall.
    """
    async with _harness() as harness:
        sessions = ["fold-load-stall-0", "fold-load-stall-1"]
        try:
            for session, reference in zip(sessions, _REFERENCES, strict=False):
                await harness.seed(session, reference)
            harness.backend.log.clear()

            async def follower() -> _Run:
                await _wait_for_reply_lease(harness.backend, "stalled")
                return await _drive("after", sessions[1], harness.engine_factory())

            runs = list(
                await asyncio.gather(
                    _drive(
                        "stalled",
                        sessions[0],
                        harness.engine_factory(),
                        stall_s=_STALL_S,
                        buffer=_STALL_BUFFER,
                    ),
                    follower(),
                )
            )
            log = list(harness.backend.log)
            fold = next(r for r in log if r.stream == "after" and r.phase == _FOLD)
            reply = next(r for r in log if r.stream == "stalled" and r.phase == _REPLY)
            print(  # noqa: T201 -- the measurement IS this test's output
                f"\na consumer stalling {_STALL_S:.0f}s at a {_STALL_BUFFER}-credit bound:"
                f"\n{_report(runs, log, min(r.requested for r in log))}"
            )
            assert _sequencing_violations(log) == []
            # The stall really landed inside the reply's hold, and the later fold really waited
            # it out. Both bounds are well clear of what an unstalled reply holds for here.
            assert reply.held > _STALL_S
            assert fold.wait > _STALL_S / 2
            assert "stalled/reply" in _blockers(fold, _holds(log))
        finally:
            for session in sessions:
                await harness.store.delete(session)


# How long a stream gets before the deliberately broken arm below is called deadlocked. Well
# past a fold plus a reply on this corpus, which the runs above measure at a few seconds each.
_DEADLOCK_TIMEOUT_S = 30.0


class _LeakyWindow:
    """The shipped window with the fold's stream left open: the sequencing bug, on purpose.

    ``drain_text`` exists so the fold leaves the adapter's acquire block at a statement rather
    than at the collector's convenience. This does what the code would do without it: opens a
    model call, pulls one event so the lease is really taken, and keeps a reference to the
    generator so nothing finalizes it. The reply's acquire then queues behind a lease nobody
    is using, which is the deadlock the argument says cannot happen.
    """

    def __init__(self, inner: HistoryWindow, backend: _RecordingBackend) -> None:
        self._inner = inner
        self._backend = backend
        self.leaked: list[AsyncIterator[InferenceEvent]] = []

    async def select(
        self,
        history: Sequence[Message],
        *,
        session_id: str,
        progress: ProgressSink | None = None,
    ) -> Sequence[Message]:
        kept = await self._inner.select(history, session_id=session_id, progress=progress)
        stream = self._backend.stream(
            _MODEL,
            [Message(role=Role.USER, text="count slowly to fifty", at=_AT, turn_id="leak")],
            bounds=RECAP_BOUNDS,
        )
        self.leaked.append(stream)
        await anext(stream)
        return kept

    async def release(self) -> None:
        """Close what was leaked, so the harness can tear down after the test has looked."""
        for stream in self.leaked:
            if isinstance(stream, AsyncGenerator):
                await stream.aclose()
        self.leaked.clear()


@pytest.mark.integration
async def test_the_timeline_catches_a_fold_that_holds_the_lease_across_the_reply() -> None:
    """Distrust green: break the sequencing and show the same helper reddening.

    A concurrency test that passes on a broken system is worthless, so the check that returned
    an empty list above is run against a window that really does hold the lease into the reply.
    It must both hang the turn and NAME the leak, because a test that only notices a timeout
    cannot tell a deadlock from a slow model.
    """
    async with _harness() as harness:
        session = "fold-load-leak"
        leaky = _LeakyWindow(harness.window, harness.backend)
        try:
            await harness.seed(session, _REFERENCES[0])
            harness.backend.log.clear()
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(
                    _drive("leak", session, harness.engine_factory(leaky)),
                    timeout=_DEADLOCK_TIMEOUT_S,
                )
            problems = _sequencing_violations(harness.backend.log)
            print(f"\nbroken arm: {problems}")  # noqa: T201 -- the proof IS this test's output
            assert any("never released it" in problem for problem in problems)
            assert any("never got it" in problem for problem in problems)
        finally:
            await leaky.release()
            await harness.store.delete(session)


@pytest.mark.integration
async def test_the_overlap_proof_finds_nothing_when_the_streams_do_not_overlap() -> None:
    """Distrust green, the other half: prove the overlap check can come back empty.

    The measurement above fails when it finds no contention, which is only meaningful if
    contention is something it could genuinely fail to find. The same two streams, run one
    after the other rather than together, must produce an empty list from the same helper.
    """
    async with _harness() as harness:
        sessions = [f"fold-load-serial-{index}" for index in range(2)]
        try:
            for session, reference in zip(sessions, _REFERENCES, strict=False):
                await harness.seed(session, reference)
            harness.backend.log.clear()
            for index, session in enumerate(sessions):
                await _drive(f"q{index}", session, harness.engine_factory())
            log = harness.backend.log
            print(  # noqa: T201 -- the proof IS this test's output
                f"\nserial arm: {len(log)} leases, {len(_contentions(log))} contentions"
            )
            # Every acquisition still happened, and every one of them was uncontended.
            assert sorted(record.phase for record in log) == [_FOLD, _FOLD, _REPLY, _REPLY]
            assert _sequencing_violations(log) == []
            assert _contentions(log) == []
        finally:
            for session in sessions:
                await harness.store.delete(session)
