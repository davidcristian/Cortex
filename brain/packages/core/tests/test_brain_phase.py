import logging
import re
from collections.abc import AsyncGenerator, Mapping, Sequence
from datetime import UTC, datetime

import pytest
import swap_harness as harness
from swap_harness import ScriptedBrainBackend, TickingClock

from cortex_core import (
    BRAIN_FAILED_NOTE,
    BUDGET_EXHAUSTED_MSG,
    NO_CADENCE_TERMS,
    REDACTED,
    REPLY_CAPPED_NOTE,
    UNREADABLE_CALL_NOTE,
    CadenceTerms,
    DecodeCadence,
    DecodeStop,
    DispatchBudget,
    GenerationBounds,
    ImagePart,
    InferenceError,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    MalformedToolCallError,
    Message,
    PlainFormatter,
    RecordingAuditSink,
    RecordingPaceSink,
    Role,
    SourceKind,
    StopReason,
    SystemClock,
    TaintLedger,
    TextChunk,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    TurnCapabilities,
    TurnEvent,
    UrlRedactingGuardrail,
    as_source,
    wrap_untrusted,
)
from cortex_core.brain_phase import SPILLED_LOG_MSG, BrainPhase
from cortex_core.memory import MemoryRecord
from cortex_core.recall import MemoryRecaller

_AT = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


async def _collect(events: AsyncGenerator[TurnEvent, None], into: list[str]) -> None:
    """Collect a phase's events into ``into``, letting whatever it raises propagate."""
    async for event in events:
        if isinstance(event, TextDelta):
            into.append(event.text)  # noqa: PERF401 - a live stream, read one event at a time


async def _drive(
    *,
    capabilities: TurnCapabilities | None = None,
    backend: ScriptedBrainBackend | None = None,
    tail: Sequence[Message] = (),
    taint: TaintLedger | None = None,
    store: InMemorySessionStore | None = None,
    cadence: CadenceTerms = NO_CADENCE_TERMS,
) -> tuple[BrainPhase, ScriptedBrainBackend, InMemorySessionStore, list[str]]:
    """Run one deep phase over a prepared session, returning what it saw and what it streamed."""
    sessions = store if store is not None else InMemorySessionStore()
    if store is None:
        await sessions.append(
            harness.SESSION,
            Message(role=Role.USER, text=harness.USER_TEXT, at=_AT, turn_id=harness.TURN),
        )
        await sessions.append(
            harness.SESSION,
            Message(role=Role.ASSISTANT, text=harness.CORTEX_TEXT, at=_AT, turn_id=harness.TURN),
        )
    used_backend = backend if backend is not None else ScriptedBrainBackend()
    phase = BrainPhase(
        sessions,
        used_backend,
        TickingClock(),
        "brain",
        capabilities if capabilities is not None else TurnCapabilities(),
        cadence,
    )
    slot = harness.armed_slot(tail=tail, taint=taint)
    record = slot.snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    texts: list[str] = []
    events = phase.run(record)
    try:
        await _collect(events, texts)
    finally:
        await events.aclose()
    return phase, used_backend, sessions, texts


async def test_the_deep_model_sees_the_history_and_the_tool_loop_tail_it_never_persisted() -> None:
    tail = (
        Message(
            role=Role.ASSISTANT,
            text="",
            at=_AT,
            turn_id=harness.TURN,
            tool_calls=(ToolCall(id="c1", name="escalate_to_brain", arguments={"brief": "go"}),),
        ),
        Message(role=Role.TOOL, text="queued", at=_AT, turn_id=harness.TURN, tool_call_id="c1"),
    )
    _phase, backend, _sessions, _deltas = await _drive(tail=tail)
    seen = [(message.role, message.text) for message in backend.seen]
    assert (Role.USER, harness.USER_TEXT) in seen
    assert (Role.ASSISTANT, harness.CORTEX_TEXT) in seen
    assert [message.role for message in backend.seen[-2:]] == [Role.ASSISTANT, Role.TOOL]
    assert backend.seen[-2].tool_calls[0].arguments == {"brief": "go"}


async def test_a_tainted_turn_stays_tainted_and_keeps_its_laundering_evidence() -> None:
    ledger = TaintLedger()
    ledger.ingest_untrusted(
        "read http://evil.test/x", source=as_source(SourceKind.TOOL, "read_page")
    )
    backend = ScriptedBrainBackend(chunks=("visit http://evil.test/x now",))
    _phase, _backend, _sessions, texts = await _drive(
        backend=backend,
        taint=ledger,
        capabilities=TurnCapabilities(guardrail=UrlRedactingGuardrail()),
    )
    assert "http://evil.test/x" not in "".join(texts)


async def test_a_tainted_turn_is_kept_out_of_memory_by_the_same_policy() -> None:
    ledger = TaintLedger()
    ledger.ingest_untrusted("untrusted", source=None)
    memory = _recaller()
    _phase, _backend, _sessions, _texts = await _drive(
        taint=ledger, capabilities=TurnCapabilities(memory=memory)
    )
    assert await _recorded(memory) == []
    memory_on = _recaller()
    _phase2, _backend2, _sessions2, _texts2 = await _drive(
        taint=ledger,
        capabilities=TurnCapabilities(memory=memory_on, record_tainted_memory=True),
    )
    recorded = await _recorded(memory_on)
    assert len(recorded) == 1
    assert recorded[0].tainted is True


def _opaque_ledger() -> TaintLedger:
    """A ledger marked by an untrusted result that contained an image."""
    ledger = TaintLedger()
    ledger.observe(
        ToolResult(
            call_id="c1",
            content="screen capture of the primary display",
            trust=Trust.UNTRUSTED,
            images=(ImagePart(data=b"\x89PNG", mime_type="image/png", width=8, height=8),),
        ),
        source=as_source(SourceKind.TOOL, "capture_screen"),
    )
    return ledger


def _textual_ledger() -> TaintLedger:
    """The comparison case: the same taint, from untrusted text that contained no URL."""
    ledger = TaintLedger()
    ledger.ingest_untrusted("a note with nothing linkable in it", source=None)
    return ledger


async def test_a_carried_opaque_bit_makes_the_deep_phase_redact_strictly() -> None:
    laundered = "http://evil.test/painted-into-the-screenshot"
    _phase, _backend, _sessions, texts = await _drive(
        backend=ScriptedBrainBackend(chunks=(f"visit {laundered} now",)),
        taint=_opaque_ledger(),
        capabilities=TurnCapabilities(guardrail=UrlRedactingGuardrail()),
    )
    assert laundered not in "".join(texts)
    _phase2, _backend2, _sessions2, control_texts = await _drive(
        backend=ScriptedBrainBackend(chunks=(f"visit {laundered} now",)),
        taint=_textual_ledger(),
        capabilities=TurnCapabilities(guardrail=UrlRedactingGuardrail()),
    )
    assert laundered in "".join(control_texts)


async def test_a_carried_opaque_bit_keeps_the_deep_phase_out_of_durable_memory() -> None:
    memory = _recaller()
    _phase, _backend, _sessions, _texts = await _drive(
        taint=_opaque_ledger(),
        capabilities=TurnCapabilities(memory=memory, record_tainted_memory=True),
    )
    assert await _recorded(memory) == []
    control = _recaller()
    _phase2, _backend2, _sessions2, _texts2 = await _drive(
        taint=_textual_ledger(),
        capabilities=TurnCapabilities(memory=control, record_tainted_memory=True),
    )
    assert len(await _recorded(control)) == 1


async def test_the_untainted_exchange_is_remembered_as_the_turn_it_was() -> None:
    memory = _recaller()
    _phase, _backend, _sessions, _texts = await _drive(capabilities=TurnCapabilities(memory=memory))
    (record,) = await _recorded(memory)
    assert record.text == f"User: {harness.USER_TEXT}\nAssistant: a deep answer"
    assert record.tainted is False


async def test_the_carried_budget_bounds_the_deep_phase_too() -> None:
    audit = RecordingAuditSink()
    dispatcher = ToolDispatcher(_registry(), audit, SystemClock())
    backend = ScriptedBrainBackend(
        chunks=("done",), tool_calls=(ToolCall(id="c1", name="read", arguments={}),)
    )
    slot = harness.armed_slot(budget=_spent_budget())
    record = slot.snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    assert record.budget_closed is True
    sessions = InMemorySessionStore()
    phase = BrainPhase(
        sessions, backend, TickingClock(), "brain", TurnCapabilities(tools=dispatcher)
    )
    events = phase.run(record)
    try:
        async for _event in events:
            pass
    finally:
        await events.aclose()
    (invocation,) = audit.records
    assert invocation.ok is False
    assert invocation.detail == BUDGET_EXHAUSTED_MSG


async def test_the_deep_phases_dispatches_are_audited_under_the_turn_that_escalated() -> None:
    audit = RecordingAuditSink()
    dispatcher = ToolDispatcher(_registry(), audit, SystemClock())
    backend = ScriptedBrainBackend(
        chunks=("done",), tool_calls=(ToolCall(id="c1", name="read", arguments={}),)
    )
    await _drive(capabilities=TurnCapabilities(tools=dispatcher), backend=backend)
    (invocation,) = audit.records
    assert (invocation.session_id, invocation.turn_id) == (harness.SESSION, harness.TURN)
    assert invocation.task_id == ""


async def test_the_query_is_recovered_from_the_store_for_recall_and_memory() -> None:
    memory = _recaller()
    _phase, _backend, _sessions, _texts = await _drive(capabilities=TurnCapabilities(memory=memory))
    (recorded,) = await _recorded(memory)
    assert recorded.text.startswith(f"User: {harness.USER_TEXT}")


async def test_a_session_deleted_mid_handoff_falls_back_to_the_brief() -> None:
    memory = _recaller()
    empty = InMemorySessionStore()
    _phase, _backend, _sessions, _texts = await _drive(
        store=empty, capabilities=TurnCapabilities(memory=memory)
    )
    (recorded,) = await _recorded(memory)
    assert recorded.text.startswith(f"User: {harness.BRIEF}")


async def test_a_deep_model_that_dies_releases_what_the_guardrail_still_held() -> None:
    backend = ScriptedBrainBackend(chunks=("see http://exa", "never streamed"), fail_after=1)
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION,
        Message(role=Role.USER, text=harness.USER_TEXT, at=_AT, turn_id=harness.TURN),
    )
    phase = BrainPhase(
        sessions,
        backend,
        TickingClock(),
        "brain",
        TurnCapabilities(guardrail=UrlRedactingGuardrail()),
    )
    record = harness.armed_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    events = phase.run(record)
    collected: list[str] = []
    with pytest.raises(InferenceError):
        await _collect(events, collected)
    await events.aclose()
    assert "".join(collected) == "see http://exa" + BRAIN_FAILED_NOTE
    persisted = [message.text for message in await sessions.history(harness.SESSION)]
    assert persisted[-1] == "see http://exa" + BRAIN_FAILED_NOTE


async def test_a_deep_model_that_dies_persists_its_partial_text_with_the_note() -> None:
    backend = ScriptedBrainBackend(chunks=("half an ", "never streamed"), fail_after=1)
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION,
        Message(role=Role.USER, text=harness.USER_TEXT, at=_AT, turn_id=harness.TURN),
    )
    phase = BrainPhase(sessions, backend, TickingClock(), "brain", TurnCapabilities())
    slot = harness.armed_slot()
    record = slot.snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    events = phase.run(record)
    collected: list[str] = []
    with pytest.raises(InferenceError, match="died mid-stream"):
        await _collect(events, collected)
    await events.aclose()
    assert "".join(collected) == "half an " + BRAIN_FAILED_NOTE
    persisted = [message.text for message in await sessions.history(harness.SESSION)]
    assert persisted[-1] == "half an " + BRAIN_FAILED_NOTE


async def test_the_deep_phase_fences_under_the_record_s_own_nonce() -> None:
    before = wrap_untrusted("whatever the cortex read", nonce=harness.NONCE)
    tail = (
        Message(
            role=Role.ASSISTANT,
            text="",
            at=_AT,
            turn_id=harness.TURN,
            tool_calls=(ToolCall(id="c0", name="read", arguments={}),),
        ),
        Message(role=Role.TOOL, text=before, at=_AT, turn_id=harness.TURN, tool_call_id="c0"),
    )
    backend = ScriptedBrainBackend(
        chunks=("done",), tool_calls=(ToolCall(id="c1", name="read", arguments={}),)
    )
    _phase, _backend, _sessions, _texts = await _drive(
        backend=backend,
        tail=tail,
        capabilities=TurnCapabilities(
            tools=ToolDispatcher(_registry(), RecordingAuditSink(), SystemClock())
        ),
    )
    fenced = [message.text for message in backend.seen if message.role is Role.TOOL]
    assert len(fenced) == 2
    assert set(re.findall(r"id=([0-9a-f]+)>", "".join(fenced))) == {harness.NONCE}


async def test_closing_the_deep_phase_mid_stream_tears_its_loop_down() -> None:
    backend = ScriptedBrainBackend(chunks=("first ", "second"))
    sessions = InMemorySessionStore()
    phase = BrainPhase(sessions, backend, TickingClock(), "brain", TurnCapabilities())
    record = harness.armed_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    events = phase.run(record)
    assert await anext(events) == TextDelta(text="first ")
    await events.aclose()
    assert backend.closed is True
    assert list(await sessions.history(harness.SESSION)) == []


def _spent_budget() -> DispatchBudget:
    budget = DispatchBudget(limit=1)
    assert budget.charge(2) is False
    return budget


def _registry() -> InMemoryToolRegistry:
    async def handler(arguments: Mapping[str, object]) -> str:
        del arguments
        return "ok"

    return InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="read a thing", parameters={}), handler)}
    )


def _recaller() -> MemoryRecaller:
    return MemoryRecaller(
        InMemoryMemoryStore(), _Embedder(), SystemClock(), id_factory=lambda: "m1"
    )


async def _recorded(recaller: MemoryRecaller) -> list[MemoryRecord]:
    hits = await recaller.recall("anything", k=5, session_id=harness.SESSION, turn_id="t")
    return [hit.record for hit in hits]


class _Embedder:
    async def embed(self, text: str) -> Sequence[float]:
        del text
        return (1.0, 0.0)


def _cadence_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Only this phase's own cadence lines, in order."""
    return [record for record in caplog.records if "decode" in record.getMessage()]


def _extra(record: logging.LogRecord, field: str) -> object:
    """One structured field of a log record, which ``extra=`` puts in the record's ``__dict__``."""
    return record.__dict__[field]


async def test_a_deep_phase_under_the_declared_floor_warns_once_naming_both_numbers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cortex_core.brain_phase")
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=17.29, tokens=96)])
    await _drive(backend=backend, cadence=CadenceTerms(22.0))
    records = _cadence_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert _extra(records[0], "decode_rate") == 17.29  # pyright: ignore[reportAttributeAccessIssue]
    assert _extra(records[0], "floor_rate") == 22.0  # pyright: ignore[reportAttributeAccessIssue]
    assert _extra(records[0], "turn_id") == harness.TURN  # pyright: ignore[reportAttributeAccessIssue]
    assert _extra(records[0], "session_id") == harness.SESSION  # pyright: ignore[reportAttributeAccessIssue]
    assert records[0].getMessage() == SPILLED_LOG_MSG


async def test_a_deep_phase_that_cleared_its_floor_says_so_without_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cortex_core.brain_phase")
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=30.4, tokens=96)])
    await _drive(backend=backend, cadence=CadenceTerms(22.0))
    records = _cadence_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert _extra(records[0], "decode_rate") == 30.4  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize(
    ("rate", "shown"),
    [
        (17.29, "decode_rate=17.29 decoded=96 floor_rate=22.0 "),
        (30.4, "decode_rate=30.4 decoded=96 floor_rate=22.0 "),
    ],
    ids=["under the floor", "at or above it"],
)
async def test_both_rate_lines_print_their_numbers_through_the_formatter(
    caplog: pytest.LogCaptureFixture, rate: float, shown: str
) -> None:
    caplog.set_level(logging.INFO, logger="cortex_core.brain_phase")
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=rate, tokens=96)])
    await _drive(backend=backend, cadence=CadenceTerms(22.0))
    (record,) = _cadence_records(caplog)
    line = PlainFormatter().format(record)
    assert shown in line
    assert REDACTED not in line


async def test_a_deployment_that_declared_no_floor_still_gets_its_number(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cortex_core.brain_phase")
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=3.0, tokens=96)])
    await _drive(backend=backend)
    records = _cadence_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.INFO


async def test_a_backend_that_reports_no_timings_is_not_reported_as_healthy(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cortex_core.brain_phase")
    await _drive(backend=ScriptedBrainBackend(), cadence=CadenceTerms(22.0))
    records = _cadence_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert "nothing was checked" in records[0].getMessage()
    assert _extra(records[0], "turn_id") == harness.TURN  # pyright: ignore[reportAttributeAccessIssue]
    assert _extra(records[0], "session_id") == harness.SESSION  # pyright: ignore[reportAttributeAccessIssue]


async def test_one_slow_round_of_a_tool_loop_does_not_convict_the_tier(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cortex_core.brain_phase")
    dispatcher = ToolDispatcher(_registry(), RecordingAuditSink(), SystemClock())
    backend = ScriptedBrainBackend(
        tool_calls=(ToolCall(id="c1", name="read", arguments={}),),
        cadences=[
            DecodeCadence(tokens_per_second=8.0, tokens=96),
            DecodeCadence(tokens_per_second=29.0, tokens=96),
        ],
    )
    await _drive(
        capabilities=TurnCapabilities(tools=dispatcher),
        backend=backend,
        cadence=CadenceTerms(22.0),
    )
    records = _cadence_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert _extra(records[0], "samples") == 2  # pyright: ignore[reportAttributeAccessIssue]
    assert _extra(records[0], "decode_rate") == 29.0  # pyright: ignore[reportAttributeAccessIssue]


async def test_a_failed_phase_still_reports_what_it_managed_to_observe(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cortex_core.brain_phase")
    backend = ScriptedBrainBackend(fail_after=1)
    with pytest.raises(InferenceError):
        await _drive(backend=backend, cadence=CadenceTerms(22.0))
    assert len(_cadence_records(caplog)) == 1


async def test_the_cadence_never_reaches_the_turns_own_stream() -> None:
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=17.29, tokens=96)])
    _phase, _backend, _sessions, deltas = await _drive(backend=backend, cadence=CadenceTerms(22.0))
    assert "".join(deltas) == "a deep answer"


async def test_a_spilled_handoff_is_published_and_not_only_logged() -> None:
    sink = RecordingPaceSink()
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=17.29, tokens=96)])
    await _drive(backend=backend, cadence=CadenceTerms(22.0, sink))
    assert list(sink.verdicts) == [True]


async def test_a_handoff_that_held_its_pace_publishes_that_too() -> None:
    sink = RecordingPaceSink()
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=30.4, tokens=96)])
    await _drive(backend=backend, cadence=CadenceTerms(22.0, sink))
    assert list(sink.verdicts) == [False]


async def test_a_deployment_that_declared_no_floor_publishes_no_verdict() -> None:
    sink = RecordingPaceSink()
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=3.0, tokens=96)])
    await _drive(backend=backend, cadence=CadenceTerms(sink=sink))
    assert list(sink.verdicts) == []


async def test_a_handoff_with_no_reading_publishes_nothing_at_all() -> None:
    sink = RecordingPaceSink()
    await _drive(backend=ScriptedBrainBackend(), cadence=CadenceTerms(22.0, sink))
    assert list(sink.verdicts) == []


async def test_a_failed_phase_still_publishes_the_verdict_it_managed_to_reach() -> None:
    sink = RecordingPaceSink()
    dispatcher = ToolDispatcher(_registry(), RecordingAuditSink(), SystemClock())
    backend = ScriptedBrainBackend(
        tool_calls=(ToolCall(id="c1", name="read", arguments={}),),
        cadences=[DecodeCadence(tokens_per_second=17.29, tokens=96)],
        fail_after=1,
    )
    with pytest.raises(InferenceError):
        await _drive(
            capabilities=TurnCapabilities(tools=dispatcher),
            backend=backend,
            cadence=CadenceTerms(22.0, sink),
        )
    assert list(sink.verdicts) == [True]


class StoppingDeepBackend:
    """A deep-model stream that reports why it stopped, and optionally fails afterwards."""

    def __init__(
        self,
        reason: StopReason,
        *,
        fail: bool = False,
        cut: bool = False,
        chunks: Sequence[str] = ("a deep ", "stump"),
    ) -> None:
        self._reason = reason
        self._fail = fail
        self._cut = cut
        self._chunks = chunks
        self.bounds: list[GenerationBounds | None] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncGenerator[InferenceEvent, None]:
        del model, messages, tools, schema
        self.bounds.append(bounds)
        for chunk in self._chunks:
            yield TextChunk(chunk)
        yield DecodeStop(self._reason)
        if self._fail:
            msg = "the deep server died after reporting its stop"
            raise InferenceError(msg)
        if self._cut:
            msg = "the tool call arguments are not JSON"
            raise MalformedToolCallError(msg)


async def _run_deep(
    backend: StoppingDeepBackend,
    bounds: GenerationBounds | None = None,
    guardrail: UrlRedactingGuardrail | None = None,
) -> tuple[list[str], InMemorySessionStore]:
    """Run one deep phase over a prepared session, returning its text and the store."""
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION,
        Message(role=Role.USER, text=harness.USER_TEXT, at=_AT, turn_id=harness.TURN),
    )
    phase = BrainPhase(
        sessions,
        backend,
        TickingClock(),
        "brain",
        TurnCapabilities(bounds=bounds, guardrail=guardrail),
    )
    record = harness.armed_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    texts: list[str] = []
    events = phase.run(record)
    try:
        await _collect(events, texts)
    finally:
        await events.aclose()
    return texts, sessions


async def test_a_deep_reply_a_token_limit_cut_says_so_and_is_persisted_saying_it() -> None:
    texts, sessions = await _run_deep(StoppingDeepBackend(StopReason.CAPPED))
    assert texts == ["a deep ", "stump", REPLY_CAPPED_NOTE]
    history = list(await sessions.history(harness.SESSION))
    assert history[-1].text == f"a deep stump{REPLY_CAPPED_NOTE}"


async def test_a_deep_reply_that_ended_itself_gets_no_note() -> None:
    texts, _sessions = await _run_deep(StoppingDeepBackend(StopReason.FINISHED))
    assert texts == ["a deep ", "stump"]


async def test_a_deep_phase_that_died_says_that_and_not_also_that_it_was_cut() -> None:
    texts: list[str] = []
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION,
        Message(role=Role.USER, text=harness.USER_TEXT, at=_AT, turn_id=harness.TURN),
    )
    phase = BrainPhase(
        sessions,
        StoppingDeepBackend(StopReason.CAPPED, fail=True),
        TickingClock(),
        "brain",
        TurnCapabilities(),
    )
    record = harness.armed_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    events = phase.run(record)
    with pytest.raises(InferenceError):
        await _collect(events, texts)
    await events.aclose()
    assert texts == ["a deep ", "stump", BRAIN_FAILED_NOTE]
    assert REPLY_CAPPED_NOTE not in "".join(texts)


async def test_a_cut_deep_tool_call_ends_the_handoff_rather_than_failing_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="cortex_core.brain_phase")
    texts, sessions = await _run_deep(StoppingDeepBackend(StopReason.CAPPED, cut=True))
    assert texts == ["a deep ", "stump", REPLY_CAPPED_NOTE]
    history = list(await sessions.history(harness.SESSION))
    assert history[-1].text == f"a deep stump{REPLY_CAPPED_NOTE}"
    (logged,) = [record for record in caplog.records if "could not be read" in record.message]
    assert _extra(logged, "capped") is True  # pyright: ignore[reportAttributeAccessIssue]
    assert _extra(logged, "turn_id") == harness.TURN  # pyright: ignore[reportAttributeAccessIssue]


async def test_a_deep_tool_call_no_limit_explains_gets_its_own_note() -> None:
    texts, sessions = await _run_deep(StoppingDeepBackend(StopReason.FINISHED, cut=True))
    assert texts == ["a deep ", "stump", UNREADABLE_CALL_NOTE]
    history = list(await sessions.history(harness.SESSION))
    assert history[-1].text == f"a deep stump{UNREADABLE_CALL_NOTE}"


async def test_a_cut_deep_tool_call_releases_what_the_guardrail_still_held() -> None:
    backend = StoppingDeepBackend(StopReason.FINISHED, cut=True, chunks=("see http://exa",))
    texts, sessions = await _run_deep(backend, guardrail=UrlRedactingGuardrail())
    assert "".join(texts) == "see http://exa" + UNREADABLE_CALL_NOTE
    history = list(await sessions.history(harness.SESSION))
    assert history[-1].text == "see http://exa" + UNREADABLE_CALL_NOTE


async def test_a_deep_server_that_dies_after_a_cap_still_fails_the_handoff() -> None:
    texts: list[str] = []
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION,
        Message(role=Role.USER, text=harness.USER_TEXT, at=_AT, turn_id=harness.TURN),
    )
    phase = BrainPhase(
        sessions,
        StoppingDeepBackend(StopReason.CAPPED, fail=True),
        TickingClock(),
        "brain",
        TurnCapabilities(),
    )
    record = harness.armed_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    events = phase.run(record)
    with pytest.raises(InferenceError, match="died after reporting its stop"):
        await _collect(events, texts)
    await events.aclose()
    assert texts == ["a deep ", "stump", BRAIN_FAILED_NOTE]
    assert UNREADABLE_CALL_NOTE not in "".join(texts)


async def test_the_turns_own_bounds_continue_onto_the_deep_model() -> None:
    asked = GenerationBounds(max_tokens=4096, thinking=False)
    bounded = StoppingDeepBackend(StopReason.FINISHED)
    await _run_deep(bounded, asked)
    assert bounded.bounds == [asked]
    unbounded = StoppingDeepBackend(StopReason.FINISHED)
    await _run_deep(unbounded)
    assert unbounded.bounds == [None]
