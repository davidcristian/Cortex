from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    FORGET_UNTRUSTED_TOOL_NAME,
    REPLY_CAPPED_NOTE,
    UNKEPT_CLAIM_NOTE,
    DecodeStop,
    GenerationBounds,
    HashEmbedder,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    MemoryRecaller,
    Message,
    RecordingAuditSink,
    StopReason,
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
    claims_kept,
    memory_withheld,
)

_START = datetime(2026, 10, 29, 3, 0, tzinfo=UTC)
_NOTED = "I've noted that your locker code is 7319."

CLAIMS = [
    _NOTED,
    "I have noted your card number: 4242 4242 4242 4242.",
    "I've remembered that your brother's name is Luca.",
    "OK. I'll remember that your card number is 4242 4242 4242 4242.",
    "I will keep this in mind for our future conversations.",
    "I\u2019ve noted that you moved to Utrecht.",
    "I've also made a note of your locker code.",
    "I have saved that to my memory.",
    "Your locker code has been noted.",
    "Got it, noted!",
    "Noted: your brother is called Luca.",
    "Here are the folders I can read:\n- /projects\nI've noted your locker code.",
    "Do you want the files too? I've noted the code.",
]

NOT_CLAIMS = [
    "",
    "I couldn't remember your locker code because the action was declined.",
    "I didn't save that card number because it was declined.",
    "I'm sorry, I wasn't able to remember your card number.",
    "I have not noted anything.",
    "I've not noted the code.",
    "I will not remember this.",
    "Would you like me to remember it?",
    "Should I list what I've noted so far?",
    "Shall I note that down?",
    "If you'd like me to remember it, please let me know.",
    "I remember that you live in Utrecht.",
    "I've saved the summary to notes.txt.",
    "The file notes.txt says: Card for testing: a passport scan is not here.",
    "I've added a line to the file in your projects folder.",
]


@pytest.mark.parametrize("reply", CLAIMS)
def test_a_reply_saying_something_was_noted_is_a_claim(reply: str) -> None:
    assert claims_kept(reply)


@pytest.mark.parametrize("reply", NOT_CLAIMS)
def test_a_reply_that_negates_offers_or_names_a_file_is_not_a_claim(reply: str) -> None:
    assert not claims_kept(reply)


def _caps(*, record_tainted: bool = False) -> TurnCapabilities:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    return TurnCapabilities(memory=recaller, record_tainted_memory=record_tainted)


_FORGOT = ToolRun(name=FORGET_UNTRUSTED_TOOL_NAME, ok=True)


@pytest.mark.parametrize(
    ("taint", "runs", "record_tainted", "withheld"),
    [
        (TaintLedger(), (), False, False),
        (TaintLedger(tainted=True), (), False, True),
        (TaintLedger(tainted=True), (), True, False),
        (TaintLedger(opaque=True), (), True, True),
        (TaintLedger(tainted=True), (_FORGOT,), True, True),
        (TaintLedger(), (_FORGOT,), True, False),
        (TaintLedger(tainted=True), (ToolRun(FORGET_UNTRUSTED_TOOL_NAME, ok=False),), True, False),
        (TaintLedger(forget_asked=True), (), False, True),
        (TaintLedger(), (ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=False),), False, True),
        (TaintLedger(), (ToolRun(name="read", ok=True),), False, False),
    ],
)
def test_a_turn_is_withheld_on_each_path_that_stores_nothing(
    *, taint: TaintLedger, runs: tuple[ToolRun, ...], record_tainted: bool, withheld: bool
) -> None:
    caps = _caps(record_tainted=record_tainted)
    assert memory_withheld(caps, taint, runs) is withheld


def test_a_turn_without_memory_is_never_withheld() -> None:
    assert not memory_withheld(TurnCapabilities(), TaintLedger(opaque=True, tainted=True), ())


class _Clock:
    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _START + timedelta(seconds=self._ticks)


class _Scripted:
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


async def _folders(arguments: Mapping[str, object]) -> str:
    del arguments
    return "/projects"


async def _turn(
    steps: Sequence[Sequence[InferenceEvent]], *, record_tainted: bool = False, memory: bool = True
) -> tuple[str, InMemorySessionStore, InMemoryMemoryStore]:
    read = ToolSpec(name="list_allowed_directories", description="list", parameters={})
    registry = InMemoryToolRegistry({read.name: (read, _folders)})
    store = InMemoryMemoryStore()
    sessions = InMemorySessionStore()
    caps = TurnCapabilities(
        memory=MemoryRecaller(store, HashEmbedder(), SystemClock()) if memory else None,
        record_tainted_memory=record_tainted,
        tools=ToolDispatcher(registry, RecordingAuditSink(), _Clock()),
    )
    engine = TurnEngine(sessions, _Scripted(steps), _Clock(), capabilities=caps)
    events = [e async for e in engine.handle_turn("s", "remember 7319", turn_id="t-1")]
    shown = "".join(event.text for event in events if isinstance(event, TextDelta))
    assert events[-1] == TurnCompleted(turn_id="t-1", full_text=shown)
    assert (await sessions.history("s"))[-1].text == shown
    return shown, sessions, store


async def _stored(store: InMemoryMemoryStore) -> int:
    return len(await store.search(await HashEmbedder().embed("7319"), k=5))


_READ = ToolCall(id="c1", name="list_allowed_directories", arguments={})
_FORGET = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"texts": ["7319"]})


@pytest.mark.parametrize(
    ("steps", "record_tainted"),
    [
        ([[TextChunk(_NOTED)]], False),
        ([[_READ], [TextChunk(_NOTED)]], False),
        ([[_READ], [TextChunk(_NOTED)]], True),
        ([[_FORGET], [TextChunk(_NOTED)]], True),
    ],
)
async def test_the_note_shows_exactly_when_the_turn_stores_nothing(
    *, steps: Sequence[Sequence[InferenceEvent]], record_tainted: bool
) -> None:
    shown, _sessions, store = await _turn(steps, record_tainted=record_tainted)
    stored = await _stored(store)
    assert shown in {_NOTED, _NOTED + UNKEPT_CLAIM_NOTE}
    assert (shown == _NOTED + UNKEPT_CLAIM_NOTE) is (stored == 0)


async def test_a_withheld_turn_whose_reply_claims_nothing_gets_no_note() -> None:
    shown, _sessions, store = await _turn([[_READ], [TextChunk("You can read /projects.")]])
    assert shown == "You can read /projects."
    assert await _stored(store) == 0


async def test_a_turn_without_memory_gets_no_note() -> None:
    shown, _sessions, _store = await _turn([[_READ], [TextChunk(_NOTED)]], memory=False)
    assert shown == _NOTED


async def test_the_note_comes_after_the_length_note() -> None:
    capped = [TextChunk("I've noted the code"), DecodeStop(StopReason.CAPPED)]
    shown, _sessions, _store = await _turn([[_READ], capped])
    assert shown == "I've noted the code" + REPLY_CAPPED_NOTE + UNKEPT_CLAIM_NOTE
