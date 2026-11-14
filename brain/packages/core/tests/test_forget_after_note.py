from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import pytest
from swap_harness import TickingClock

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GenerationBounds,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    RecordingAuditSink,
    Role,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.dispatch import UNASKED_MSG
from cortex_core.forget_claim import UNFORGOTTEN_CLAIM_NOTE, UNFORGOTTEN_CLAIM_NOTES
from cortex_core.forget_uncalled import UNCALLED_FORGET_NOTES
from cortex_core.forget_unnamed import kept_note
from cortex_core.forget_unrequested import FORGET_UNREQUESTED_MSG
from cortex_core.turn_output import place_note

_CALL = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "code"})
_AT = datetime(2026, 1, 1, tzinfo=UTC)


class _Backend:
    def __init__(self) -> None:
        self._calls = [_CALL]

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
        calls, self._calls = self._calls, []
        for call in calls:
            yield call
        if not calls:
            yield TextChunk("Noted.")


def _with_notes(text: str, *notes: str) -> str:
    parts = [text]
    for note in notes:
        parts.append(place_note(parts, note))
    return "".join(parts)


async def _details(asked: str, reply: str, query: str) -> list[str]:
    async def forget(arguments: Mapping[str, object]) -> str:
        del arguments
        return "done"

    spec = ToolSpec(name=FORGET_CHOSEN_TOOL_NAME, description="", parameters={})
    audit = RecordingAuditSink()
    registry = InMemoryToolRegistry({FORGET_CHOSEN_TOOL_NAME: (spec, forget)})
    tools = ToolDispatcher(registry, audit, TickingClock())
    sessions = InMemorySessionStore()
    await sessions.append("s", Message(role=Role.USER, text=asked, at=_AT, turn_id="t0"))
    await sessions.append("s", Message(role=Role.ASSISTANT, text=reply, at=_AT, turn_id="t0"))
    caps = TurnCapabilities(tools=tools)
    engine = TurnEngine(sessions, _Backend(), TickingClock(), capabilities=caps)
    _events = [event async for event in engine.handle_turn("s", query, turn_id="t1")]
    return [record.detail for record in audit.records]


_ASKED = "What is my locker code?"


@pytest.mark.parametrize(
    ("reply", "query", "refusal"),
    [
        (
            _with_notes("Your code is 7731.", UNFORGOTTEN_CLAIM_NOTE),
            "What is my locker code?",
            FORGET_UNREQUESTED_MSG,
        ),
        (
            _with_notes("Tu código es 7731.", UNFORGOTTEN_CLAIM_NOTES["es"]),
            "Recuerda que mi color favorito es el verde.",
            FORGET_UNREQUESTED_MSG,
        ),
        (
            _with_notes(
                "C'est noté.", UNCALLED_FORGET_NOTES["fr"], kept_note(["User: 7731"], "fr")
            ),
            "Souviens-toi que le code de mon casier est 7731.",
            FORGET_UNREQUESTED_MSG,
        ),
        (_with_notes("", UNFORGOTTEN_CLAIM_NOTE), "Remember that my sister is vegan.", UNASKED_MSG),
        (
            _with_notes("I deleted your code.", UNFORGOTTEN_CLAIM_NOTE),
            "What is my locker code?",
            FORGET_UNREQUESTED_MSG,
        ),
        (
            _with_notes("He borrado tu código.", UNFORGOTTEN_CLAIM_NOTES["es"]),
            "Recuerda que mi color favorito es el verde.",
            FORGET_UNREQUESTED_MSG,
        ),
    ],
)
async def test_the_brains_note_in_the_last_reply_leaves_the_forget_refused(
    *, reply: str, query: str, refusal: str
) -> None:
    assert await _details(_ASKED, reply, query) == [refusal]


@pytest.mark.parametrize(
    ("reply", "query"),
    [
        ("Should I forget it?", "Yes, do it."),
        ("I deleted your code.", "What is my locker code?"),
        ("He borrado tu código.", "Recuerda que mi color favorito es el verde."),
    ],
)
async def test_a_reply_whose_own_text_names_a_delete_keeps_the_forget(
    *, reply: str, query: str
) -> None:
    assert await _details(_ASKED, reply, query) == ["done"]
