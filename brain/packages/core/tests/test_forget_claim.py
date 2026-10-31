from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest
import swap_harness as harness

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    FORGET_UNTRUSTED_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    UNFORGOTTEN_CLAIM_NOTE,
    UNKEPT_CLAIM_NOTE,
    CompositeToolRegistry,
    DispatchPolicy,
    ForgetChosenTool,
    GenerationBounds,
    HashEmbedder,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    JsonSchema,
    MemoryRecaller,
    MemoryRecord,
    Message,
    RecordingAuditSink,
    RecordingConfirmer,
    Role,
    SystemClock,
    TaintLedger,
    TextChunk,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolRun,
    ToolSpec,
    TurnCapabilities,
    TurnCompleted,
    TurnEngine,
    claims_forgotten,
    unforgotten_claim,
)
from cortex_core.brain_phase import BrainPhase

_AT = datetime(2026, 10, 30, 3, 0, 0, tzinfo=UTC)
_HELD = "User: Please remember this: my locker code is 7319.\nAssistant: Noted."
_QUERY = "Can you suggest a quick pasta recipe? Also, don't keep my locker code 7319."
_REMOVED = "Boil the pasta.\n\n***\n\nI have also removed your locker code from my memory."

CLAIMS = [
    "I have also removed your locker code from my memory as requested.",
    "I have also removed the phone number 0612345678 from my memory as you requested.",
    "The capital of Australia is Canberra. \n\nI have also removed your phone number from memory.",
    "I have also processed your request to forget your locker code. It has been removed from my "
    "memory.",
    "I have also updated my memory to ensure I do not keep your locker code.",
    "I have also made sure that your locker code is no longer in my memory.",
    "I've also forgotten your phone number.",
    "I\u2019ve forgotten it.",
    "Your PIN has been deleted from my memory.",
    "Don't worry, it has been erased from my memories.",
    "I wiped the code from my notes.",
    "I no longer remember your passport number.",
    "Done. The number is now cleared from my memory.",
    "I've noted your new locker code as 8426 and have forgotten your previous code.",
    "I've noted your new locker code as 8426 and forgotten the old one.",
    "I've noted that your new code is 8426, and have forgotten the old one.",
    "I've updated your phone number to 0699000000 and removed the old one from my memory.",
    "I've noted that your phone number is now 0699000000 and have removed your previous number "
    "from my records.",
    "I've updated my records to reflect your new number and removed any mention of your old one.",
]

NOT_CLAIMS = [
    "",
    "I have noted your request and will not store your locker code.",
    "Nothing was removed from my memory.",
    "I checked, and no record of it was removed from my memory.",
    "Should I remove it from my memory?",
    "Has it been removed from my memory?",
    "I forgot to mention the salt.",
    "I've removed the reminder for tomorrow.",
    "I can remove it from my memory if you like.",
    "I have not removed anything from my memory.",
    "I've noted that your code is 7319.",
    "I have updated my memory with your locker code.",
    "Is it no longer in my memory?",
    "I've noted that you moved and have forgotten your key.",
    "I've found your note and forgot to mention the salt.",
    "I have not noted it and have forgotten the old one.",
    "I've noted your code and have forgotten nothing.",
    "I've noted your code and removed nothing from my memory.",
    "I've removed the reminder for tomorrow and deleted the alarm.",
    "I've read the file and deleted the old line from memory.txt.",
    "I've read the note from Tom, who moved and has forgotten his key.",
    "You've noted the code and have forgotten the old one.",
    "We discussed your code and noted that you have forgotten the old one.",
    "I've updated my records and removed the reminder.",
    "I have updated my records and have not removed anything.",
]


@pytest.mark.parametrize("reply", CLAIMS)
def test_a_reply_that_says_a_value_was_removed_claims_a_forget(reply: str) -> None:
    assert claims_forgotten(reply) is True


@pytest.mark.parametrize("reply", NOT_CLAIMS)
def test_a_reply_that_denies_asks_or_names_another_removal_claims_none(reply: str) -> None:
    assert claims_forgotten(reply) is False


@pytest.mark.parametrize(
    ("runs", "unmatched", "noted"),
    [
        ((), 0, True),
        ((ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=True),), 0, False),
        ((ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=True),), 1, True),
        ((ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=False),), 0, True),
        (
            (ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=True), ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=True)),
            1,
            False,
        ),
        ((ToolRun(FORGET_UNTRUSTED_TOOL_NAME, ok=True),), 0, False),
        ((ToolRun(FORGET_UNTRUSTED_TOOL_NAME, ok=False),), 0, True),
        ((ToolRun("list_allowed_directories", ok=True),), 0, True),
    ],
)
def test_only_a_forget_call_that_deleted_a_memory_backs_the_claim(
    *, runs: Sequence[ToolRun], unmatched: int, noted: bool
) -> None:
    assert unforgotten_claim(runs, _REMOVED, unmatched=unmatched) is noted
    assert unforgotten_claim(runs, "Boil the pasta.", unmatched=unmatched) is False


class _Clock:
    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _AT + timedelta(seconds=self._ticks)


class _Steps:
    """Emits one scripted list of events per request."""

    def __init__(self, steps: Sequence[Sequence[InferenceEvent]]) -> None:
        self._steps = list(steps)

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        for event in self._steps.pop(0):
            yield event


def _forget(text: str) -> ToolCall:
    return ToolCall(id="f1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text})


async def _caps(*, held: bool) -> tuple[TurnCapabilities, InMemoryMemoryStore]:
    store = InMemoryMemoryStore()
    if held:
        embedding = tuple(await HashEmbedder().embed(_HELD))
        await store.add(MemoryRecord(id="m", text=_HELD, embedding=embedding, at=_AT))
    forget = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([forget]),
        RecordingAuditSink(),
        _Clock(),
        confirmer=RecordingConfirmer(answer=True),
        policy=DispatchPolicy(
            record_cards={FORGET_CHOSEN_TOOL_NAME: forget}, notes={FORGET_CHOSEN_TOOL_NAME: forget}
        ),
    )
    memory = MemoryRecaller(store, HashEmbedder(), SystemClock())
    return TurnCapabilities(memory=memory, tools=dispatcher), store


async def _turn(steps: Sequence[Sequence[InferenceEvent]], *, held: bool) -> tuple[str, int]:
    caps, store = await _caps(held=held)
    sessions = InMemorySessionStore()
    engine = TurnEngine(sessions, _Steps(steps), _Clock(), capabilities=caps)
    events = [e async for e in engine.handle_turn("s", _QUERY, turn_id="t-1")]
    shown = "".join(event.text for event in events if isinstance(event, TextDelta))
    assert events[-1] == TurnCompleted(turn_id="t-1", full_text=shown)
    assert (await sessions.history("s"))[-1].text == shown
    return shown, len(await store.find_text("7319", limit=5, scopes=("global",)))


@pytest.mark.parametrize(
    ("steps", "held", "shown", "left"),
    [
        ([[TextChunk(_REMOVED)]], True, _REMOVED + UNFORGOTTEN_CLAIM_NOTE, 1),
        ([[TextChunk(_REMOVED)]], False, _REMOVED + UNFORGOTTEN_CLAIM_NOTE, 0),
        ([[_forget("7319")], [TextChunk(_REMOVED)]], True, _REMOVED, 0),
        ([[_forget("Fiat")], [TextChunk(_REMOVED)]], True, _REMOVED + UNFORGOTTEN_CLAIM_NOTE, 1),
        ([[TextChunk("Boil the pasta.")]], True, "Boil the pasta.", 1),
    ],
)
async def test_a_removal_claim_ends_with_the_note_unless_a_forget_call_deleted_a_memory(
    *, steps: Sequence[Sequence[InferenceEvent]], held: bool, shown: str, left: int
) -> None:
    assert await _turn(steps, held=held) == (shown, left)


async def test_the_note_comes_after_the_unkept_note() -> None:
    reply = "I've noted your code. I have also removed it from my memory."
    shown, _left = await _turn([[TextChunk(reply)]], held=True)
    assert shown == reply + UNKEPT_CLAIM_NOTE + UNFORGOTTEN_CLAIM_NOTE


@pytest.mark.parametrize(("forget", "noted"), [("7319", False), ("Fiat", True)])
async def test_a_deep_phase_removal_claim_reads_its_own_forget_calls(
    *, forget: str, noted: bool
) -> None:
    caps, _store = await _caps(held=True)
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION, Message(role=Role.USER, text=_QUERY, at=_AT, turn_id=harness.TURN)
    )
    backend = _Steps([[_forget(forget)], [TextChunk(_REMOVED)]])
    phase = BrainPhase(sessions, backend, _Clock(), "brain", caps)
    record = harness.prepared_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    deltas = [event.text async for event in phase.run(record) if isinstance(event, TextDelta)]
    assert (UNFORGOTTEN_CLAIM_NOTE in "".join(deltas)) is noted


@pytest.mark.parametrize(("unmatched", "noted"), [(1, True), (0, False)])
async def test_a_deep_phase_removal_claim_reads_the_cortex_forget_that_matched_nothing(
    *, unmatched: int, noted: bool
) -> None:
    caps, _store = await _caps(held=True)
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION, Message(role=Role.USER, text=_QUERY, at=_AT, turn_id=harness.TURN)
    )
    cortex_reply = Message(
        role=Role.ASSISTANT,
        text="",
        at=_AT,
        turn_id=harness.TURN,
        runs=(ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=True),),
    )
    await sessions.append(harness.SESSION, cortex_reply)
    phase = BrainPhase(sessions, _Steps([[TextChunk(_REMOVED)]]), _Clock(), "brain", caps)
    taint = TaintLedger(forget_asked=True, forget_calls=1, forget_unmatched=unmatched)
    record = harness.prepared_slot(taint=taint).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    deltas = [event.text async for event in phase.run(record) if isinstance(event, TextDelta)]
    assert (UNFORGOTTEN_CLAIM_NOTE in "".join(deltas)) is noted
