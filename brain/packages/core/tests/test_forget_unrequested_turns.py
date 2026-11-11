from collections.abc import AsyncIterator, Mapping, Sequence

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
    SystemClock,
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
