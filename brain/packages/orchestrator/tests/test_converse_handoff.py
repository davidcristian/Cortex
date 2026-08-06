"""The whole handoff over the real ``Converse`` stream: one turn, two models, one completion.

The core suites prove the sequence and its convergence; this one proves the user-visible shape
ADR-0030 decision 6 fixes, driven end to end in process through the real ``converse()`` with the
real dispatcher, the real confirm gate, the real escalating wrapper, and the real conductor over
the scripted model host. Nothing is stubbed but the two model streams and the process host.

What it pins: the confirm card rides the existing gate; the cortex's wrap-up streams as normal
deltas; the swap's status events ride the same stream; the deep model's answer continues it;
`TurnComplete` fires exactly once at the true end; and a handoff killed mid-swap still ends the
stream honestly and leaves the next turn working.
"""

import asyncio
from collections.abc import AsyncIterator, Sequence

from cortex_core import (
    ESCALATE_TOOL_NAME,
    CompositeToolRegistry,
    Confirmer,
    EscalateToBrainTool,
    EscalatingTurnEngine,
    EscalationSlot,
    GenerationBounds,
    InferenceEvent,
    InMemoryHandoffStore,
    InMemorySessionStore,
    JsonSchema,
    Message,
    ProgressSink,
    RecordingAuditSink,
    RecordingSleeper,
    ResidencyPlan,
    ScriptedModelHost,
    SwapConductor,
    SwappingModelManager,
    SystemClock,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
    TurnRunner,
)
from cortex_core.brain_phase import BrainPhase
from cortex_orchestrator import EngineFactory, ToolsConfig, converse
from cortex_seam import ClientEvent, ConfirmResponse, ServerEvent, UserTurn

_PLAN = ResidencyPlan(cortex_model="cortex", brain_model="brain")
_ENDPOINTS = {"cortex": "http://llama-cortex:8080", "brain": "http://llama-brain:8081"}


class _LiveClient:
    """An interactive client-event iterator: tests push events while consuming output."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[ClientEvent | None] = asyncio.Queue()

    def send(self, event: ClientEvent) -> None:
        self._queue.put_nowait(event)

    def end(self) -> None:
        self._queue.put_nowait(None)

    def __aiter__(self) -> AsyncIterator[ClientEvent]:
        return self

    async def __anext__(self) -> ClientEvent:
        event = await self._queue.get()
        if event is None:
            raise StopAsyncIteration
        return event


class _ScriptedModel:
    """Replays one event list per inference step, per model id."""

    def __init__(self, script: dict[str, Sequence[Sequence[InferenceEvent]]]) -> None:
        self._script = script
        self._calls: dict[str, int] = {}

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del messages, tools, schema, bounds
        step = self._calls.get(model, 0)
        self._calls[model] = step + 1
        for event in self._script[model][step]:
            yield event


def _escalating_factory(
    store: InMemorySessionStore,
    host: ScriptedModelHost,
    backend: _ScriptedModel,
    *,
    turn_id: str = "t-esc",
) -> EngineFactory:
    """The composition root's escalating wiring, in miniature: wrapper + conductor + phase."""
    manager = SwappingModelManager(host, _ENDPOINTS, _PLAN, SystemClock(), RecordingSleeper())
    handoffs = InMemoryHandoffStore()

    def make(confirmer: Confirmer, _progress: ProgressSink) -> TurnRunner:
        dispatcher = ToolDispatcher(
            CompositeToolRegistry([EscalateToBrainTool()]),
            RecordingAuditSink(),
            SystemClock(),
            confirmer=confirmer,
            policy=ToolsConfig().dispatch_policy,
        )
        caps = TurnCapabilities(tools=dispatcher)
        conductor = SwapConductor(
            handoffs,
            manager,
            BrainPhase(store, backend, SystemClock(), "brain", TurnCapabilities()),
            _PLAN,
            SystemClock(),
        )

        def inner(slot: EscalationSlot) -> TurnRunner:
            return TurnEngine(
                store,
                backend,
                SystemClock(),
                capabilities=TurnCapabilities(tools=caps.tools, escalation=slot),
                turn_id_factory=lambda: turn_id,
            )

        return EscalatingTurnEngine(inner, conductor)

    return make


def _script(brain_reply: str = "the deep answer") -> _ScriptedModel:
    return _ScriptedModel(
        {
            "cortex": [
                [ToolCall(id="c1", name=ESCALATE_TOOL_NAME, arguments={"brief": "go deep"})],
                [TextChunk("handing this over. ")],
            ],
            "brain": [[TextChunk(brain_reply)]],
        }
    )


def _user_turn(text: str, session: str = "s") -> ClientEvent:
    return ClientEvent(session_id=session, user_turn=UserTurn(text=text))


def _answer(confirm_id: str, *, approved: bool) -> ClientEvent:
    return ClientEvent(
        session_id="s", confirm_response=ConfirmResponse(confirm_id=confirm_id, approved=approved)
    )


async def _next_of(stream: AsyncIterator[ServerEvent], kind: str) -> ServerEvent:
    """The next event of `kind`; bounded so a missing emit fails the test, not the suite."""
    try:
        async with asyncio.timeout(5.0):
            async for event in stream:
                if event.WhichOneof("event") == kind:
                    return event
    except TimeoutError:
        msg = f"no {kind} event arrived while the stream stayed open"
        raise AssertionError(msg) from None
    msg = f"stream ended before a {kind} event"
    raise AssertionError(msg)


async def _drain(stream: AsyncIterator[ServerEvent]) -> list[ServerEvent]:
    return [event async for event in stream]


def _kinds(events: Sequence[ServerEvent]) -> list[str]:
    return [event.WhichOneof("event") for event in events]


def _reply(events: Sequence[ServerEvent]) -> str:
    return "".join(
        event.text_delta.text for event in events if event.WhichOneof("event") == "text_delta"
    )


async def test_one_turn_carries_the_swap_from_the_cortex_to_the_deep_model() -> None:
    """The user-visible shape: approve, cortex wraps up, swap, deep answer, one completion."""
    store = InMemorySessionStore()
    host = ScriptedModelHost(running=["cortex"])
    client = _LiveClient()
    stream = converse(_escalating_factory(store, host, _script()), client)
    client.send(_user_turn("prove this properly"))
    request = (await _next_of(stream, "confirm_request")).confirm_request
    assert request.tool_name == ESCALATE_TOOL_NAME
    client.send(_answer(request.confirm_id, approved=True))
    client.end()
    events = await _drain(stream)

    assert _reply(events) == "handing this over. the deep answer"
    # Exactly one completion, and it is last: the turn is not over when the cortex stops talking.
    assert _kinds(events).count("turn_complete") == 1
    assert _kinds(events)[-1] == "turn_complete"
    # The swap window reported itself on the same stream the user already held.
    swapping = [e.status for e in events if e.WhichOneof("event") == "status"]
    assert [status.state for status in swapping] == ["swapping"] * len(swapping)
    assert len(swapping) == 4
    # Both models answered under one turn id, and the machine is back on the cortex.
    history = [(m.role.value, m.text, m.turn_id) for m in await store.history("s")]
    assert history == [
        ("user", "prove this properly", "t-esc"),
        ("assistant", "handing this over. ", "t-esc"),
        ("assistant", "the deep answer", "t-esc"),
    ]
    assert host.running == {"cortex"}


async def test_a_second_turn_sent_during_the_swap_runs_after_it() -> None:
    """The stream's own queue is what keeps a mid-handoff turn from failing or interleaving."""
    store = InMemorySessionStore()
    host = ScriptedModelHost(running=["cortex"])
    backend = _ScriptedModel(
        {
            "cortex": [
                [ToolCall(id="c1", name=ESCALATE_TOOL_NAME, arguments={"brief": "go deep"})],
                [TextChunk("handing over. ")],
                [TextChunk("and now the follow-up")],
            ],
            "brain": [[TextChunk("the deep answer")]],
        }
    )
    client = _LiveClient()
    stream = converse(_escalating_factory(store, host, backend), client)
    client.send(_user_turn("prove this properly"))
    request = (await _next_of(stream, "confirm_request")).confirm_request
    client.send(_answer(request.confirm_id, approved=True))
    client.send(_user_turn("and what about the corollary"))  # arrives mid-handoff
    client.end()
    events = await _drain(stream)

    assert _reply(events) == "handing over. the deep answerand now the follow-up"
    assert _kinds(events).count("turn_complete") == 2  # the handoff turn, then the queued one
    assert host.running == {"cortex"}


async def test_a_handoff_killed_mid_swap_ends_the_stream_honestly_and_the_next_turn_works() -> None:
    """The chaos case at the seam: the deep model will not load, and the user is told so."""
    store = InMemorySessionStore()
    host = ScriptedModelHost(running=["cortex"], fail={("start", "brain"): "CUDA OOM at load"})
    backend = _ScriptedModel(
        {
            "cortex": [
                [ToolCall(id="c1", name=ESCALATE_TOOL_NAME, arguments={"brief": "go deep"})],
                [TextChunk("handing this over. ")],
                [TextChunk("carrying on myself")],
            ],
            "brain": [[TextChunk("never reached")]],
        }
    )
    client = _LiveClient()
    stream = converse(_escalating_factory(store, host, backend), client)
    client.send(_user_turn("prove this properly"))
    request = (await _next_of(stream, "confirm_request")).confirm_request
    client.send(_answer(request.confirm_id, approved=True))
    client.send(_user_turn("never mind, tell me what you can"))
    client.end()
    events = await _drain(stream)

    # Honest, not silent: the turn completes with text saying the deep model was not loaded.
    assert "the deep model could not be loaded" in _reply(events).lower()
    assert _kinds(events)[-1] == "turn_complete"
    assert "error" not in _kinds(events)
    # And the stream is still usable: the queued turn ran on the restored cortex.
    assert _reply(events).endswith("carrying on myself")
    assert host.running == {"cortex"}


async def test_a_denied_escalation_leaves_the_turn_exactly_as_it_was() -> None:
    """The gate is the consent surface: a refused card means no record and no swap at all."""
    store = InMemorySessionStore()
    host = ScriptedModelHost(running=["cortex"])
    client = _LiveClient()
    stream = converse(_escalating_factory(store, host, _script()), client)
    client.send(_user_turn("prove this properly"))
    request = (await _next_of(stream, "confirm_request")).confirm_request
    client.send(_answer(request.confirm_id, approved=False))
    client.end()
    events = await _drain(stream)

    assert _reply(events) == "handing this over. "
    assert _kinds(events).count("turn_complete") == 1
    assert host.calls == []  # nothing was ever unloaded
    assert [m.text for m in await store.history("s")] == [
        "prove this properly",
        "handing this over. ",
    ]
