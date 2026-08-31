"""The per-stream engine factory, driven directly rather than through ``run_from_env``."""

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, replace

from fakeredis import FakeAsyncRedis, FakeServer

from cortex_core import (
    CAPTURE_SCREEN_TOOL_NAME,
    ESCALATE_TOOL_NAME,
    GET_VOLUME_TOOL_NAME,
    AsyncioSleeper,
    CaptureBounds,
    EscalatingTurnEngine,
    GenerationBounds,
    InferenceEvent,
    InMemoryBodyGateway,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    RecordingConfirmer,
    RecordingProgressSink,
    ScriptedVisionProbe,
    SystemClock,
    TextChunk,
    ToolCall,
    ToolRegistry,
    ToolSpec,
    TurnEngine,
    TurnEvent,
    TurnRunner,
)
from cortex_orchestrator import (
    BrainRuntimeConfig,
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
    """An ``InferenceBackend`` that records every request and replays a script per model id.

    The core's ``ScriptedInferenceBackend`` deliberately reads none of the request, and what the
    cases here assert is the request: which tools a tier was offered and what bound its decode.
    """

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
        policy=ToolsConfig().dispatch_policy,
        sight=None,
        record_tainted_memory=False,
        bounds=None,
        deep=None,
    )


async def _sent(arguments: Mapping[str, object]) -> str:
    """The one remote tool these cases dispatch; gated by the shipped `CORTEX_TOOLS_GATED`."""
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
    """Two streams, two confirmers, and each gated call reaches the one that asked for it."""
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
    """Escalation is off by default, and with it off the factory returns a plain `TurnEngine`."""
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
    """One turn across both tiers: the cortex keeps the screen tool and the tier that swaps in
    is not offered it.
    """
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
    """The bound travels with the capability bundle, so the phase that continues a turn decodes
    under it too.
    """
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
