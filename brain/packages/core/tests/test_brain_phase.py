"""The deep model's phase: what it rebuilds from the stores, and what it leaves behind.

This is the one hard rule at its narrowest. The phase is handed nothing but a record and its
ports, so every assertion here is about state that came back out of a store or the record after
the process that produced it is (notionally) gone.

Distrust-green proofs (each mutation reddened the named test, then was restored):
- dropping the record's ``loop_tail`` from the working set reddens
  ``test_the_deep_model_sees_the_history_and_the_tool_loop_tail_it_never_persisted``;
- rebuilding a fresh ``TaintLedger`` instead of the record's reddens
  ``test_a_tainted_turn_stays_tainted_and_keeps_its_laundering_evidence``;
- reusing a fresh ``DispatchBudget`` instead of resuming the carried position reddens
  ``test_the_carried_budget_bounds_the_deep_phase_too``;
- taking the query from the brief rather than from history reddens
  ``test_the_query_is_recovered_from_the_store_for_recall_and_memory``;
- dropping the ``opaque`` bit anywhere on its way across (off the snapshot, off the record, or
  out of the rebuilt ledger) reddens both
  ``test_a_carried_opaque_bit_makes_the_deep_phase_redact_strictly`` and
  ``test_a_carried_opaque_bit_keeps_the_deep_phase_out_of_durable_memory``, each of which runs
  its own tainted-but-not-opaque control arm so the difference is the bit and not the taint;
- fencing under a fresh nonce instead of the record's reddens
  ``test_the_deep_phase_fences_under_the_record_s_own_nonce``;
- dropping the phase's own ``aclose`` on its event stream reddens
  ``test_closing_the_deep_phase_mid_stream_tears_its_loop_down``.
"""

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
    REPLY_CAPPED_NOTE,
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
    Message,
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
    """Drain a phase's events into ``into``, letting whatever it raises propagate."""
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
    """Run one deep phase over a seeded session, returning what it saw and what it streamed."""
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
    """Preamble plus history plus the tail: the turn continues where the cortex left it."""
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
    # The tail comes last, in order, with the escalating call itself carrying the brief.
    assert [message.role for message in backend.seen[-2:]] == [Role.ASSISTANT, Role.TOOL]
    assert backend.seen[-2].tool_calls[0].arguments == {"brief": "go"}


async def test_a_tainted_turn_stays_tainted_and_keeps_its_laundering_evidence() -> None:
    """Taint that did not survive the swap would fail open, and the URL set is the defense."""
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
    # The guardrail opened over the RECORD's evidence, so the laundered URL is scrubbed from
    # the deep model's reply exactly as it would have been from the cortex's.
    assert "http://evil.test/x" not in "".join(texts)


async def test_a_tainted_turn_is_kept_out_of_memory_by_the_same_policy() -> None:
    """One taint policy, applied by both phases: the default drops a tainted exchange."""
    ledger = TaintLedger()
    ledger.ingest_untrusted("untrusted", source=None)
    memory = _recaller()
    _phase, _backend, _sessions, _texts = await _drive(
        taint=ledger, capabilities=TurnCapabilities(memory=memory)
    )
    assert await _recorded(memory) == []
    # With the recording policy on, it is remembered instead, marked untrusted.
    memory_on = _recaller()
    _phase2, _backend2, _sessions2, _texts2 = await _drive(
        taint=ledger,
        capabilities=TurnCapabilities(memory=memory_on, record_tainted_memory=True),
    )
    recorded = await _recorded(memory_on)
    assert len(recorded) == 1
    assert recorded[0].tainted is True


def _opaque_ledger() -> TaintLedger:
    """A ledger an image-bearing untrusted result marked, the one way production marks one.

    No URL anywhere in the result text, which is the whole point of the bit: a link painted
    into pixels never reaches ``untrusted_urls``, so the default guardrail has nothing
    collected to redact and only the bit can escalate it.
    """
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
    """The control: the same taint, from untrusted TEXT that carried no URL either."""
    ledger = TaintLedger()
    ledger.ingest_untrusted("a note with nothing linkable in it", source=None)
    return ledger


async def test_a_carried_opaque_bit_makes_the_deep_phase_redact_strictly() -> None:
    """The first consumer, across the swap: strict redaction for a turn that read pixels.

    Defence in depth and named as such. ``SwapConductor._prepare`` refuses an opaque turn
    before any record exists, so the deep phase does not meet one today; what this pins is
    that when it does, the policy it applies comes from the turn's own bit and not from a
    ledger that started fresh. The control arm is the same taint without the bit, so a
    difference here is the bit and nothing else.
    """
    laundered = "http://evil.test/painted-into-the-screenshot"
    _phase, _backend, _sessions, texts = await _drive(
        backend=ScriptedBrainBackend(chunks=(f"visit {laundered} now",)),
        taint=_opaque_ledger(),
        capabilities=TurnCapabilities(guardrail=UrlRedactingGuardrail()),
    )
    assert laundered not in "".join(texts)
    # Same default policy, same taint, no bit: nothing was collected from result text, so the
    # verbatim policy has nothing to flag and the link streams. That IS the vision gap.
    _phase2, _backend2, _sessions2, control_texts = await _drive(
        backend=ScriptedBrainBackend(chunks=(f"visit {laundered} now",)),
        taint=_textual_ledger(),
        capabilities=TurnCapabilities(guardrail=UrlRedactingGuardrail()),
    )
    assert laundered in "".join(control_texts)


async def test_a_carried_opaque_bit_keeps_the_deep_phase_out_of_durable_memory() -> None:
    """The second consumer, across the swap: the memory drop that outranks the record policy.

    Same defence-in-depth framing as its sibling. With recording explicitly switched on, an
    opaque turn is still dropped (a capture turn's reply is a transcription of the screen), and
    the control arm proves the drop is the bit rather than a tightening of taint.
    """
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
    """A swap must not refill the turn's allowance: the deep model gets what was left."""
    audit = RecordingAuditSink()
    dispatcher = ToolDispatcher(_registry(), audit, SystemClock())
    backend = ScriptedBrainBackend(
        chunks=("done",), tool_calls=(ToolCall(id="c1", name="read", arguments={}),)
    )
    slot = harness.armed_slot(budget=_spent_budget())
    record = slot.snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    assert record.budget_closed is True  # the cortex phase had already exhausted the pool
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
    # The pool arrived closed, so the deep model's tool call is refused and audited rather than
    # running on a fresh allowance.
    (invocation,) = audit.records
    assert invocation.ok is False
    assert invocation.detail == BUDGET_EXHAUSTED_MSG


async def test_the_deep_phases_dispatches_are_audited_under_the_turn_that_escalated() -> None:
    """A handoff is one turn continued, and the trail has to read as one turn (ADR-0009
    named-work addendum). The deep phase runs under a fresh model, a fresh loop and a fresh
    ledger, so the only thing tying its tool calls to the cortex's is the id it answers under.
    """
    audit = RecordingAuditSink()
    dispatcher = ToolDispatcher(_registry(), audit, SystemClock())
    backend = ScriptedBrainBackend(
        chunks=("done",), tool_calls=(ToolCall(id="c1", name="read", arguments={}),)
    )
    await _drive(capabilities=TurnCapabilities(tools=dispatcher), backend=backend)
    (invocation,) = audit.records
    assert (invocation.session_id, invocation.turn_id) == (harness.SESSION, harness.TURN)
    assert invocation.task_id == ""  # a handoff is a turn's own work, not a delegate's


async def test_the_query_is_recovered_from_the_store_for_recall_and_memory() -> None:
    """The record carries no user text, so the query comes back out of the session store."""
    memory = _recaller()
    _phase, _backend, _sessions, _texts = await _drive(capabilities=TurnCapabilities(memory=memory))
    (recorded,) = await _recorded(memory)
    assert recorded.text.startswith(f"User: {harness.USER_TEXT}")


async def test_a_session_deleted_mid_handoff_falls_back_to_the_brief() -> None:
    """With no user message left to read, the cortex's brief is the truest ask available."""
    memory = _recaller()
    empty = InMemorySessionStore()
    _phase, _backend, _sessions, _texts = await _drive(
        store=empty, capabilities=TurnCapabilities(memory=memory)
    )
    (recorded,) = await _recorded(memory)
    assert recorded.text.startswith(f"User: {harness.BRIEF}")


async def test_a_deep_model_that_dies_releases_what_the_guardrail_still_held() -> None:
    """A death mid-stream still flushes the guarded carry, so no shown text is lost silently."""
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
    # The partial URL the filter was still holding is released before the note, and persisted.
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
    # The phase re-raises after persisting, so the conductor can fail the record and converge.
    with pytest.raises(InferenceError, match="died mid-stream"):
        await _collect(events, collected)
    await events.aclose()
    assert "".join(collected) == "half an " + BRAIN_FAILED_NOTE
    persisted = [message.text for message in await sessions.history(harness.SESSION)]
    assert persisted[-1] == "half an " + BRAIN_FAILED_NOTE


async def test_the_deep_phase_fences_under_the_record_s_own_nonce() -> None:
    """The fence id survives the swap, or the preamble stops explaining the tail's markers.

    The standing rule tells the model the markers carry a random id **per turn**, and that a
    marker not bearing that id is itself untrusted data. A deep phase that fenced its own
    results under a fresh nonce would put two ids into one context: the blocks the cortex
    fenced before the swap would stop matching the id in force, and exactly the content the
    boundary exists to flag would read as unexplained noise. Fail-open, so it is pinned.
    """
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
    assert len(fenced) == 2  # the tail's block, and the one this phase's own round added
    # One id across both, and it is the record's: the swap changed the weights, not the turn.
    assert set(re.findall(r"id=([0-9a-f]+)>", "".join(fenced))) == {harness.NONCE}


async def test_closing_the_deep_phase_mid_stream_tears_its_loop_down() -> None:
    """A consumer that walks away must not leave the deep model's round half suspended.

    This is the production teardown shape rather than a cancellation: ``converse`` closes the
    engine's stream when the client goes away, and every generator in the chain owes a
    deterministic close then, not a collection at whatever later moment the model server's
    round happens to be dropped.
    """
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
    # And a torn-down phase persists nothing: there is no finished answer to keep.
    assert list(await sessions.history(harness.SESSION)) == []


def _spent_budget() -> DispatchBudget:
    budget = DispatchBudget(limit=1)
    assert budget.charge(2) is False  # closes the pool for good
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
    hits = await recaller.recall("anything", k=5, session_id=harness.SESSION)
    return [hit.record for hit in hits]


class _Embedder:
    async def embed(self, text: str) -> Sequence[float]:
        del text
        return (1.0, 0.0)


# --- The spill watch (ADR-0030 spill-watch addendum) ------------------------------------------
#
# Distrust-green proofs for this section, each mutation reverted after it reddened its test:
# - dropping ``cadence=watch`` from the phase's ``ToolLoopContext`` reddens every test below that
#   expects any reading, because nothing then reaches the watch at all;
# - dropping the ``DecodeCadence`` branch from ``stream_tool_loop`` reddens the same tests AND
#   raises ``AttributeError`` inside the loop, since the event falls through to ``event.text``;
# - logging the collapse at INFO instead of WARNING reddens
#   ``test_a_deep_phase_under_the_declared_floor_warns_once_naming_both_numbers``;
# - reporting after ``_persist`` rather than before reddens nothing, which is why the ordering is
#   pinned by ``test_a_failed_phase_still_reports_what_it_managed_to_observe`` instead.


def _cadence_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Only this phase's own cadence lines, in order."""
    return [record for record in caplog.records if "decode" in record.getMessage()]


def _extra(record: logging.LogRecord, field: str) -> object:
    """One structured field off a log record, ``extra`` landing in the record's own ``__dict__``."""
    return record.__dict__[field]


async def test_a_deep_phase_under_the_declared_floor_warns_once_naming_both_numbers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The measured spill, as the shipped instrument sees it: 17.29 tok/s against a 22 floor."""
    caplog.set_level(logging.INFO, logger="cortex_core.brain_phase")
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=17.29, tokens=96)])
    await _drive(backend=backend, cadence=CadenceTerms(22.0))
    records = _cadence_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert _extra(records[0], "tokens_per_second") == 17.29  # pyright: ignore[reportAttributeAccessIssue]
    assert _extra(records[0], "floor_tokens_per_second") == 22.0  # pyright: ignore[reportAttributeAccessIssue]
    assert records[0].getMessage() == SPILLED_LOG_MSG


async def test_a_deep_phase_that_cleared_its_floor_says_so_without_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The healthy contrast, from the same instrument: the solo rate on the same card."""
    caplog.set_level(logging.INFO, logger="cortex_core.brain_phase")
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=30.4, tokens=96)])
    await _drive(backend=backend, cadence=CadenceTerms(22.0))
    records = _cadence_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert _extra(records[0], "tokens_per_second") == 30.4  # pyright: ignore[reportAttributeAccessIssue]


async def test_a_deployment_that_declared_no_floor_still_gets_its_number(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The number is worth publishing on its own: it is what a later floor would be set from."""
    caplog.set_level(logging.INFO, logger="cortex_core.brain_phase")
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=3.0, tokens=96)])
    await _drive(backend=backend)
    records = _cadence_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.INFO


async def test_a_backend_that_reports_no_timings_is_not_reported_as_healthy(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Silence must never read as a pass, which is the whole reason the port permits silence."""
    caplog.set_level(logging.INFO, logger="cortex_core.brain_phase")
    await _drive(backend=ScriptedBrainBackend(), cadence=CadenceTerms(22.0))
    records = _cadence_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert "nothing was checked" in records[0].getMessage()


async def test_one_slow_round_of_a_tool_loop_does_not_convict_the_tier(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A whole handoff is watched, not a completion, and the best round is what it is judged on."""
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
    assert _extra(records[0], "tokens_per_second") == 29.0  # pyright: ignore[reportAttributeAccessIssue]


async def test_a_failed_phase_still_reports_what_it_managed_to_observe(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A server that died mid-stream is exactly when an operator most wants the rate it managed."""
    caplog.set_level(logging.INFO, logger="cortex_core.brain_phase")
    backend = ScriptedBrainBackend(fail_after=1)
    with pytest.raises(InferenceError):
        await _drive(backend=backend, cadence=CadenceTerms(22.0))
    assert len(_cadence_records(caplog)) == 1


async def test_the_cadence_never_reaches_the_turns_own_stream() -> None:
    """How fast the machine decoded is not something the turn said, so no delta may carry it."""
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=17.29, tokens=96)])
    _phase, _backend, _sessions, deltas = await _drive(backend=backend, cadence=CadenceTerms(22.0))
    assert "".join(deltas) == "a deep answer"


# --- The verdict past the log (ADR-0030 spill-note addendum) -----------------------------------
#
# The half of the watch that reaches somebody: what the phase hands its ``PaceSink``. Each case
# asserts the verdict it published rather than the line it logged, because the two answer
# different people and only one of them is read by an operator who is not tailing a container.
#
# Distrust-green proofs, measured the same way as the section above:
# - logging the verdict and publishing nothing (the state before this landed) reddens 3, every
#   case here that expects a verdict at all;
# - publishing ``collapsed`` rather than the three-state ``verdict`` reddens 1,
#   ``test_a_deployment_that_declared_no_floor_publishes_no_verdict``, which is what keeps a
#   deployment with no floor from clearing a note it could never have written.


async def test_a_spilled_handoff_is_published_and_not_only_logged() -> None:
    """The entry's whole point: the fact leaves the log for somewhere a person will meet it."""
    sink = RecordingPaceSink()
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=17.29, tokens=96)])
    await _drive(backend=backend, cadence=CadenceTerms(22.0, sink))
    assert list(sink.verdicts) == [True]


async def test_a_handoff_that_held_its_pace_publishes_that_too() -> None:
    """The clearing half, and why it is published rather than skipped as uninteresting.

    A tier that reached its floor is the only direct evidence there is that the card has room
    again, so a healthy handoff has to be able to take a standing note down.
    """
    sink = RecordingPaceSink()
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=30.4, tokens=96)])
    await _drive(backend=backend, cadence=CadenceTerms(22.0, sink))
    assert list(sink.verdicts) == [False]


async def test_a_deployment_that_declared_no_floor_publishes_no_verdict() -> None:
    """A number is not a judgement, and a "no" for want of an opinion would clear a real note."""
    sink = RecordingPaceSink()
    backend = ScriptedBrainBackend(cadences=[DecodeCadence(tokens_per_second=3.0, tokens=96)])
    await _drive(backend=backend, cadence=CadenceTerms(sink=sink))
    assert list(sink.verdicts) == []


async def test_a_handoff_with_no_reading_publishes_nothing_at_all() -> None:
    """Silence is not a pass at the port either, or a short completion would clear a spill."""
    sink = RecordingPaceSink()
    await _drive(backend=ScriptedBrainBackend(), cadence=CadenceTerms(22.0, sink))
    assert list(sink.verdicts) == []


async def test_a_failed_phase_still_publishes_the_verdict_it_managed_to_reach() -> None:
    """A server that died under the deep model is exactly when the card is worth suspecting.

    The reading comes off the round before the one that died, which is the only way a failed
    phase has one at all: a stream that raises never reports its own timings.
    """
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
    """A deep-model stream that reports why it stopped, and optionally dies after saying it."""

    def __init__(self, reason: StopReason, *, fail: bool = False) -> None:
        self._reason = reason
        self._fail = fail
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
        yield TextChunk("a deep ")
        yield TextChunk("stump")
        yield DecodeStop(self._reason)
        if self._fail:
            msg = "the deep server died after reporting its stop"
            raise InferenceError(msg)


async def _run_deep(
    backend: StoppingDeepBackend, bounds: GenerationBounds | None = None
) -> tuple[list[str], InMemorySessionStore]:
    """Drive one deep phase over a seeded session, returning its text and the store."""
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION,
        Message(role=Role.USER, text=harness.USER_TEXT, at=_AT, turn_id=harness.TURN),
    )
    phase = BrainPhase(sessions, backend, TickingClock(), "brain", TurnCapabilities(bounds=bounds))
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
    """The tier with the tightest context is the one whose stump is least visible."""
    texts, sessions = await _run_deep(StoppingDeepBackend(StopReason.CAPPED))
    assert texts == ["a deep ", "stump", REPLY_CAPPED_NOTE]
    history = list(await sessions.history(harness.SESSION))
    assert history[-1].text == f"a deep stump{REPLY_CAPPED_NOTE}"


async def test_a_deep_reply_that_ended_itself_gets_no_note() -> None:
    """The control arm on the deep phase, as on the cortex turn."""
    texts, _sessions = await _run_deep(StoppingDeepBackend(StopReason.FINISHED))
    assert texts == ["a deep ", "stump"]


async def test_a_deep_phase_that_died_says_that_and_not_also_that_it_was_cut() -> None:
    """One stump, one explanation: the failure note already says the answer is unfinished."""
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


async def test_the_turns_own_bounds_continue_onto_the_deep_model() -> None:
    """A deployment that capped a reply did not ask for the cap to lapse at the handoff."""
    asked = GenerationBounds(max_tokens=4096, thinking=False)
    bounded = StoppingDeepBackend(StopReason.FINISHED)
    await _run_deep(bounded, asked)
    assert bounded.bounds == [asked]
    unbounded = StoppingDeepBackend(StopReason.FINISHED)
    await _run_deep(unbounded)
    assert unbounded.bounds == [None]
