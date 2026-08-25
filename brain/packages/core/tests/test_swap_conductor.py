import asyncio
import logging
from collections.abc import Mapping, Sequence

import pytest
import swap_harness as harness
from swap_harness import (
    Fakes,
    Gate,
    RecordingHandoffStore,
    ScriptedBrainBackend,
    assert_the_window_announced_real_progress,
    build_harness,
)

from cortex_core import (
    ALREADY_ACTIVE_NOTE,
    BRAIN_FAILED_NOTE,
    BUDGET_EXHAUSTED_MSG,
    CAPTURE_SCREEN_TOOL_NAME,
    DRAIN_TIMEOUT_NOTE,
    DRAIN_TIMEOUT_REASON,
    DRAINING_DETAIL,
    ESCALATE_TOOL_NAME,
    LOADING_DETAIL,
    POOL_DRAINING_MSG,
    RESTORE_FAILED_NOTE,
    RESTORING_DETAIL,
    STORE_FAILED_NOTE,
    SWAP_FAILED_NOTE,
    SWAPPING_STATE,
    UNHOSTED_TIER_NOTE,
    WORKING_DETAIL,
    CaptureScreenTool,
    DispatchBudget,
    EscalateToBrainTool,
    EscalationSlot,
    HandoffState,
    HandoffStoreError,
    InMemoryBodyGateway,
    InMemoryToolRegistry,
    ModelHostState,
    PlainFormatter,
    RecordingAuditSink,
    RecordingConfirmer,
    ScriptedModelHost,
    StatusUpdate,
    SubagentAdmissionError,
    SystemClock,
    TaintLedger,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEvent,
    UrlRedactingGuardrail,
    record_fields,
)
from cortex_core.composite import CompositeToolRegistry
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop


def _texts(events: Sequence[TurnEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TextDelta))


def _states(events: Sequence[TurnEvent]) -> list[str]:
    return [event.detail for event in events if isinstance(event, StatusUpdate)]


def _reading_registry() -> InMemoryToolRegistry:
    """One tool the deep model can spend the turn's remaining budget on."""

    async def handler(arguments: Mapping[str, object]) -> str:
        del arguments
        return "what the tool read"

    return InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="read a thing", parameters={}), handler)}
    )


async def test_a_clean_handoff_walks_the_record_through_its_states() -> None:
    live = build_harness()
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert live.handoffs.states == [
        HandoffState.READY,
        HandoffState.BRAIN_ACTIVE,
        HandoffState.DONE,
    ]
    assert live.handoffs.deleted == [harness.TURN]
    assert await live.handoffs.active() is None
    assert live.host.calls == [
        ("status", "brain"),
        ("boot_id", ""),
        ("stop", "cortex"),
        ("start", "brain"),
        ("status", "brain"),
        ("stop", "brain"),
        ("start", "cortex"),
        ("status", "cortex"),
    ]
    assert live.host.running == {"cortex"}
    assert _texts(events) == "a deep answer"
    assert {event.state for event in events if isinstance(event, StatusUpdate)} == {SWAPPING_STATE}
    assert _states(events) == [DRAINING_DETAIL, LOADING_DETAIL, WORKING_DETAIL, RESTORING_DETAIL]
    assert_the_window_announced_real_progress(live)


async def test_the_deep_model_answers_from_the_store_and_persists_a_second_message() -> None:
    live = build_harness()
    await live.seed_session()
    await harness.run_handoff(live, harness.armed_slot())
    assert live.backend.models == ["brain"]
    seen = [message.text for message in live.backend.seen]
    assert harness.USER_TEXT in seen
    assert harness.CORTEX_TEXT in seen
    history = [
        (message.role.value, message.text)
        for message in await live.sessions.history(harness.SESSION)
    ]
    assert history == [
        ("user", harness.USER_TEXT),
        ("assistant", harness.CORTEX_TEXT),
        ("assistant", "a deep answer"),
    ]


async def test_the_deep_phase_resumes_the_carried_budget_and_taint() -> None:
    spent = DispatchBudget(limit=4)
    assert spent.charge(3) is True
    ledger = TaintLedger()
    ledger.ingest_untrusted("see http://evil.test/x", source=None)
    audit = RecordingAuditSink()
    live = build_harness(
        Fakes(
            backend=ScriptedBrainBackend(
                chunks=("go to http://evil.test/x",),
                tool_calls=(
                    ToolCall(id="c1", name="read", arguments={}),
                    ToolCall(id="c2", name="read", arguments={}),
                ),
            )
        ),
        capabilities=TurnCapabilities(
            tools=ToolDispatcher(_reading_registry(), audit, SystemClock()),
            guardrail=UrlRedactingGuardrail(),
        ),
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot(taint=ledger, budget=spent))
    assert [invocation.ok for invocation in audit.records] == [True, False]
    assert audit.records[-1].detail == BUDGET_EXHAUSTED_MSG
    assert "http://evil.test/x" not in _texts(events)
    assert await live.handoffs.get(harness.TURN) is None


async def test_a_second_concurrent_handoff_is_refused_without_evicting_anything(
    caplog: pytest.LogCaptureFixture,
) -> None:
    live = build_harness()
    await live.seed_session()
    await live.handoffs.put(
        harness.armed_slot().snapshot(
            turn_id="t-other", session_id=harness.SESSION, requested_at=SystemClock().now()
        )
    )
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_conductor"):
        events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == ALREADY_ACTIVE_NOTE
    assert live.host.calls == harness.PREFLIGHT_CALLS
    assert live.backend.calls == 0
    assert [(record.message, record_fields(record)) for record in caplog.records] == [
        (
            "refusing a handoff while the store still has one in flight",
            {
                "active_turn_id": "t-other",
                "session_id": harness.SESSION,
                "turn_id": harness.TURN,
            },
        )
    ]


async def test_a_deployment_whose_host_has_no_deep_tier_is_refused_before_the_drain(
    caplog: pytest.LogCaptureFixture,
) -> None:
    live = build_harness(Fakes(host=ScriptedModelHost(running=["cortex"], unhosted=["brain"])))
    await live.seed_session()
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_conductor"):
        events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == UNHOSTED_TIER_NOTE
    assert _states(events) == []
    assert live.host.calls == harness.PREFLIGHT_CALLS
    assert live.scheduler.drains == 0
    assert live.host.running == {"cortex"}
    assert live.handoffs.states == []
    assert live.backend.calls == 0
    assert "CORTEX_MODEL_FILE_BRAIN" in caplog.text
    assert "CORTEX_ESCALATION" in caplog.text
    assert "model=brain" in " ".join(PlainFormatter().format(r) for r in caplog.records)


async def test_a_host_that_gains_the_deep_tier_stops_refusing_the_handoff() -> None:
    host = ScriptedModelHost(running=["cortex"], unhosted=["brain"])
    live = build_harness(Fakes(host=host))
    await live.seed_session()
    assert _texts(await harness.run_handoff(live, harness.armed_slot())) == UNHOSTED_TIER_NOTE
    host.unhosted.discard("brain")
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "a deep answer"
    assert ("start", "brain") in host.calls
    assert host.running == {"cortex"}


async def test_a_host_that_cannot_be_asked_is_not_read_as_one_with_no_deep_tier(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(running=["cortex"], fail={("status", "brain"): "the socket is gone"})
    live = build_harness(Fakes(host=host))
    await live.seed_session()
    with caplog.at_level(logging.WARNING, logger="cortex_core.residency_moves"):
        events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == SWAP_FAILED_NOTE
    assert ("stop", "cortex") in host.calls
    assert host.running == {"cortex"}
    assert "could not be asked whether it serves" in caplog.text


async def test_a_swap_that_finds_the_gpu_already_handed_over_says_so_and_not_that_it_broke() -> (
    None
):
    live = build_harness()
    await live.seed_session()
    async with live.manager.swap_scope(live.residency.brain_model):
        assert live.host.running == {"brain"}
        events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == ALREADY_ACTIVE_NOTE
    assert live.handoffs.states == [HandoffState.READY, HandoffState.FAILED]
    assert live.backend.calls == 0
    assert live.host.calls.count(("start", "brain")) == 1
    assert live.host.running == {"cortex"}


async def test_a_handoff_store_that_cannot_record_the_snapshot_changes_nothing() -> None:
    live = build_harness(
        Fakes(handoffs=RecordingHandoffStore(fail=HandoffStoreError("redis is gone")))
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == STORE_FAILED_NOTE
    assert live.host.calls == harness.PREFLIGHT_CALLS
    assert live.backend.calls == 0


async def test_a_handoff_store_that_cannot_be_read_refuses_the_handoff_the_same_way() -> None:
    class _Unreadable(RecordingHandoffStore):
        async def active(self) -> None:
            msg = "redis is gone"
            raise HandoffStoreError(msg)

    live = build_harness(Fakes(handoffs=_Unreadable()))
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == STORE_FAILED_NOTE
    assert live.host.calls == harness.PREFLIGHT_CALLS
    assert live.handoffs.states == []


async def test_a_drain_that_times_out_aborts_before_anything_is_evicted() -> None:
    live = build_harness(residency=harness.plan(drain_timeout_s=0.0))
    await live.seed_session()
    held = asyncio.Event()
    release = asyncio.Event()

    async def in_flight() -> None:
        async with live.scheduler.admit(harness.request()):
            held.set()
            await release.wait()

    task = asyncio.create_task(in_flight())
    async with asyncio.timeout(5.0):
        await held.wait()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == DRAIN_TIMEOUT_NOTE
    assert live.host.calls == harness.PREFLIGHT_CALLS
    assert live.handoffs.states == [HandoffState.READY, HandoffState.FAILED]
    aborted = await live.handoffs.get(harness.TURN)
    assert aborted is not None
    assert aborted.failure == DRAIN_TIMEOUT_REASON
    assert not task.done()
    release.set()
    await task
    async with live.scheduler.admit(harness.request()):
        pass


async def test_a_deployment_without_a_subagent_pool_has_nothing_to_drain() -> None:
    live = build_harness(with_scheduler=False)
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "a deep answer"
    assert live.handoffs.states[-1] is HandoffState.DONE
    assert _states(events) == [DRAINING_DETAIL, LOADING_DETAIL, WORKING_DETAIL, RESTORING_DETAIL]
    assert_the_window_announced_real_progress(live)


async def test_a_deep_model_that_will_not_load_ends_the_turn_honestly() -> None:
    live = build_harness(
        Fakes(host=ScriptedModelHost(running=["cortex"], fail={("start", "brain"): "CUDA OOM"}))
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == SWAP_FAILED_NOTE
    assert live.host.running == {"cortex"}
    assert live.handoffs.states == [HandoffState.READY, HandoffState.FAILED]
    assert live.backend.calls == 0


@pytest.mark.parametrize(
    ("failing_call", "sentence"),
    [
        (("stop", "cortex"), "the child is wedged and will not reap"),
        (("start", "brain"), "CUDA OOM at load"),
    ],
)
async def test_a_swap_that_broke_writes_the_model_hosts_own_sentence_down(
    failing_call: tuple[str, str], sentence: str, caplog: pytest.LogCaptureFixture
) -> None:
    host = ScriptedModelHost(running=["cortex"], fail={failing_call: sentence})
    live = build_harness(Fakes(host=host))
    await live.seed_session()
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_settle"):
        events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == SWAP_FAILED_NOTE
    settled = await live.handoffs.get(harness.TURN)
    assert settled is not None
    assert settled.state is HandoffState.FAILED
    assert settled.failure is not None
    assert sentence in settled.failure
    assert "swapping in 'brain'" in settled.failure
    logged = [
        record for record in caplog.records if record.getMessage() == "a handoff ended failed"
    ]
    assert [record_fields(entry) for entry in logged] == [
        {"session_id": harness.SESSION, "turn_id": harness.TURN, "reason": settled.failure}
    ]


async def test_a_deep_model_that_never_becomes_ready_ends_the_turn_honestly() -> None:
    live = build_harness(
        Fakes(
            host=ScriptedModelHost(
                running=["cortex"], status_override={"brain": ModelHostState.LOADING}
            )
        ),
        residency=harness.plan(load_timeout_s=0.0),
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == SWAP_FAILED_NOTE
    assert live.host.running == {"cortex"}


async def test_a_deep_model_that_dies_mid_answer_keeps_its_partial_text_with_a_note() -> None:
    live = build_harness(
        Fakes(backend=ScriptedBrainBackend(chunks=("half an ", "never streamed"), fail_after=1))
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "half an " + BRAIN_FAILED_NOTE
    persisted = [message.text for message in await live.sessions.history(harness.SESSION)]
    assert persisted[-1] == "half an " + BRAIN_FAILED_NOTE
    assert live.handoffs.states == [
        HandoffState.READY,
        HandoffState.BRAIN_ACTIVE,
        HandoffState.FAILED,
    ]
    died = await live.handoffs.get(harness.TURN)
    assert died is not None
    assert died.failure == "the deep model's server died mid-stream"
    assert live.host.running == {"cortex"}


async def test_a_cortex_that_cannot_be_restored_says_so_on_the_stream() -> None:
    live = build_harness(
        Fakes(
            host=ScriptedModelHost(running=["cortex"], fail={("start", "cortex"): "no such device"})
        )
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "a deep answer" + RESTORE_FAILED_NOTE
    assert live.handoffs.states[-1] is HandoffState.FAILED
    assert live.host.calls.count(("start", "cortex")) == 2
    gave_up = await live.handoffs.get(harness.TURN)
    assert gave_up is not None
    assert gave_up.failure is not None
    assert "could not restore 'cortex'" in gave_up.failure


class _FailsLate(RecordingHandoffStore):
    """A store that fails after the snapshot: every state written from then on is refused."""

    async def transition(
        self, handoff_id: str, state: HandoffState, *, failure: str | None = None
    ) -> bool:
        del handoff_id, state, failure
        msg = "redis went away mid-handoff"
        raise HandoffStoreError(msg)


async def test_a_store_that_fails_while_settling_the_record_does_not_fail_the_turn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    live = build_harness(Fakes(handoffs=_FailsLate()))
    await live.seed_session()
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_conductor"):
        events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "a deep answer"
    assert live.host.running == {"cortex"}
    assert [record.message for record in caplog.records] == [
        "could not record the handoff's state",
        "could not record the handoff's state",
    ]
    assert live.handoffs.deleted == [harness.TURN]
    assert await live.handoffs.active() is None


async def test_the_reason_reaches_the_log_even_when_the_store_cannot_keep_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    live = build_harness(
        Fakes(
            handoffs=_FailsLate(),
            host=ScriptedModelHost(running=["cortex"], fail={("start", "brain"): "CUDA OOM"}),
        )
    )
    await live.seed_session()
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_settle"):
        events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == SWAP_FAILED_NOTE
    assert await live.handoffs.get(harness.TURN) is None
    logged = [
        record for record in caplog.records if record.getMessage() == "a handoff ended failed"
    ]
    assert len(logged) == 1
    assert "CUDA OOM" in str(record_fields(logged[0])["reason"])


async def test_a_store_that_cannot_even_drop_the_record_says_what_is_now_stuck(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _AlsoRefusesTheDelete(_FailsLate):
        async def delete(self, handoff_id: str) -> None:
            del handoff_id
            msg = "redis is still gone"
            raise HandoffStoreError(msg)

    live = build_harness(Fakes(handoffs=_AlsoRefusesTheDelete()))
    await live.seed_session()
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_conductor"):
        events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "a deep answer"
    assert live.host.running == {"cortex"}
    assert [record.message for record in caplog.records][-1] == (
        "could not release the finished handoff; escalation stays refused until a restart"
    )


async def test_a_turn_that_looked_at_the_screen_after_escalating_ends_with_a_note() -> None:
    audit = RecordingAuditSink()
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([EscalateToBrainTool(), CaptureScreenTool(InMemoryBodyGateway())]),
        audit,
        SystemClock(),
        confirmer=RecordingConfirmer(answer=True),
    )
    slot = harness.armed_slot(brief=None)
    assert slot.refs is not None
    working = slot.refs.working
    cortex = ScriptedBrainBackend(
        chunks=("handing this over",),
        tool_calls=(
            ToolCall(id="c1", name=ESCALATE_TOOL_NAME, arguments={"brief": harness.BRIEF}),
            ToolCall(id="c2", name=CAPTURE_SCREEN_TOOL_NAME, arguments={"target": "display"}),
        ),
    )
    context = ToolLoopContext(
        dispatcher=dispatcher,
        clock=SystemClock(),
        turn_id=harness.TURN,
        taint=slot.refs.taint,
        nonce=slot.refs.nonce,
        session_id=harness.SESSION,
        escalation=slot,
    )
    async for _delta in stream_tool_loop(cortex, "cortex", working, context):
        pass

    assert slot.brief == harness.BRIEF, "the escalation really was queued before the capture"
    assert [line.name for line in audit.records] == [ESCALATE_TOOL_NAME, CAPTURE_SCREEN_TOOL_NAME]
    assert [len(message.images) for message in working[slot.refs.base_len :]].count(1) == 1

    live = build_harness()
    await live.seed_session()
    events = await harness.run_handoff(live, slot)

    assert _texts(events) == (
        "\n\n(This turn looked at your screen, and a picture cannot be handed to the deep model, "
        "so the handoff was not started. Nothing was unloaded. Ask again in a new message if you "
        "still want the deep model.)"
    )
    assert _states(events) == [], "nothing was announced, because nothing was done"
    assert live.handoffs.states == []
    assert live.host.calls == []
    assert live.backend.calls == 0
    assert live.handoffs.states == []


async def test_the_deep_phase_cannot_escalate_to_itself() -> None:
    audit = RecordingAuditSink()
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([EscalateToBrainTool()], remote=InMemoryToolRegistry({})),
        audit,
        SystemClock(),
        confirmer=RecordingConfirmer(answer=True),
    )
    stowaway = EscalationSlot()
    live = build_harness(
        Fakes(
            backend=ScriptedBrainBackend(
                chunks=("thinking",),
                tool_calls=(
                    ToolCall(
                        id="c1", name=ESCALATE_TOOL_NAME, arguments={"brief": "go deeper still"}
                    ),
                ),
            )
        ),
        capabilities=TurnCapabilities(tools=dispatcher, escalation=stowaway),
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    (invocation,) = audit.records
    assert invocation.ok is False
    assert "escalation is not available for this turn" in invocation.detail
    assert stowaway.brief is None
    assert _texts(events) == "thinking"


def _coresident_harness(gate: Gate, *, coresident: bool) -> harness.Harness:
    """The one setting this pair of tests differs on; everything else is identical."""
    return build_harness(
        Fakes(
            host=ScriptedModelHost(running=["cortex", "subagent-gpu"]),
            backend=ScriptedBrainBackend(gate=gate, gate_after=1),
        ),
        residency=harness.plan(evict_models=("subagent-gpu",), coresident=coresident),
    )


async def _paused_mid_phase(live: harness.Harness, gate: Gate) -> asyncio.Task[list[TurnEvent]]:
    """Run a handoff until the deep model's stream is in progress, and hold it there."""
    task = asyncio.create_task(harness.run_handoff(live, harness.armed_slot()))
    await gate.arrived()
    return task


async def test_a_coresident_handoff_keeps_its_peers_and_keeps_delegating() -> None:
    gate = Gate()
    live = _coresident_harness(gate, coresident=True)
    await live.seed_session()
    task = await _paused_mid_phase(live, gate)
    assert live.host.running == {"brain", "subagent-gpu"}
    async with live.scheduler.admit(harness.request()):
        pass
    gate.release.set()
    events = await task
    assert live.scheduler.drains == 0
    assert ("stop", "subagent-gpu") not in live.host.calls
    assert live.handoffs.states[-1] is HandoffState.DONE
    assert _texts(events) == "a deep answer"


async def test_the_shipped_default_still_evicts_its_peers_and_refuses_a_spawn() -> None:
    gate = Gate()
    live = _coresident_harness(gate, coresident=False)
    await live.seed_session()
    task = await _paused_mid_phase(live, gate)
    assert live.host.running == {"brain"}
    with pytest.raises(SubagentAdmissionError, match=POOL_DRAINING_MSG):
        async with live.scheduler.admit(harness.request()):
            pass  # pragma: no cover - admit raises before the block is ever entered
    gate.release.set()
    await task
    assert live.scheduler.drains == 1
    assert ("stop", "subagent-gpu") in live.host.calls
    assert live.host.running == {"cortex", "subagent-gpu"}


async def test_a_coresident_handoff_does_not_announce_a_drain_it_never_performs() -> None:
    live = build_harness(residency=harness.plan(coresident=True))
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "a deep answer"
    assert _states(events) == [LOADING_DETAIL, WORKING_DETAIL, RESTORING_DETAIL]
    assert live.scheduler.drains == 0
