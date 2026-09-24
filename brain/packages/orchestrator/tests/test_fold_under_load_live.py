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

# Small on purpose: what matters is the ratio of window to conversation, and a short corpus
# keeps each stream to one fold and one reply.
_BUDGET = 350

# Two streams prove contention; three make the queue behind a held lease visible.
_STREAMS = 3

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

_FOLD = "fold"
_REPLY = "reply"

_LABEL: ContextVar[str] = ContextVar("cortex_fold_load_stream", default="?")


@dataclass
class _Lease:
    """One model call's timeline on the GPU lease, in monotonic seconds."""

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
    """The real manager, timestamped for ONE call."""

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
    """The shipped adapter with a lease log around it, one record per model call."""

    def __init__(self, manager: ModelManager, client: httpx.AsyncClient) -> None:
        self._manager = manager
        self._client = client
        self.log: list[_Lease] = []
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
    """A conversation whose opening states ``reference``, with enough after it to push it out."""
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
    """Open one Converse stream, ask the question, and time what comes back."""
    _LABEL.set(label)
    run = _Run(label=label, session_id=session_id, started=time.monotonic())
    async for event in converse(make_engine, _one_turn(session_id), max_buffered_events=buffer):
        _absorb(run, event)
        if stall_s and run.first_token is not None:
            await asyncio.sleep(stall_s)
            stall_s = 0.0
    return run


def _contentions(log: Sequence[_Lease]) -> list[tuple[_Lease, _Hold]]:
    """Every moment one stream asked for the lease while a DIFFERENT stream held it."""
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
    """Every way the sequencing argument could be wrong, read off the recorded timeline."""
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
        """This stream's engine: the shared window, and only the progress sink per stream."""
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
    window = build_history_window(
        runtime, sessions=store, backend=backend, clock=SystemClock(), model=runtime.cortex_model
    )
    assert window is not None, "the builder refused to build a window for this config"
    try:
        yield _Harness(store=store, backend=backend, window=window)
    finally:
        await client.aclose()
        await store.aclose()


def _blockers(record: _Lease, holds: Sequence[_Hold]) -> list[str]:
    """Return the holds this acquisition sat behind, which attributes the load cost per holder
    rather than totalling it.
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
    """Render the evidence as one block: every lease interval and every stream's own timings."""
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
            folded = sorted(record.stream for record in log if record.phase == _FOLD)
            assert folded == [f"s{index}" for index in range(_STREAMS)]
            for run in runs:
                assert run.statuses.count(RECAP_PROGRESS_STATE) == 1
            assert _contentions(log), "the streams never contended; this run measured nothing"
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
            for run in runs:
                assert _REFERENCES[0] in run.answer, f"{run.label} lost the session's reference"
            assert len(history) == len(_corpus(_REFERENCES[0])) + 4
            assert recap is not None
            assert 1 <= recap.covers <= len(history)
        finally:
            await harness.store.delete(session)


# One credit, so the stall becomes backpressure on the first event rather than 256 events later.
# The stall is several times a normal reply's hold, so a wait it causes cannot be read as one.
_STALL_S = 12.0
_STALL_BUFFER = 1


async def _wait_for_reply_lease(backend: _RecordingBackend, label: str) -> None:
    """Block until ``label`` is actually generating, so the next stream really queues behind it."""
    while not any(
        record.stream == label and record.phase == _REPLY and record.granted is not None
        for record in backend.log
    ):
        backend.granted.clear()
        await backend.granted.wait()


@pytest.mark.integration
async def test_a_consumer_that_stops_reading_holds_the_gpu_a_later_fold_needs() -> None:
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
            assert reply.held > _STALL_S
            assert fold.wait > _STALL_S / 2
            assert "stalled/reply" in _blockers(fold, _holds(log))
        finally:
            for session in sessions:
                await harness.store.delete(session)


# Well past a fold plus a reply on this corpus, which the runs above measure at a few seconds.
_DEADLOCK_TIMEOUT_S = 30.0


class _LeakyWindow:
    """The shipped window with the fold's stream left open: the sequencing bug, on purpose."""

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
            assert sorted(record.phase for record in log) == [_FOLD, _FOLD, _REPLY, _REPLY]
            assert _sequencing_violations(log) == []
            assert _contentions(log) == []
        finally:
            for session in sessions:
                await harness.store.delete(session)
