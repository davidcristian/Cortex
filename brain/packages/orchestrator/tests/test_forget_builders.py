from datetime import UTC, datetime

from cortex_core import (
    ESCALATE_TOOL_NAME,
    FORGET_CARD,
    FORGET_CHOSEN_TOOL_NAME,
    FORGET_UNTRUSTED_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    GLOBAL_SCOPE,
    USER_DECLINED_MSG,
    ForgetChosenTool,
    InMemoryMemoryStore,
    MemoryRecord,
    RecordingConfirmer,
    SystemClock,
    ToolCall,
    ToolDispatcher,
    TurnStamp,
    UntrustedMemoryForget,
)
from cortex_orchestrator import build_builtin_tools, build_cortex_tools


def test_the_forget_tool_is_built_only_when_memory_is_wired() -> None:
    forget = UntrustedMemoryForget(InMemoryMemoryStore(), GLOBAL_MEMORY_SCOPE)
    names = [tool.spec.name for tool in build_builtin_tools(None, None, memory=forget)]
    assert names == [FORGET_UNTRUSTED_TOOL_NAME]
    assert build_builtin_tools(None, None) == []


def test_the_chosen_forget_tool_is_built_only_when_memory_is_wired() -> None:
    chosen = ForgetChosenTool(InMemoryMemoryStore(), GLOBAL_MEMORY_SCOPE)
    assert build_builtin_tools(None, None, chosen=chosen) == [chosen]


async def test_the_cortex_dispatcher_shows_the_chosen_rows_and_deletes_them_on_approval() -> None:
    store = InMemoryMemoryStore()
    at = datetime(2026, 10, 28, 5, 0, 0, tzinfo=UTC)
    for record_id, text in (("m1", "card 4242 4242"), ("m2", "wifi plum")):
        await store.add(MemoryRecord(id=record_id, text=text, embedding=(1.0,), at=at))
    confirmer = RecordingConfirmer(answer=True)
    chosen = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    tools = build_cortex_tools(
        None, build_builtin_tools(None, None, chosen=chosen), SystemClock(), confirmer=confirmer
    )
    assert isinstance(tools, ToolDispatcher)
    result = await tools.dispatch(
        ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "4242"}),
        stamp=TurnStamp(session_id="chat-a", tainted=True),
        confirm_required=True,
    )
    assert result.is_error is False
    assert [request.reason for request in confirmer.requests] == [
        "Deletes for good, with no undo, these 1 remembered exchanges:\n- card 4242 4242"
    ]
    assert [hit.record.id for hit in await store.search((1.0,), k=5)] == ["m2"]


async def test_the_cortex_dispatcher_shows_the_forget_card_on_a_recall_tainted_turn() -> None:
    store = InMemoryMemoryStore()
    at = datetime(2026, 10, 14, 4, 0, 0, tzinfo=UTC)
    await store.add(
        MemoryRecord(
            id="m1", text="quoted note", embedding=(1.0,), at=at, scope=GLOBAL_SCOPE, tainted=True
        )
    )
    confirmer = RecordingConfirmer(answer=True)
    builtins = build_builtin_tools(
        None, None, memory=UntrustedMemoryForget(store, GLOBAL_MEMORY_SCOPE)
    )
    tools = build_cortex_tools(None, builtins, SystemClock(), confirmer=confirmer)
    assert isinstance(tools, ToolDispatcher)
    (spec,) = await tools.describe_tools()
    result = await tools.dispatch(
        ToolCall(id="c1", name=FORGET_UNTRUSTED_TOOL_NAME, arguments={}),
        stamp=TurnStamp(session_id="chat-a", tainted=True, recalled_only=True),
        confirm_required=spec.confirm_required,
    )
    assert result.is_error is False
    assert [request.reason for request in confirmer.requests] == [FORGET_CARD]
    assert await store.count_candidates() == 0


async def test_a_built_in_missing_from_the_turns_list_still_shows_its_card() -> None:
    store = InMemoryMemoryStore()
    at = datetime(2026, 10, 26, 1, 0, 0, tzinfo=UTC)
    await store.add(
        MemoryRecord(
            id="m1", text="quoted note", embedding=(1.0,), at=at, scope=GLOBAL_SCOPE, tainted=True
        )
    )
    confirmer = RecordingConfirmer(answer=False)
    builtins = build_builtin_tools(
        None, None, escalation=True, memory=UntrustedMemoryForget(store, GLOBAL_MEMORY_SCOPE)
    )
    tools = build_cortex_tools(None, builtins, SystemClock(), confirmer=confirmer)
    assert isinstance(tools, ToolDispatcher)
    for name in (FORGET_UNTRUSTED_TOOL_NAME, ESCALATE_TOOL_NAME):
        result = await tools.dispatch(
            ToolCall(id=name, name=name, arguments={"reason": "deep"}),
            stamp=TurnStamp(session_id="chat-a"),
            confirm_required=False,
        )
        assert result.content == USER_DECLINED_MSG
    assert [request.tool_name for request in confirmer.requests] == [
        FORGET_UNTRUSTED_TOOL_NAME,
        ESCALATE_TOOL_NAME,
    ]
    assert await store.count_candidates() == 1


async def test_the_cortex_dispatcher_withholds_the_forget_from_a_chat_with_nothing_to_forget() -> (
    None
):
    store = InMemoryMemoryStore()
    builtins = build_builtin_tools(
        None, None, escalation=True, memory=UntrustedMemoryForget(store, GLOBAL_MEMORY_SCOPE)
    )
    tools = build_cortex_tools(None, builtins, SystemClock())
    assert isinstance(tools, ToolDispatcher)
    assert await tools.withheld("chat-a") == {FORGET_UNTRUSTED_TOOL_NAME}
    at = datetime(2026, 10, 26, 2, 0, 0, tzinfo=UTC)
    await store.add(
        MemoryRecord(
            id="m1", text="quoted note", embedding=(1.0,), at=at, scope=GLOBAL_SCOPE, tainted=True
        )
    )
    assert await tools.withheld("chat-a") == frozenset()
