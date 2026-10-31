from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime

import pytest
import swap_harness as harness
from swap_harness import ScriptedBrainBackend, TickingClock

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    NO_CADENCE_TERMS,
    SCHEDULE_TOOL_NAME,
    SET_VOLUME_TOOL_NAME,
    BrainPhase,
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
    Role,
    SystemClock,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
    asks_kept,
    asks_not_kept,
)
from cortex_core.dispatch import UNASKED_MSG
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.unasked_tools import unasked_forget, unasked_sidecar_tools, unasked_tools

_AT = datetime(2026, 10, 30, 4, 0, 0, tzinfo=UTC)
_BOTH = frozenset({SET_VOLUME_TOOL_NAME, SCHEDULE_TOOL_NAME})
_FILE_TOOLS = ("list_allowed_directories", "read_file", "search_files")
_REMEMBER_A_FACT = "Please remember this: my daughter is allergic to peanuts."
_REMEMBER_AND_ASK = (
    "Please remember this: my locker code is 7319. Also, which folders can you read?"
)


_RETRACTED = (
    *("nuked", "killed", "destroyed", "shredded", "dumped", "expunged", "overwritten", "cancelled"),
    *("scratched", "striked", "crossed out", "thrown away", "disposed of"),
    *("blanked", "reset", "cleaned up", "updated", "changed", "corrected", "obsolete", "stale"),
    *("gone", "nevermind", "unsaved", "unremembered", "unstored", "the earlier one", "prior"),
)


def _sidecar(*names: str) -> tuple[ToolSpec, ...]:
    return tuple(ToolSpec(name=name, description="", parameters={}, sidecar=True) for name in names)


@pytest.mark.parametrize(
    "query",
    [
        "Please remember this: I work as a nurse.",
        "Please remember this: I take the train at 7:40.",
        "Remember that my wifi router is in the hallway.",
        "Note that my mother's birthday is on 12 May.",
        "Keep in mind that I am vegetarian.",
        "Please don't forget this: my gym class is on Tuesday.",
        "Note my code 7319.",
        "Note down my locker number 42.",
        "Remember that my brother texts me every day.",
        "Note that the heads of the team meet on Monday.",
        "Remember that the remote is under the couch, and turn the heating down.",
    ],
)
def test_a_request_to_remember_a_fact_asks_for_neither_tool(query: str) -> None:
    assert unasked_tools(query) == _BOTH


@pytest.mark.parametrize(
    "query",
    [
        "Please remember this: I take my pills at 8 pm. Remind me every day at 8 pm to take them.",
        "Note that my mother's birthday is on 12 May, and remind me of it the day before.",
        "Remember to call the plumber tomorrow at 10.",
        "Please don't forget to wake me at 6.",
        "Keep in mind that I have a flight on Friday, and set an alarm for 5.",
        "Remember that my exam is on Monday; tell me before it starts.",
        "Note that the parcel comes on Friday, so don\u2019t let me forget it.",
        "Remember this: I want a notification every Sunday to water the plants.",
        "Please remember this: schedule a call with Ana on Monday.",
        "Note my dentist appointment on Friday and remind me the day before.",
        "Note down my flight at 6 and wake me at 4.",
        "Note down the meeting time and remind me at 4.",
        "Note my dentist appointment Friday at 3 and give me a heads-up an hour before.",
        "Remember my exam on Monday and give me a heads up the night before.",
        "Note my flight at 6 and text me at 4.",
        "Remember the meeting at 9 and nudge me at 8:45.",
        "Note down the bus at 7 and buzz me at 6:50.",
        "Keep in mind my parking ends at 5, so warn me at 4:50.",
        "Note my call at 3 and message me before it.",
        "Remember my tea is steeping and poke me in 5 minutes.",
    ],
)
def test_a_request_to_remember_that_asks_for_a_reminder_keeps_the_schedule_tool(
    query: str,
) -> None:
    assert unasked_tools(query) == {SET_VOLUME_TOOL_NAME}


@pytest.mark.parametrize(
    "query",
    [
        "Please remember this: I like my music quiet, so turn the volume down to 20%.",
        "Keep in mind that I am in a meeting now, so please mute the sound.",
        "Please remember this: I am hard of hearing. Make it louder.",
        "Remember that the speakers are too loud at night.",
        "Note my code 7319 and turn it down.",
        "Remember I sleep at 11, so turn that down now.",
        "Keep in mind the baby is asleep and turn this up only a little.",
    ],
)
def test_a_request_to_remember_that_names_the_sound_keeps_the_volume_tool(query: str) -> None:
    assert unasked_tools(query) == {SCHEDULE_TOOL_NAME}


@pytest.mark.parametrize(
    "query",
    [
        "Remind me at 9 to call my mother.",
        "Turn it down a bit.",
        "My brother's name is Luca.",
        "I just remember that the bank closes at four.",
        "Note: I'm off tomorrow, cancel my meeting.",
        "Please remember not to store my card number.",
    ],
)
def test_a_message_that_asks_nothing_be_remembered_leaves_every_tool(query: str) -> None:
    assert unasked_tools(query) == frozenset()
    assert unasked_sidecar_tools(query, _sidecar(*_FILE_TOOLS)) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        _REMEMBER_A_FACT,
        "Please remember this: my locker code is 7319.",
        "Please remember this: I take the train at 7:40.",
        "Please remember this: my card number is 4242 4242 4242 4242.",
        "Remember that my wifi router is in the hallway.",
        "Note that my mother's birthday is on 12 May.",
        "Keep in mind that I am vegetarian.",
        "Please don't forget this: my gym class is on Tuesday.",
        "Note my code 7319.",
    ],
)
def test_a_request_to_remember_a_fact_refuses_every_sidecar_tool(query: str) -> None:
    assert unasked_sidecar_tools(query, _sidecar(*_FILE_TOOLS)) == set(_FILE_TOOLS)


@pytest.mark.parametrize(
    "query",
    [
        _REMEMBER_AND_ASK,
        "Remember my locker code is 7319 and list the folders you can read.",
        "Read notes.txt and remember what it says.",
        "Remember what is in notes.txt.",
        "Note that my plan is in notes.txt. What does it say?",
        "Keep in mind that my notes file is called notes.txt, and show me what it holds.",
        "Remember the contents of my documents folder.",
        "Note down what the report says.",
        "Remember the second line of /home/me/todo.",
        "Remember this page: https://example.com/a",
        "Keep in mind what my last email said.",
        "Remember my code 7319. Then look in the folder for the form.",
        "Note this document for me",
        "Remember this attachment",
        "Remember what is on the wiki, and then search for the form.",
        "Note my code 7319; find the form as well.",
        "Remember which drawer the form is in",
        "Note that I moved to Utrecht last week, and tell me which files you can see.",
        "Please remember this: my brother's name is Luca. Also, what does notes.txt say?",
        "Remember that my locker code is 7319, and list the folders you can read.",
        "Remember my code 7319, and can you tell me the time?",
        "Remember my code 7319. Then tell me the time.",
        "Remember notes.txt for me.",
    ],
)
def test_a_request_to_remember_that_asks_about_a_source_keeps_every_sidecar_tool(
    query: str,
) -> None:
    assert unasked_sidecar_tools(query, _sidecar(*_FILE_TOOLS)) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Please remember this: I read a lot of novels.",
        "Remember that my file cabinet is in the hallway.",
        "Keep in mind that my shopping list is on the fridge.",
        "Note that my sister's folder is blue.",
        "Remember that I look after my mother on Sundays.",
        "Please remember this: my landlord is called Mr. Weber.",
    ],
)
def test_a_fact_holding_a_word_for_a_source_only_keeps_the_sidecar_tools_offered(
    query: str,
) -> None:
    assert unasked_sidecar_tools(query, _sidecar(*_FILE_TOOLS)) == frozenset()


def test_a_word_of_a_sidecar_tool_name_keeps_the_tools_of_any_server() -> None:
    calendar = _sidecar("query_calendar_events")
    assert unasked_sidecar_tools("Note down my calendar entries.", calendar) == frozenset()
    assert unasked_sidecar_tools("Note down my locker number 42.", calendar) == {
        "query_calendar_events"
    }


def test_a_tool_no_sidecar_serves_is_not_refused_for_being_listed() -> None:
    listed = (ToolSpec(name="look", description="", parameters={}),)
    assert unasked_sidecar_tools(_REMEMBER_A_FACT, listed) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Please remember this: my brother's name is Luca.",
        "Please remember this: I work as a nurse.",
        "Please remember this: my car is a red Fiat.",
        "Please remember this: my daughter is allergic to peanuts.",
        "Please remember this: my bank closes at four on Fridays.",
        "Please remember this: my landlord is called Mr Weber.",
        "Please remember this: my favourite tea is jasmine.",
        "Please remember this: my passport expires in March.",
        "Please remember this: my neighbour's dog is called Rex.",
        "Please remember this: I take the train at 7:40.",
        "Remember that my wifi router is in the hallway.",
        "Note that my mother's birthday is on 12 May.",
        "Keep in mind that I am vegetarian.",
        "Please remember this: my sister's name is Ana.",
        "Please don't forget this: my gym class is on Tuesday.",
        "Please don\u2019t forget this: my gym class is on Tuesday.",
        "Do not forget: my PIN is 5521.",
        "Never forget my locker code 7319.",
        "Note down my locker number 42.",
        "Remember the address on my lease.",
        "Remember that my sister and her kids live in Graz.",
        "Note that I like tea and coffee.",
        "Remember that my cat, Mia, sleeps on the sofa.",
        "Please remember this: my car, a red Fiat, is in the garage.",
        "Remember that I was born in 1990 and live in Graz.",
        "Please remember this: I walk the dog at 7.",
        "Please remember this: my boss is called Ana \u2013 she runs the lab.",
        "Please don\u2019t forget this: the plumber\u2019s name is Tom.",
        "Please remember this: my rent is 900\u20ac.",
    ],
)
def test_a_request_to_remember_a_plain_fact_refuses_the_forget_tool(query: str) -> None:
    assert unasked_forget(query) == {FORGET_CHOSEN_TOOL_NAME}


@pytest.mark.parametrize(
    "query",
    [
        "Remember that my new locker code is 8426, and forget the old code.",
        "Note that I want you to forget the PIN.",
        "Please don't forget to forget my PIN.",
        "Note my new number 555 and erase the entry for 554",
        "Remember that I unlearned the code 7319, so should you.",
        "Note that my phone number is now 0699, and delete the entry for 0612.",
        "Keep in mind that the PIN is out of date, so remove the entry.",
        "Remember the code 7319 and wipe the PIN.",
        "Note that the PIN is stale and you can drop the entry.",
        "Remember this: clear the entry for my PIN.",
        "Remember this: purge the entry for my PIN.",
        "Note that the PIN is stale, discard the entry.",
        "Note that the PIN is stale, scrub the entry.",
        "Note that the PIN is stale, ditch the entry.",
        "Note that the PIN is stale, scrap the entry.",
        "Note that the PIN is stale, toss the entry.",
        "Note that the PIN is stale, trash the entry.",
        "Remember: get rid of the entry with my PIN.",
        "Remember that you can lose the entry about my PIN.",
        "Remember that you should stop storing my PIN.",
        "Remember this: undo what I said about my PIN.",
        "Note that I retract what I said about my PIN.",
        "Note that I revoke what I said about my PIN.",
        "Note that I withdraw what I said about my PIN.",
        "Keep in mind that you should ignore my last message.",
        "Keep in mind that you should disregard my last message.",
        "Remember to pretend I said a different PIN.",
        "Keep in mind that I regret telling you my PIN.",
        "Note that my PIN was told by mistake.",
        "Note that my PIN was told by accident.",
        "Note that the PIN you hold is wrong.",
        "Note that I take back what I said about my PIN.",
        "Remember the code 8426 and replace the PIN entry.",
        "Remember that I no longer want my PIN stored.",
        "Remember this: never mind my PIN.",
        "Remember this: none of my PIN entries are right.",
        "Remember this: nothing about my PIN stays.",
        "Remember that I would rather you kept less about my PIN.",
        "Note that the new PIN is 8426, the old one can go.",
        "Note that the new PIN is 8426, the previous one can go.",
        "Note that the new PIN is 8426, the former one can go.",
        "Note that the new PIN is 8426, the outdated one can go.",
        "Note this: I don't want my PIN in your memory.",
        "Note this: I don\u2019t want my PIN in your memory.",
        "Note this: I dont want my PIN in your memory.",
        "Remember, I said you wouldnt need my PIN.",
        "Remember that you cant use my PIN.",
        "Remember that you wont need my PIN.",
        "Remember that you shouldnt have my PIN.",
        "Remember that I didnt mean to send my PIN.",
        "Remember my PIN? Let it go.",
        "Please remember this: my new PIN is 1234. Let the last one go.",
        "Please remember this: my new PIN is 1234! Let the last one go.",
        "Please remember this: my PIN is 5521. Vergeet de oude.",
        "Please remember this: my new PIN is 1234\nLet the last one go",
        "Remember my new locker code is 5555 and nuke 8426.",
        "Remember my new locker code is 5555 and kill 8426.",
        "Remember my code is 5555 and destroy the PIN.",
        "Remember my code is 5555 and shred the PIN.",
        "Remember my code is 5555 and dump the PIN.",
        "Remember my code is 5555 and expunge the PIN.",
        "Remember my code is 5555 and overwrite 8426.",
        "Remember my code is 5555 and cancel 8426.",
        "Remember my code is 5555, scratch that.",
        "Remember my code is 5555 and strike 8426.",
        "Remember my code is 5555 and cross out 8426.",
        "Remember my code is 5555 and throw away 8426.",
        "Remember my code is 5555 and throw out 8426.",
        "Remember my code is 5555 and dispose of 8426.",
        "Remember my code is 5555 and blank 8426.",
        "Remember my code is 5555 and reset 8426.",
        "Remember my code is 5555 and clean up 8426.",
        "Remember my code is 5555, update what you have.",
        "Remember my code changed from 8426 to 5555.",
        "Remember my code is 5555, correct what you have.",
        "Remember my code is 5555 instead of 8426.",
        "Remember 5555 is my code, 8426 was the earlier one.",
        "Remember 5555 is my code, 8426 was the prior one.",
        "Remember my code is 5555 and 8426 is obsolete.",
        "Remember my code is 5555 and 8426 is stale.",
        "Remember my code is 5555 and 8426 is gone.",
        "Remember my PIN is 5521, nevermind.",
        "Remember to unsave my code.",
        "Remember to unremember my code.",
        "Remember to unstore my code.",
        "Remember my code is 5555 and let go of 8426.",
        "Remember, make my code go away.",
        "Note that I want it out of your memory.",
        "Remember my PIN and then get it out of your head.",
        "Remember I used to use 8426.",
        "Keep in mind that 8426 must go.",
        "Remember to nuke my locker code.",
        "Remember my code is 5555 and zap 8426.",
        "Remember my code is 5555 and bin the PIN.",
        "Remember my code is 5555; del 8426.",
        "Remember my code is 5555, rm 8426.",
        "Don't forget to zap it.",
        "Don't forget that I asked you to nuke my code.",
        "Remember: vergiss 8426.",
        "Remember: vergiss meine alte Nummer.",
        "Remember: vergessen meine Nummer.",
        "Remember: entferne meine Nummer.",
        "Remember: loesche meine Nummer.",
        "Remember: oublie mon code.",
        "Remember: efface mon code.",
        "Remember: olvida mi codigo.",
        "Remember: borra mi codigo.",
        "Remember: dimentica il mio codice.",
        "Remember: cancella il mio codice.",
        "Remember: vergeet mijn code.",
        "Remember: verwijder mijn code.",
        "Remember: l\u00f6sch meine Nummer.",
        "Remember: \u5fd8\u8bb0 8426",
        "Remember: 8426 \u3092\u5fd8\u308c\u3066",
        "Remember: \u0437\u0430\u0431\u0443\u0434\u044c 8426",
        "Remember: zap 8426.",
        "Remember my code is 5555 then zap 8426.",
        "Remember my code is 5555 and zap my PIN.",
        "Remember my code is 5555 and zap it.",
        "Remember my code is 5555 and zap this.",
        "Remember my code is 5555 and zap that.",
        "Remember my code is 5555 and zap those.",
        "Remember my code is 5555 and zap them.",
        "Remember my code is 5555 and zap what you hold.",
        "Remember my code is 5555 and zap everything.",
        *(f"Note that 8426 should be {word}." for word in _RETRACTED),
        "Note that I use 5555 instead.",
        "Note that you can let go of 8426.",
        "Note that 8426 should go away.",
        "Note that I want 8426 out of your memory.",
        "Note that I used to use 8426.",
        "Note that 8426 must go.",
        "Remember to zap my code.",
        "Don't forget to zap my code.",
    ],
)
def test_a_request_to_remember_that_can_also_ask_to_forget_keeps_the_forget_tool(
    query: str,
) -> None:
    assert asks_kept(query)
    assert not asks_not_kept(query)
    assert unasked_forget(query) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Remember that people just forget their PINs.",
        "Note that I erased notes.txt",
        "Keep in mind that my daughter is 3 years old.",
        "Remember that my bus stop is Central.",
        "Remember that I don't keep cash at home.",
        "Please remember, never keep the milk out of the fridge.",
        "Remember that I feed the cat and walk the dog.",
        "Remember that my landlord is Herr M\u00fcller.",
        "Note that my gym has clean towels.",
        "Note that my bank changed its opening hours.",
        "Remember to call Ana on Monday.",
    ],
)
def test_a_fact_holding_a_word_that_can_retract_only_keeps_the_forget_tool(query: str) -> None:
    assert asks_kept(query)
    assert unasked_forget(query) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "",
        "My brother's name is Luca.",
        "I shouldn't have told you my passport number X4821937.",
        "Vergeet alsjeblieft mijn pincode 5521.",
        "Bitte vergiss meine Passnummer X4821937.",
        "Don't save this anywhere, it's private: my PIN is 5521.",
        "Just between us, and not for your memory: my locker code is 7319.",
        "Forget that my passport number is X4821937.",
        "Unlearn my phone number 0612345678.",
        "Pretend I never told you that my sister's name is Ilinca.",
        "Remember my PIN 1234. Actually, forget it.",
        "Remember this, off the record: my PIN is 5521",
    ],
)
def test_a_message_that_is_no_plain_request_to_remember_keeps_the_forget_tool(query: str) -> None:
    assert unasked_forget(query) == frozenset()


class _Backend:
    """Keeps the tool names each request offered, and asks for ``calls`` in its first round."""

    def __init__(self, calls: Sequence[ToolCall] = ()) -> None:
        self.offered: list[list[str]] = []
        self.seen: list[Sequence[Message]] = []
        self._calls = list(calls)

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, schema, bounds
        self.offered.append([spec.name for spec in tools])
        self.seen.append(tuple(messages))
        calls, self._calls = self._calls, []
        for call in calls:
            yield call
        if not calls:
            yield TextChunk("noted")


def _dispatcher(ran: list[str], audit: RecordingAuditSink) -> ToolDispatcher:
    def tool(
        name: str, *, sidecar: bool = False
    ) -> tuple[ToolSpec, Callable[[Mapping[str, object]], Awaitable[str]]]:
        async def handler(arguments: Mapping[str, object]) -> str:
            del arguments
            ran.append(name)
            return "done"

        return ToolSpec(name=name, description=name, parameters={}, sidecar=sidecar), handler

    names = (SET_VOLUME_TOOL_NAME, SCHEDULE_TOOL_NAME, "look")
    tools = {name: tool(name) for name in names}
    tools[_FILE_TOOLS[0]] = tool(_FILE_TOOLS[0], sidecar=True)
    return ToolDispatcher(InMemoryToolRegistry(tools), audit, TickingClock())


async def _turn(text: str, backend: _Backend) -> tuple[list[str], RecordingAuditSink]:
    ran: list[str] = []
    audit = RecordingAuditSink()
    engine = TurnEngine(
        InMemorySessionStore(),
        backend,
        TickingClock(),
        capabilities=TurnCapabilities(tools=_dispatcher(ran, audit)),
    )
    async for _event in engine.handle_turn("s", text, turn_id="t"):
        pass
    return ran, audit


async def test_a_turn_that_asks_to_remember_a_fact_is_offered_neither_tool() -> None:
    backend = _Backend()
    await _turn("Please remember this: I work as a nurse.", backend)
    assert backend.offered == [["look", _FILE_TOOLS[0]]]


async def test_a_turn_that_asks_to_remember_and_for_the_sound_is_offered_the_volume() -> None:
    backend = _Backend()
    await _turn("Please remember this: I am hard of hearing. Set the volume to 80%.", backend)
    assert backend.offered == [[SET_VOLUME_TOOL_NAME, "look", _FILE_TOOLS[0]]]


async def test_a_turn_that_asks_to_remember_and_about_a_folder_is_offered_the_file_tool() -> None:
    backend = _Backend()
    await _turn(_REMEMBER_AND_ASK, backend)
    assert backend.offered == [["look", _FILE_TOOLS[0]]]


async def test_a_file_tool_a_turn_asked_about_runs_when_called() -> None:
    backend = _Backend([ToolCall(id="c1", name=_FILE_TOOLS[0], arguments={})])
    ran, audit = await _turn(_REMEMBER_AND_ASK, backend)
    assert ran == [_FILE_TOOLS[0]]
    assert [record.ok for record in audit.records] == [True]


async def test_a_sidecar_tool_called_by_name_is_refused_and_leaves_the_turn_untainted() -> None:
    ran: list[str] = []
    audit = RecordingAuditSink()
    taint = TaintLedger()
    backend = _Backend([ToolCall(id="c1", name=_FILE_TOOLS[0], arguments={})])
    context = ToolLoopContext(
        dispatcher=_dispatcher(ran, audit),
        clock=TickingClock(),
        turn_id="t",
        taint=taint,
        nonce="n",
        session_id="s",
        query=_REMEMBER_A_FACT,
    )
    working = [Message(role=Role.USER, text=_REMEMBER_A_FACT, at=_AT, turn_id="t")]
    events = [event async for event in stream_tool_loop(backend, "m", working, context)]
    assert ran == []
    assert taint.tainted is False
    assert events == ["noted"]
    assert UNASKED_MSG in backend.seen[1][-1].text
    (refused,) = audit.records
    assert (refused.name, refused.ok, refused.detail) == (_FILE_TOOLS[0], False, UNASKED_MSG)


async def test_an_unasked_tool_called_by_name_is_refused_and_never_runs() -> None:
    call = ToolCall(id="c1", name=SET_VOLUME_TOOL_NAME, arguments={"level": 0.5})
    backend = _Backend([call, ToolCall(id="c2", name="look", arguments={})])
    ran, audit = await _turn("Please remember this: I work as a nurse.", backend)
    assert ran == ["look"]
    refused, looked = audit.records
    assert (refused.name, refused.ok, refused.detail) == (SET_VOLUME_TOOL_NAME, False, UNASKED_MSG)
    assert looked.ok
    assert UNASKED_MSG in backend.seen[1][-2].text


async def test_a_request_to_remember_whose_file_call_was_refused_still_stores_the_fact() -> None:
    store = InMemoryMemoryStore()
    ran: list[str] = []
    backend = _Backend([ToolCall(id="c1", name=_FILE_TOOLS[0], arguments={})])
    caps = TurnCapabilities(
        memory=MemoryRecaller(store, HashEmbedder(), SystemClock()),
        tools=_dispatcher(ran, RecordingAuditSink()),
    )
    engine = TurnEngine(InMemorySessionStore(), backend, TickingClock(), capabilities=caps)
    async for _event in engine.handle_turn("s", _REMEMBER_A_FACT, turn_id="t"):
        pass
    assert ran == []
    (kept,) = await store.search(await HashEmbedder().embed("peanuts"), k=5)
    assert "peanuts" in kept.record.text


async def test_the_deep_phase_refuses_a_tool_its_request_to_remember_did_not_ask_for() -> None:
    sessions = InMemorySessionStore()
    text = "Please remember this: I work as a nurse."
    await sessions.append(
        harness.SESSION, Message(role=Role.USER, text=text, at=_AT, turn_id=harness.TURN)
    )
    ran: list[str] = []
    audit = RecordingAuditSink()
    backend = ScriptedBrainBackend(
        chunks=("done",),
        tool_calls=(ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments={}),),
    )
    caps = TurnCapabilities(tools=_dispatcher(ran, audit))
    phase = BrainPhase(sessions, backend, TickingClock(), "brain", caps, NO_CADENCE_TERMS)
    record = harness.prepared_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    events = phase.run(record)
    try:
        async for _event in events:
            pass
    finally:
        await events.aclose()
    (refused,) = audit.records
    assert (refused.name, refused.detail) == (SCHEDULE_TOOL_NAME, UNASKED_MSG)
    assert ran == []


async def test_the_deep_phase_refuses_a_sidecar_tool_its_request_did_not_ask_for() -> None:
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION,
        Message(role=Role.USER, text=_REMEMBER_A_FACT, at=_AT, turn_id=harness.TURN),
    )
    ran: list[str] = []
    audit = RecordingAuditSink()
    backend = ScriptedBrainBackend(
        chunks=("done",),
        tool_calls=(ToolCall(id="c1", name=_FILE_TOOLS[0], arguments={}),),
    )
    caps = TurnCapabilities(tools=_dispatcher(ran, audit))
    phase = BrainPhase(sessions, backend, TickingClock(), "brain", caps, NO_CADENCE_TERMS)
    record = harness.prepared_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    events = phase.run(record)
    try:
        async for _event in events:
            pass
    finally:
        await events.aclose()
    (refused,) = audit.records
    assert (refused.name, refused.detail) == (_FILE_TOOLS[0], UNASKED_MSG)
    assert ran == []
