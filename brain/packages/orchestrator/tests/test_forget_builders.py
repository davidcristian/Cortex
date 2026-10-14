from datetime import UTC, datetime

from cortex_core import (
    FORGET_CARD,
    FORGET_UNTRUSTED_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    GLOBAL_SCOPE,
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
