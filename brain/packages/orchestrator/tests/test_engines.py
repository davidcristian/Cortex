import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import pytest
from fakeredis import FakeAsyncRedis, FakeServer

from cortex_core import (
    CAPTURE_SCREEN_TOOL_NAME,
    ESCALATE_TOOL_NAME,
    GET_VOLUME_TOOL_NAME,
    HANDOFF_AHEAD_DETAIL,
    SWAPPING,
    AsyncioSleeper,
    AttachmentError,
    CaptureBounds,
    EscalatingTurnEngine,
    GenerationBounds,
    HashEmbedder,
    ImagePart,
    InferenceBackend,
    InferenceEvent,
    InMemoryBodyGateway,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    JudgeRecallPolicy,
    MemoryRecaller,
    Message,
    RecordingConfirmer,
    RecordingProgressSink,
    Role,
    ScriptedVisionProbe,
    StatusUpdate,
    SystemClock,
    TextChunk,
    TextDelta,
    ToolCall,
    ToolRegistry,
    ToolSpec,
    TurnEngine,
    TurnEvent,
    TurnRunner,
)
from cortex_orchestrator import (
    BrainRuntimeConfig,
    DispatchSetup,
    InferenceConfig,
    SwapConfig,
    SwapRuntime,
    ToolsConfig,
    build_builtin_tools,
    build_swap_runtime,
    swap_closer,
)
from cortex_orchestrator.engines import DeepTier, StreamEngines
from cortex_session import RedisHandoffStore

_SEND_SPEC = ToolSpec(name="send_email", description="send one", parameters={})
_SEND_CALL = ToolCall(id="c1", name="send_email", arguments={"to": "someone"})
_ESCALATE_CALL = ToolCall(id="c2", name=ESCALATE_TOOL_NAME, arguments={"brief": "go deep"})


@dataclass(frozen=True, slots=True)
class _Request:
    """One completion the engine asked for: which tier, what it was offered, how far it may go."""

    model: str
    tools: tuple[str, ...]
    bounds: GenerationBounds | None


class _Model:
    """An ``InferenceBackend`` that records every request and replays a script per model id."""

    def __init__(self, script: Mapping[str, Sequence[Sequence[InferenceEvent]]]) -> None:
        self._script = {model: list(rounds) for model, rounds in script.items()}
        self.requests: list[_Request] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        """Record the request, then yield this tier's next scripted round (the last repeats)."""
        del messages, schema
        rounds = self._script[model]
        step = min(sum(1 for request in self.requests if request.model == model), len(rounds) - 1)
        self.requests.append(
            _Request(model=model, tools=tuple(spec.name for spec in tools), bounds=bounds)
        )
        for event in rounds[step]:
            yield event

    def offered(self, model: str) -> set[str]:
        """Every tool name this tier was offered across the turn's completions."""
        return {
            name for request in self.requests if request.model == model for name in request.tools
        }


def _engines(backend: _Model, *, tools: ToolRegistry | None = None) -> StreamEngines:
    """A factory over in-memory parts, with every optional capability off unless a case adds it."""
    return StreamEngines(
        sessions=InMemorySessionStore(),
        backend=backend,
        clock=SystemClock(),
        runtime=BrainRuntimeConfig(),
        memory=None,
        tools=tools,
        builtins=(),
        dispatch=DispatchSetup(ToolsConfig().dispatch_policy),
        sight=None,
        record_tainted_memory=False,
        bounds=None,
        deep=None,
    )


async def _sent(arguments: Mapping[str, object]) -> str:
    """The one remote tool these cases dispatch; it needs approval under `CORTEX_TOOLS_GATED`."""
    del arguments
    return "ok"


async def _run(engine: TurnRunner, text: str, *, turn_id: str) -> list[TurnEvent]:
    return [event async for event in engine.handle_turn("s", text, turn_id=turn_id)]


def _swap_runtime() -> SwapRuntime:
    """Build the process-wide handoff half the root would have built, over the scripted host."""
    runtime = build_swap_runtime(
        SwapConfig(escalation=True, modelhost_backend="scripted", brain_endpoint="http://brain"),
        BrainRuntimeConfig(),
        InferenceConfig(),
        SystemClock(),
        AsyncioSleeper(),
        lambda _url: RedisHandoffStore(FakeAsyncRedis(server=FakeServer())),
    )
    assert runtime is not None
    return runtime


def _escalating(backend: _Model, swap: SwapRuntime) -> StreamEngines:
    """The root's escalating composition: the cortex's set with the screen tool, the deep tier's
    without it.
    """
    body = InMemoryBodyGateway()
    cortex_set = build_builtin_tools(
        None, body, escalation=True, vision=CaptureBounds(max_edge=800, max_bytes=1_000)
    )
    deep_set = build_builtin_tools(None, body, escalation=True, vision=None)
    return replace(
        _engines(backend),
        builtins=cortex_set,
        sight=ScriptedVisionProbe((True,)),
        deep=DeepTier(swap, deep_set, None),
    )


async def test_each_stream_confirms_through_its_own_overlay() -> None:
    backend = _Model(
        {"cortex": [[_SEND_CALL], [TextChunk("sent")], [_SEND_CALL], [TextChunk("sent")]]}
    )
    engines = _engines(backend, tools=InMemoryToolRegistry({"send_email": (_SEND_SPEC, _sent)}))
    first = RecordingConfirmer(answer=True)
    second = RecordingConfirmer(answer=False)

    await _run(engines.for_stream(first, RecordingProgressSink()), "one", turn_id="t1")
    await _run(engines.for_stream(second, RecordingProgressSink()), "two", turn_id="t2")

    assert [request.tool_name for request in first.requests] == ["send_email"]
    assert [request.tool_name for request in second.requests] == ["send_email"]


async def test_only_a_wired_handoff_wraps_a_streams_engine() -> None:
    backend = _Model({"cortex": [[TextChunk("hi")]]})
    plain = _engines(backend)
    confirmer = RecordingConfirmer(answer=True)
    assert isinstance(plain.for_stream(confirmer, RecordingProgressSink()), TurnEngine)

    swap = _swap_runtime()
    try:
        wrapped = replace(plain, deep=DeepTier(swap, (), None))
        engine = wrapped.for_stream(confirmer, RecordingProgressSink())
        assert isinstance(engine, EscalatingTurnEngine)
    finally:
        await swap_closer(swap)()


async def test_the_deep_model_is_offered_the_tier_set_the_root_built_for_it() -> None:
    backend = _Model(
        {
            "cortex": [[_ESCALATE_CALL], [TextChunk("handing over. ")]],
            "brain": [[TextChunk("the deep answer")]],
        }
    )
    swap = _swap_runtime()
    try:
        engines = _escalating(backend, swap)
        engine = engines.for_stream(RecordingConfirmer(answer=True), RecordingProgressSink())
        await _run(engine, "hello", turn_id="t1")
    finally:
        await swap_closer(swap)()

    assert CAPTURE_SCREEN_TOOL_NAME in backend.offered("cortex")
    deep = backend.offered("brain")
    assert deep, "the deep phase never ran, so nothing was offered to it"
    assert CAPTURE_SCREEN_TOOL_NAME not in deep
    assert GET_VOLUME_TOOL_NAME in deep, "the deep tier keeps every other built-in"


async def test_the_deployments_reply_bounds_reach_both_phases_of_a_turn() -> None:
    bounds = GenerationBounds(max_tokens=512, thinking=False)
    backend = _Model(
        {
            "cortex": [[_ESCALATE_CALL], [TextChunk("handing over. ")]],
            "brain": [[TextChunk("the deep answer")]],
        }
    )
    swap = _swap_runtime()
    try:
        engines = replace(_escalating(backend, swap), bounds=bounds)
        engine = engines.for_stream(RecordingConfirmer(answer=True), RecordingProgressSink())
        await _run(engine, "hello", turn_id="t1")
    finally:
        await swap_closer(swap)()

    asked = {request.model: request.bounds for request in backend.requests}
    assert asked == {"cortex": bounds, "brain": bounds}


async def test_a_stream_s_turn_announces_a_handoff_it_waits_behind() -> None:
    backend = _Model({"cortex": [[TextChunk("hi")]]})
    swap = _swap_runtime()
    entered = asyncio.Event()
    leave = asyncio.Event()

    async def handoff_ahead() -> None:
        async with swap.manager.swap_scope("brain"):
            entered.set()
            await leave.wait()

    try:
        ahead = asyncio.create_task(handoff_ahead())
        await entered.wait()
        progress = RecordingProgressSink()
        engine = _escalating(backend, swap).for_stream(RecordingConfirmer(answer=True), progress)
        turn = asyncio.create_task(_run(engine, "hello", turn_id="t2"))
        for _ in range(10):
            await asyncio.sleep(0)
        assert not turn.done()
        assert backend.requests == []
        assert progress.events == (StatusUpdate(state=SWAPPING, detail=HANDOFF_AHEAD_DETAIL),)
        leave.set()
        await ahead
        async with asyncio.timeout(5.0):
            await turn
        assert [request.model for request in backend.requests] == ["cortex"]
    finally:
        await swap_closer(swap)()


class _HandoffAtHistory(InMemorySessionStore):
    """A store whose history read starts another turn's handoff, after the turn's own check."""

    def __init__(self, swap: SwapRuntime) -> None:
        super().__init__()
        self._swap = swap
        self.entered = asyncio.Event()
        self.leave = asyncio.Event()
        self.ahead: asyncio.Task[None] | None = None

    async def _handoff(self) -> None:
        async with self._swap.manager.swap_scope("brain"):
            self.entered.set()
            await self.leave.wait()

    async def history(self, session_id: str) -> Sequence[Message]:
        if self.ahead is None:
            self.ahead = asyncio.create_task(self._handoff())
            await self.entered.wait()
        return await super().history(session_id)


async def test_a_stream_s_reply_announces_a_handoff_that_began_after_the_turn_s_check() -> None:
    backend = _Model({"cortex": [[TextChunk("hi")]]})
    swap = _swap_runtime()
    sessions = _HandoffAtHistory(swap)
    engines = replace(_escalating(backend, swap), sessions=sessions)
    try:
        await _expect_announced_wait(engines, sessions, backend, calls=1)
    finally:
        await swap_closer(swap)()


async def test_a_stream_s_recall_announces_a_handoff_that_began_after_the_turn_s_check() -> None:
    backend = _Model({"cortex": [[TextChunk('{"order": [0]}')], [TextChunk("hi")]]})
    swap = _swap_runtime()
    memories = InMemoryMemoryStore()
    await MemoryRecaller(memories, HashEmbedder(), SystemClock()).record("tea", session_id="s")

    def recaller_for(backend: InferenceBackend, model: str) -> MemoryRecaller:
        judge = JudgeRecallPolicy(backend, model, pool_factor=2)
        return MemoryRecaller(memories, HashEmbedder(), SystemClock(), policy=judge)

    sessions = _HandoffAtHistory(swap)
    engines = replace(_escalating(backend, swap), sessions=sessions, memory=recaller_for)
    try:
        await _expect_announced_wait(engines, sessions, backend, calls=2)
    finally:
        await swap_closer(swap)()


async def _expect_announced_wait(
    engines: StreamEngines, sessions: _HandoffAtHistory, backend: _Model, *, calls: int
) -> None:
    progress = RecordingProgressSink()
    engine = engines.for_stream(RecordingConfirmer(answer=True), progress)
    turn = asyncio.create_task(_run(engine, "hello", turn_id="t2"))
    for _ in range(10):
        await asyncio.sleep(0)
    assert sessions.ahead is not None
    assert not turn.done()
    assert backend.requests == []
    assert progress.events == (StatusUpdate(state=SWAPPING, detail=HANDOFF_AHEAD_DETAIL),)
    sessions.leave.set()
    await sessions.ahead
    async with asyncio.timeout(5.0):
        await turn
    assert [request.model for request in backend.requests] == ["cortex"] * calls


class _Leasing(_Model):
    """A scripted backend that leases each model through the residency manager."""

    def __init__(
        self, script: Mapping[str, Sequence[Sequence[InferenceEvent]]], swap: SwapRuntime
    ) -> None:
        super().__init__(script)
        self._manager = swap.manager

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        """Lease ``model``, then replay its next scripted round."""
        async with self._manager.acquire(model):
            async for event in super().stream(
                model, messages, tools=tools, schema=schema, bounds=bounds
            ):
                yield event


async def _escalate_under_lease(engines: StreamEngines, swap: SwapRuntime) -> list[TurnEvent]:
    engine = engines.for_stream(RecordingConfirmer(answer=True), RecordingProgressSink())
    try:
        async with asyncio.timeout(5.0):
            return await _run(engine, "hello", turn_id="t1")
    finally:
        await swap_closer(swap)()


async def test_the_deep_phase_s_recall_is_judged_by_the_deep_model() -> None:
    swap = _swap_runtime()
    order = [TextChunk('{"order": [0]}')]
    backend = _Leasing(
        {
            "cortex": [order, [_ESCALATE_CALL], [TextChunk("handing off")]],
            "brain": [order, [TextChunk("deep answer")]],
        },
        swap,
    )
    memories = InMemoryMemoryStore()
    await MemoryRecaller(memories, HashEmbedder(), SystemClock()).record("tea", session_id="s")

    def recaller_for(backend: InferenceBackend, model: str) -> MemoryRecaller:
        judge = JudgeRecallPolicy(backend, model, pool_factor=2)
        return MemoryRecaller(memories, HashEmbedder(), SystemClock(), policy=judge)

    events = await _escalate_under_lease(
        replace(_escalating(backend, swap), memory=recaller_for), swap
    )
    assert [request.model for request in backend.requests] == [
        "cortex",
        "cortex",
        "cortex",
        "brain",
        "brain",
    ]
    assert backend.requests[3].tools == ()
    assert any(isinstance(event, TextDelta) and event.text == "deep answer" for event in events)


async def test_the_deep_phase_s_history_recap_is_written_by_the_deep_model() -> None:
    swap = _swap_runtime()
    backend = _Leasing(
        {
            "cortex": [[TextChunk("")], [_ESCALATE_CALL], [TextChunk("handing off")]],
            "brain": [[TextChunk("They talked about x.")], [TextChunk("deep answer")]],
        },
        swap,
    )
    sessions = InMemorySessionStore()
    for index, role in enumerate((Role.USER, Role.ASSISTANT) * 2):
        at = datetime(2026, 9, 24, tzinfo=UTC)
        await sessions.append("s", Message(role=role, text="x" * 300, at=at, turn_id=f"o{index}"))
    runtime = BrainRuntimeConfig(
        history_char_budget=400, history_summary=True, history_recap_min_chars=100
    )
    engines = replace(_escalating(backend, swap), sessions=sessions, runtime=runtime)
    events = await _escalate_under_lease(engines, swap)
    assert [request.model for request in backend.requests] == [
        "cortex",
        "cortex",
        "cortex",
        "brain",
        "brain",
    ]
    assert backend.requests[3].tools == ()
    assert any(isinstance(event, TextDelta) and event.text == "deep answer" for event in events)


async def test_a_stream_whose_cortex_cannot_see_refuses_an_attached_picture_unasked() -> None:
    backend = _Model({"cortex": [[TextChunk("a cat")]]})
    engines = replace(_engines(backend), sight=ScriptedVisionProbe((False,)))
    engine = engines.for_stream(RecordingConfirmer(answer=True), RecordingProgressSink())
    picture = ImagePart(
        data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, mime_type="image/png", width=64, height=48
    )
    with pytest.raises(AttachmentError):
        async for _event in engine.handle_turn("s", "what?", turn_id="t1", images=(picture,)):
            pass
    assert backend.requests == []
    assert await engines.sessions.history("s") == ()
