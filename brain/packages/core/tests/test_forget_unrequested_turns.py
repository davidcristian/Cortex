from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from swap_harness import TickingClock

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
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
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.dispatch import UNASKED_MSG
from cortex_core.forget_claim import UNFORGOTTEN_CLAIM_NOTE
from cortex_core.forget_unrequested import FORGET_UNREQUESTED_MSG
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_CALL = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "bike lock"})


class _Backend:
    def __init__(self, reply: str) -> None:
        self.seen: list[Sequence[Message]] = []
        self._calls = [_CALL]
        self._reply = reply

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema, bounds
        self.seen.append(tuple(messages))
        calls, self._calls = self._calls, []
        for call in calls:
            yield call
        if not calls:
            yield TextChunk(self._reply)


async def _turn(
    query: str, reply: str, store: InMemoryMemoryStore | None = None
) -> tuple[list[str], list[str], str]:
    ran: list[str] = []

    async def forget(arguments: Mapping[str, object]) -> str:
        del arguments
        ran.append(FORGET_CHOSEN_TOOL_NAME)
        return "done"

    spec = ToolSpec(name=FORGET_CHOSEN_TOOL_NAME, description="", parameters={})
    audit = RecordingAuditSink()
    tools = ToolDispatcher(
        InMemoryToolRegistry({FORGET_CHOSEN_TOOL_NAME: (spec, forget)}), audit, TickingClock()
    )
    memory = None if store is None else MemoryRecaller(store, HashEmbedder(), SystemClock())
    caps = TurnCapabilities(memory=memory, tools=tools)
    engine = TurnEngine(InMemorySessionStore(), _Backend(reply), TickingClock(), capabilities=caps)
    turn = engine.handle_turn("s", query, turn_id="t")
    shown = "".join([event.text async for event in turn if isinstance(event, TextDelta)])
    return ran, [record.detail for record in audit.records], shown


async def test_a_forget_on_a_question_is_refused_once_and_closes_the_reply_with_no_note() -> None:
    reply = "I don't have your bike lock code in my memory."
    ran, details, shown = await _turn("What is my bike lock code?", reply)
    assert (ran, details, shown) == ([], [FORGET_UNREQUESTED_MSG], reply)


async def test_a_forget_refused_on_a_question_asking_to_note_a_fact_keeps_the_fact() -> None:
    store = InMemoryMemoryStore()
    query = "Can you note that Anna likes plants?"
    ran, details, _shown = await _turn(query, "Noted: Anna likes plants.", store)
    assert (ran, details) == ([], [FORGET_UNREQUESTED_MSG])
    (kept,) = await store.search(await HashEmbedder().embed("Anna plants"), k=5)
    assert "Anna likes plants" in kept.record.text


async def test_a_plain_fact_to_remember_keeps_its_own_single_refusal() -> None:
    _ran, details, _shown = await _turn("Remember that my sister is vegan.", "Noted.")
    assert details == [UNASKED_MSG]


@pytest.mark.parametrize(
    ("reply", "note"),
    [
        ("I have removed your bike lock code from my memory.", UNFORGOTTEN_CLAIM_NOTE),
        ("Your bike lock code is not stored.", ""),
    ],
)
async def test_a_reply_after_an_unrequested_forget_gets_only_a_true_note(
    *, reply: str, note: str
) -> None:
    _ran, _details, shown = await _turn("What is my bike lock code?", reply)
    assert shown == reply + note


async def test_a_forget_on_a_message_that_asks_to_forget_still_runs() -> None:
    ran, details, _shown = await _turn("Forget my bike lock code.", "Done.")
    assert (ran, details) == ([FORGET_CHOSEN_TOOL_NAME], ["done"])


class _Script:
    def __init__(self, rounds: Sequence[Sequence[InferenceEvent]]) -> None:
        self._rounds = list(rounds)

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
        for event in self._rounds.pop(0):
            yield event


_ANSWER = "What about the first one?"


async def _chat(queries: Sequence[str], replies: Sequence[str]) -> list[str]:
    ran: list[str] = []

    async def forget(arguments: Mapping[str, object]) -> str:
        del arguments
        ran.append(FORGET_CHOSEN_TOOL_NAME)
        return "done"

    spec = ToolSpec(name=FORGET_CHOSEN_TOOL_NAME, description="", parameters={})
    registry = InMemoryToolRegistry({FORGET_CHOSEN_TOOL_NAME: (spec, forget)})
    tools = ToolDispatcher(registry, RecordingAuditSink(), TickingClock())
    asked = [[TextChunk(reply)] for reply in replies]
    backend = _Script([*asked, [_CALL], [TextChunk("Done.")]])
    engine = TurnEngine(
        InMemorySessionStore(), backend, TickingClock(), capabilities=TurnCapabilities(tools=tools)
    )
    for turn, query in enumerate(queries):
        _events = [event async for event in engine.handle_turn("s", query, turn_id=f"t{turn}")]
    return ran


async def _answer(first: str, second: str) -> list[str]:
    return await _chat((first, second), ["You have two numbers stored. Which one do you mean?"])


async def test_an_answer_to_a_question_about_a_forget_runs_the_forget() -> None:
    assert await _answer("Forget my phone number.", _ANSWER) == [FORGET_CHOSEN_TOOL_NAME]


async def test_an_answer_to_a_question_about_a_lookup_refuses_the_forget() -> None:
    assert await _answer("What is my phone number?", _ANSWER) == []


async def test_a_statement_two_exchanges_after_a_forget_runs_the_forget() -> None:
    queries = ("Cancel the code I gave you.", "The alarm one.", "My alarm code is 5528.")
    replies = ["Which code is it?", "Which alarm code is it?"]
    assert await _chat(queries, replies) == [FORGET_CHOSEN_TOOL_NAME]


async def test_a_statement_after_a_courtesy_question_refuses_the_forget() -> None:
    queries = ("Hi! How are you today?", "My locker code at the pool is 7319.")
    replies = ["I'm doing well, thank you for asking! How can I help you today?"]
    assert await _chat(queries, replies) == []


async def test_a_statement_three_exchanges_after_a_forget_refuses_the_forget() -> None:
    queries = ("Cancel the code I gave you.", "Thanks.", "Hello again.", "My alarm code is 5528.")
    replies = ["Which code is it?", "You're welcome. Anything else?", "Hi! How can I help you?"]
    assert await _chat(queries, replies) == []


def _said(role: Role, text: str, turn_id: str) -> Message:
    return Message(role=role, text=text, at=datetime(2026, 11, 13, tzinfo=UTC), turn_id=turn_id)


async def _handoff(exchanges: Sequence[tuple[str, str]], query: str) -> list[str]:
    calls: list[str] = []

    async def forget(arguments: Mapping[str, object]) -> str:
        del arguments
        calls.append(FORGET_CHOSEN_TOOL_NAME)
        return "done"

    spec = ToolSpec(name=FORGET_CHOSEN_TOOL_NAME, description="", parameters={})
    registry = InMemoryToolRegistry({FORGET_CHOSEN_TOOL_NAME: (spec, forget)})
    tools = ToolDispatcher(registry, RecordingAuditSink(), TickingClock())
    earlier = [
        _said(role, text, f"t{turn}")
        for turn, exchange in enumerate(exchanges)
        for role, text in zip((Role.USER, Role.ASSISTANT), exchange, strict=True)
    ]
    escalate = ToolCall(id="e1", name="escalate", arguments={})
    working = [
        *earlier,
        _said(Role.USER, query, "now"),
        replace(_said(Role.ASSISTANT, "", "now"), tool_calls=(escalate,)),
        replace(_said(Role.TOOL, "taken", "now"), tool_call_id="e1"),
    ]
    context = ToolLoopContext(
        dispatcher=tools,
        clock=TickingClock(),
        turn_id="now",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
        query=query,
    )
    backend = _Script([[_CALL], [TextChunk("Done.")]])
    _events = [event async for event in stream_tool_loop(backend, "m", working, context)]
    return calls


@pytest.mark.parametrize(
    ("first", "ran"),
    [("Cancel the code I gave you.", [FORGET_CHOSEN_TOOL_NAME]), ("Hello there.", [])],
)
async def test_a_handoff_reads_the_two_exchanges_before_its_own_turn(
    *, first: str, ran: list[str]
) -> None:
    exchanges = [(first, "Which code is it?"), ("The alarm one.", "Which alarm code is it?")]
    assert await _handoff(exchanges, "My alarm code is 5528.") == ran


@pytest.mark.parametrize(
    ("reply", "ran"),
    [("Should I forget it?", [FORGET_CHOSEN_TOOL_NAME]), ("Anything else?", [])],
)
@pytest.mark.parametrize(
    "query", ["My alarm code is 5528.", "Remember that my alarm code is 5528."]
)
async def test_a_handoff_reads_the_last_reply_before_its_own_turn(
    *, reply: str, ran: list[str], query: str
) -> None:
    exchanges = [("What do you have about my alarm?", f"Your alarm code is 4826. {reply}")]
    assert await _handoff(exchanges, query) == ran
