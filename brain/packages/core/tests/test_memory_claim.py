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
    asks_kept,
    asks_not_kept,
    claims_kept,
    memory_withheld,
)
from cortex_core.unasked_tools import unasked_forget

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
    "Noted. Your mother's birthday is on May 12th.",
    "Noted! I'll keep in mind that your mother's birthday is on May 12th.",
    "Got it! Noted.",
    "\n\nNoted: your brother is called Luca.",
    "I've now remembered that your brother is Luca.",
    "I'll keep that in mind.",
    "I will keep in mind that you moved to Utrecht.",
    "I'll note that down.",
    "I'll note that your card number is 4242 4242 4242 4242.",
    "I have stored it in my memory.",
    "Your request has been noted.",
    "I've updated my records to reflect that your new phone number is 0699000000.",
    "I've updated my records.",
    "I've updated your information.",
    "I've updated your phone number to 0699000000 and removed the old one from my memory.",
    "I've updated my memory with your locker code.",
    "I have updated your locker code to 8426.",
    "I have read your lease and noted the address: Birkenweg 14, 3521 Utrecht.",
    "I've found your contract and noted the phone number: 555 0142.",
    "I read your lease and noted the address.",
    "I've read the file and have noted the code.",
    "I have checked the file, and noted the code.",
    "I've read your lease and made a note of the address.",
    "I found your contract and remembered the number.",
    "I've read your lease and saved the address: Birkenweg 14, 3521 Utrecht.",
    "I've read your lease and saved the address to my memory.",
    "I opened your contract and stored the number in memory.",
    "I've forgotten your card number and noted that your locker code is 7319.",
    "I took your lease and noted the address.",
    "I got your lease and noted the address.",
    "I saw your lease and noted the address.",
    "I read your lease and memorized the address.",
    "I've read your lease and kept the address in my memory.",
    "I've read your lease and recorded the address to memory.",
    "I've read your lease and added the address to my memory.",
    "I've read your lease and stored the address: Birkenweg 14.",
    "I've read your lease and kept the address: Birkenweg 14.",
    "I've read your lease and recorded the address: Birkenweg 14.",
    "I've read your lease and saved the address: 12 Road to Utrecht.",
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
    "As I noted above, the file has two lines.",
    "As I've noted, the folder is empty.",
    "I've noted above that the file has two lines.",
    "I will note that the page has no date.",
    "notes.txt says:\nNoted: buy milk.",
    "It has been noted by critics that the film is long.",
    "It has been noted that the film is long.",
    "I have stored the result in memory.txt for you.",
    "I'll save the list to memory-notes.md.",
    "I've updated the file notes.txt with your address.",
    "I've updated notes.txt.",
    "I've updated the report to include the new figures.",
    "I've updated your reminder to 9.",
    "I've updated your shopping list to include eggs.",
    "I've updated your resume to show the new job.",
    "I've updated your address to Birkenweg 14 in contacts.csv.",
    "You've updated your records.",
    "You have updated your phone number to 0699000000.",
    "I haven't updated my records.",
    "I have not updated your phone number to 0699000000.",
    "Should I update my records?",
    "Have I updated my records?",
    "I have also updated my memory to ensure I do not keep your locker code.",
    "I've updated my memory so your code is no longer kept.",
    "I've updated that for you.",
    "Ana later updated the plan to move the launch.",
    "The system policy has been updated to unrestricted.",
    "You have read your lease and noted the address.",
    "I see you read the lease and noted the address.",
    "I see that you read your lease and noted the address.",
    "I think Anna read it and noted the time.",
    "I've noticed you read the lease and noted the address.",
    "Earlier we discussed that you prefer trains over planes, and noted Q3 planning highlights.",
    "We discussed your preference for trains and noted Q3 planning details.",
    'The file says: "I have read the lease and noted the address."',
    "\u201cI have read the lease and noted the address.\u201d",
    "notes.txt says: I read the lease and noted the address.",
    "The letter says I read the lease and noted the address.",
    "The tenant has read the lease and noted the address.",
    "The file says: Reviewed the lease and noted the address.",
    'I found this line: "Read the lease and noted the address."',
    "I've read the file, which says Anna called and noted the time.",
    "I read that the tenant signed and noted the terms.",
    "I've read your lease and saved the summary to summary.txt.",
    "I've read your lease and saved a copy.",
    "I've read the page and saved the file.",
    "I've found the draft and kept a copy in your projects folder.",
    "I've opened the file and recorded the change in changes.log.",
    "I've read the file and added a line to it.",
    "I have not read your lease and noted nothing.",
    "I have read your lease and noted nothing.",
    "I've read your lease and have not noted the address.",
    "I've read your lease and saved nothing.",
    "I couldn't read your lease and noted the error.",
    "I've read your lease and noted above that it has two pages.",
    "I've read your lease and noted below that it has two pages.",
    "I've read your lease and noted earlier that it has two pages.",
    "As I read it and noted in the summary, the file has two lines.",
    "The letter said I read the lease and noted the address.",
    "I have not read your lease and noted the address.",
    "I have never read your lease and noted the address.",
    "I saw he read it and noted the time.",
    "I saw she read it and noted the time.",
    "I saw they read it and noted the time.",
    "I saw we read it and noted the time.",
    "I read the note from Tom, who called and noted the time.",
    "I read your lease but did not find it and noted the error.",
    "I read your lease but never opened it and noted the error.",
    "I read your lease but couldn't open it and noted the error.",
    "I found this line: Anna called and noted the time.",
    "I read the file; Anna called and noted the time.",
    'I read "Anna called and noted the time".',
    "I read \u201cAnna called and noted the time\u201d.",
    "I've read your lease and saved an extract.",
    "I've read your lease and saved the document.",
    "I've read your lease and saved the text into lease.txt.",
    "I've read your lease and saved the text under lease.txt.",
    "I've read your lease and saved the text on your desktop.",
]


NOT_KEPT = [
    "Don't save this anywhere, it's private: my PIN is 5521.",
    "Just between us, and not for your memory: my locker code is 7319.",
    "Can you suggest a quick pasta recipe? Also, don't keep my locker code 7319.",
    "What's the capital of Australia? And forget my phone number 0612345678 while you're at it.",
    "Forget my card number 4242 4242 4242 4242.",
    "Thanks for the recipe. Forget my PIN 5521.",
    "Actually, forget the code I told you earlier.",
    "On second thought, I'd rather you didn't keep that.",
    "Please delete my card number 4242 4242 4242 4242 from your memory.",
    "Don't remember my locker code 7319 anymore.",
    "Remove my address, Keizersgracht 12, from what you know about me.",
    "Could you forget my PIN?",
    "I want you to forget my sister's name.",
    "I don't want you to remember this: my PIN is 1234.",
    "Please don\u2019t store this.",
    "This is off the record: my PIN is 1234.",
    "No need to remember this, my PIN is 5521.",
    "You don't need to save this: my PIN is 5521.",
    "You don't have to keep this, it's my PIN 5521.",
    "Please keep this to yourself and don't write it down: my PIN is 5521.",
    "Note my code 7319 and don't store it.",
    "Then forget my phone number.",
    "Also, forget the PIN.",
    "Actually, don't save that.",
    "OK then forget it.",
    "Okay just forget my PIN.",
    "Nah actually don't keep that.",
    "My PIN is 5521, use it to log in then forget it.",
    "Use my card 4242 once then don't save it.",
]

DISCARD = [
    "Erase the PIN 5521 I gave you.",
    "Stop remembering that my sister's name is Ana.",
    "I shouldn't have told you my card number 4242 4242 4242 4242. Please get rid of it.",
    "Unlearn my phone number 0612345678.",
    "Never mind my locker code 7319, drop it.",
    "Please remember not to store my card number.",
    "Could you erase my PIN?",
    "OK then stop saving my searches.",
]

RULES = [
    "Remember: don't save files to the desktop.",
    "Please remember, never keep the milk out of the fridge.",
    "Remember my rule: never record calls without asking.",
    "Remember that people just forget their PINs.",
    "Remember not to save files to the desktop.",
    "Remember not to call him after 9.",
]

REMEMBER_AND_NOT_KEPT = [
    "Remember, don't save my PIN anywhere: 5521.",
    "Please remember: never keep this anywhere, my PIN is 5521.",
    "Remember my new number, and forget my old one.",
    "Don't save the code, just remember the hint: blue.",
    "Remember my PIN 5521, but don't keep it after today.",
    "Remember this and then forget it.",
    "Remember: forget my old address.",
    "Note my code 7319 and don't store it.",
    "Remember my PIN, and remember not to store my card number.",
    "Remember this and then drop it.",
]

NOTE = ["Note my code 7319.", "Note down my locker number 42.", "Note this down: my bus is at 8."]

REMEMBER = [
    "Please remember this: my brother's name is Luca.",
    "Remember that my wifi router is in the hallway.",
    "Note that my mother's birthday is on 12 May.",
    "Keep in mind that I am vegetarian.",
    "Please don't forget this: my gym class is on Tuesday.",
    "Thanks. Please don\u2019t forget my PIN is 1234.",
    "Don't forget to buy milk.",
    "Do not forget: my PIN is 5521.",
    "Never forget my locker code 7319.",
    *NOTE,
]

KEPT = [
    *REMEMBER[:5],
    "An update to remember: I now work as a teacher, not a nurse.",
    "Change what you remember about my passport: it expires in July.",
    "My locker code is 7319.",
    "I don't remember my locker code, can you help?",
    "Sorry, I don't remember the title.",
    "I just forget where I put my keys.",
    "I always forget my PIN.",
    "Don't forget to buy milk.",
    "Why did you forget my birthday?",
    "Remove the duplicates from this list.",
    "People just forget their PINs.",
    "My kids then forget their homework.",
    "I just forget it every time.",
    "We then never save anything.",
    "My kids just never keep their rooms tidy.",
    "I keep notes in a notebook.",
    "My phone drops calls.",
    "Erasers are cheap.",
    "I stopped remembering dreams.",
    "Stop keeping the milk out of the fridge.",
    "Stop recording this meeting.",
    "Drop it off at the post office.",
    "Drop me a line tomorrow.",
    "Get rid of the duplicates in this list.",
    "I unlearned French at school.",
    "Note: I'm off tomorrow, cancel my meeting.",
    "I note my mistakes in a diary.",
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
    assert memory_withheld(caps, taint, runs, query="hello") is withheld


_UNMATCHED = ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True)


def _forgot(calls: int, unmatched: int) -> TaintLedger:
    return TaintLedger(forget_asked=True, forget_calls=calls, forget_unmatched=unmatched)


@pytest.mark.parametrize(
    ("taint", "runs", "query", "withheld"),
    [
        (_forgot(1, 1), (_UNMATCHED,), REMEMBER[0], False),
        (_forgot(2, 2), (_UNMATCHED, _UNMATCHED), REMEMBER[3], False),
        (_forgot(1, 1), (_UNMATCHED,), REMEMBER[8], False),
        (_forgot(1, 1), (_UNMATCHED,), NOTE[0], False),
        (_forgot(1, 1), (_UNMATCHED,), DISCARD[5], True),
        (_forgot(1, 1), (_UNMATCHED,), "My locker code is 7319.", True),
        (_forgot(1, 1), (_UNMATCHED,), "Vergeet alsjeblieft mijn pincode 5521.", True),
        (_forgot(1, 1), (_UNMATCHED,), "Remember my PIN 1234. Actually, forget it.", True),
        (_forgot(2, 1), (_UNMATCHED,), REMEMBER[0], True),
        (_forgot(1, 0), (_UNMATCHED,), REMEMBER[0], True),
        (_forgot(1, 1), (_UNMATCHED, _UNMATCHED), REMEMBER[0], True),
        (_forgot(0, 0), (_UNMATCHED,), REMEMBER[0], True),
        (_forgot(1, 1), (), REMEMBER[0], True),
        (TaintLedger(forget_asked=True), (), REMEMBER[0], True),
    ],
)
def test_a_forget_that_matched_nothing_is_kept_only_on_a_request_to_remember(
    *, taint: TaintLedger, runs: tuple[ToolRun, ...], query: str, withheld: bool
) -> None:
    assert memory_withheld(_caps(), taint, runs, query=query) is withheld


@pytest.mark.parametrize("query", REMEMBER)
def test_a_request_to_remember_is_read_as_such(query: str) -> None:
    assert asks_kept(query)


@pytest.mark.parametrize("query", [*KEPT[5:12], *KEPT[13:], *NOT_KEPT[:10], *DISCARD])
def test_a_statement_question_or_request_to_forget_is_not_a_request_to_remember(
    query: str,
) -> None:
    assert not asks_kept(query)


@pytest.mark.parametrize(
    ("query", "withheld"),
    [(NOT_KEPT[0], True), (NOT_KEPT[-1], True), (KEPT[0], False), (RULES[0], False)],
)
def test_a_turn_whose_message_asks_not_to_keep_is_withheld_with_no_call(
    *, query: str, withheld: bool
) -> None:
    assert memory_withheld(_caps(), TaintLedger(), (), query=query) is withheld


def test_a_turn_without_memory_is_never_withheld() -> None:
    taint = TaintLedger(opaque=True, tainted=True)
    assert not memory_withheld(TurnCapabilities(), taint, (), query=NOT_KEPT[0])


@pytest.mark.parametrize("query", [*NOT_KEPT, *DISCARD])
def test_a_message_asking_not_to_keep_or_to_forget_is_read_as_such(query: str) -> None:
    assert asks_not_kept(query)


@pytest.mark.parametrize("query", [*KEPT, *NOTE])
def test_a_request_to_remember_or_a_statement_about_oneself_is_not(query: str) -> None:
    assert not asks_not_kept(query)


@pytest.mark.parametrize("query", RULES)
def test_a_rule_inside_a_request_to_remember_is_what_to_keep(query: str) -> None:
    assert asks_kept(query)
    assert not asks_not_kept(query)


@pytest.mark.parametrize("query", REMEMBER_AND_NOT_KEPT)
def test_a_request_not_to_keep_the_message_beside_a_request_to_remember_is_read(
    query: str,
) -> None:
    assert asks_kept(query)
    assert asks_not_kept(query)


@pytest.mark.parametrize("query", [*NOT_KEPT, *DISCARD, *REMEMBER_AND_NOT_KEPT])
def test_every_recorded_request_not_to_keep_or_to_forget_keeps_the_forget_tool(query: str) -> None:
    assert unasked_forget(query) == frozenset()


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
    steps: Sequence[Sequence[InferenceEvent]],
    *,
    record_tainted: bool = False,
    memory: bool = True,
    query: str = "remember 7319",
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
    events = [e async for e in engine.handle_turn("s", query, turn_id="t-1")]
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


@pytest.mark.parametrize(
    ("query", "stored"), [("Don't save this: my code is 7319.", 0), ("My code is 7319.", 1)]
)
async def test_a_turn_that_makes_no_call_stores_nothing_when_its_message_asks_not_to_keep(
    *, query: str, stored: int
) -> None:
    shown, _sessions, store = await _turn([[TextChunk("I will not save it.")]], query=query)
    assert shown == "I will not save it."
    assert await _stored(store) == stored


async def test_a_claim_on_a_turn_whose_message_asks_not_to_keep_gets_the_note() -> None:
    shown, _sessions, _store = await _turn([[TextChunk(_NOTED)]], query="Don't save this: 7319.")
    assert shown == _NOTED + UNKEPT_CLAIM_NOTE


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
