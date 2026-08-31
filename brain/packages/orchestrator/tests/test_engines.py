"""The per-stream engine factory, driven directly rather than through ``run_from_env``.

``StreamEngines`` is what the composition root hands ``serve`` as its ``EngineFactory``, and the
whole reason it is an object is that it runs **again per Converse stream** while everything else
in the root runs once. The suites that drive the real root (``test_wiring``, ``test_swap_wiring``,
``test_vision_wiring``) each open one stream, so none of them can see the property that matters
here: a factory that built its bundle once and answered every stream with it would pass all three
while handing the second stream the first stream's confirmer, which is a gated call prompting the
wrong overlay. The first case below is that pin, and it is the reason this file exists.

The parts are the shipped ones throughout. What is substituted is the world outside the process:
the session store, the model behind the ``InferenceBackend`` port, and the model host a handoff
starts and stops. The dispatchers, the built-in sets, the window, the guardrail, the escalating
wrapper and the conductor are all built by production code from the object under test.

Proof these cases can fail, each mutation applied to ``engines.py`` alone with the 445 tests of
``packages/orchestrator`` re-run over it (2026-08-22):
- caching the bundle, so ``for_stream`` builds it once and hands every later stream that one,
  makes exactly 1 test fail, ``test_each_stream_confirms_through_its_own_overlay``;
- handing the deep phase ``self.builtins`` instead of ``deep.builtins`` makes exactly 2 tests
  fail, ``test_the_deep_model_is_offered_the_tier_set_the_root_built_for_it`` here and
  ``test_the_deep_tier_is_never_offered_the_screen`` in ``test_vision_wiring``;
- dropping ``bounds=self.bounds`` from the bundle makes exactly 1 test fail,
  ``test_the_deployments_reply_bounds_reach_both_phases_of_a_turn``;
- returning the plain engine unconditionally makes 4 tests fail, the three escalating cases here
  and that same ``test_vision_wiring`` one, which is the whole escalating arm and no more.
"""

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

    The two sets are built by the shipped builder from one body, so the only difference between
    them is the one the root makes, which is what the deep-tier case reads back.
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
    """Two streams, two confirmers, and each gated call reaches the one that asked for it.

    The property the object has to keep now that the closures are gone: `for_stream` builds a
    fresh capability bundle per call, so the dispatcher a stream's turns run through holds that
    stream's own confirmer. A cached bundle would send both asks to the first overlay and leave
    the second stream's user watching a call they were never shown, with every end-to-end suite
    green because each of them opens exactly one stream.
    """
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

    This is read at the far end, off what each model was actually offered, because building the
    right two sets and then handing the deep phase the cortex's is the mistake with no other
    symptom: it would advertise `capture_screen` to a model with no projector, spending the whole
    privacy cost of a screen read on a picture nothing can read.
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

    Nothing else in the tree compares the number the composition root read out of the reply
    config with the one a completion is asked under, and the deep phase is the half that would
    be missed: it is handed a bundle the factory rebuilt, not the one the cortex phase used.
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
