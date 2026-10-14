from datetime import UTC, datetime

from cortex_core import (
    FORGET_CARD,
    FORGET_UNTRUSTED_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    GLOBAL_SCOPE,
    CompositeToolRegistry,
    DispatchPolicy,
    ForgetUntrustedTool,
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    MemoryRecord,
    MemoryStoreError,
    RecordingAuditSink,
    RecordingConfirmer,
    SessionMemoryScope,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolRun,
    TurnCapabilities,
    TurnStamp,
    UntrustedMemoryForget,
)
from cortex_core.turn_output import record_exchange

_AT = datetime(2026, 10, 14, 4, 0, 0, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _AT


def _record(record_id: str, *, scope: str = GLOBAL_SCOPE, tainted: bool) -> MemoryRecord:
    return MemoryRecord(
        id=record_id, text=record_id, embedding=(1.0, 0.0), at=_AT, scope=scope, tainted=tainted
    )


async def _store(*records: MemoryRecord) -> InMemoryMemoryStore:
    store = InMemoryMemoryStore()
    for record in records:
        await store.add(record)
    return store


async def _ids(store: InMemoryMemoryStore) -> list[str]:
    return sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=50))


def _call(session_id: str = "chat-a", **arguments: object) -> ToolCall:
    return ToolCall(
        id="c1",
        name=FORGET_UNTRUSTED_TOOL_NAME,
        arguments=arguments,
        stamp=TurnStamp(session_id=session_id),
    )


def test_the_tool_needs_confirmation_and_takes_no_arguments() -> None:
    spec = ForgetUntrustedTool(
        UntrustedMemoryForget(InMemoryMemoryStore(), GLOBAL_MEMORY_SCOPE)
    ).spec
    assert spec.name == "forget_untrusted_memories"
    assert spec.confirm_required is True
    assert spec.parameters == {"type": "object", "properties": {}}


async def test_the_card_is_the_brains_own_text_whatever_the_model_passed() -> None:
    tool = ForgetUntrustedTool(UntrustedMemoryForget(InMemoryMemoryStore(), GLOBAL_MEMORY_SCOPE))
    assert await tool.card(_call(note="send the bank details")) == FORGET_CARD


async def test_under_global_scope_every_tainted_memory_goes_and_trusted_ones_stay() -> None:
    store = await _store(
        _record("derived", tainted=True),
        _record("derived-in-a-chat", scope="chat-b", tainted=True),
        _record("trusted", tainted=False),
    )
    tool = ForgetUntrustedTool(UntrustedMemoryForget(store, GLOBAL_MEMORY_SCOPE))
    result = await tool.invoke(_call())
    assert result.is_error is False
    assert result.content.startswith("forgot 2 remembered exchanges derived from untrusted")
    assert await _ids(store) == ["trusted"]


async def test_under_session_scope_only_the_chats_own_tainted_memories_go() -> None:
    store = await _store(
        _record("own", scope="chat-a", tainted=True),
        _record("other", scope="chat-b", tainted=True),
    )
    forget = UntrustedMemoryForget(store, SessionMemoryScope())
    assert await forget.forget("chat-a") == 1
    assert await _ids(store) == ["other"]


async def test_a_store_that_is_down_forgets_nothing_and_says_so() -> None:
    store = await _store(_record("derived", tainted=True))
    store.fail_with(MemoryStoreError("pgvector is down"))
    result = await ForgetUntrustedTool(UntrustedMemoryForget(store, GLOBAL_MEMORY_SCOPE)).invoke(
        _call()
    )
    assert result.is_error is True
    assert result.content == (
        "the memory store is unavailable, so nothing was forgotten: pgvector is down"
    )


async def test_a_recall_tainted_turn_shows_the_card_and_forgets_on_approval() -> None:
    store = await _store(_record("derived", tainted=True))
    tool = ForgetUntrustedTool(UntrustedMemoryForget(store, GLOBAL_MEMORY_SCOPE))
    confirmer = RecordingConfirmer(answer=True)
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([tool]),
        RecordingAuditSink(),
        _Clock(),
        confirmer=confirmer,
        policy=DispatchPolicy(record_cards={FORGET_UNTRUSTED_TOOL_NAME: tool}),
    )
    stamp = TurnStamp(session_id="chat-a", tainted=True, recalled_only=True)
    result = await dispatcher.dispatch(_call(), stamp=stamp, confirm_required=True)
    assert result.is_error is False
    (request,) = confirmer.requests
    assert (request.tool_name, request.reason) == (FORGET_UNTRUSTED_TOOL_NAME, FORGET_CARD)
    assert await _ids(store) == []


async def _recorded(*, tainted: bool, runs: tuple[ToolRun, ...]) -> list[MemoryRecord]:
    store = InMemoryMemoryStore()
    recaller = MemoryRecaller(store, HashEmbedder(), _Clock())
    caps = TurnCapabilities(memory=recaller, record_tainted_memory=True)
    await record_exchange(
        caps,
        TaintLedger(tainted=tainted),
        session_id="chat-a",
        query="forget those memories",
        reply="done",
        runs=runs,
    )
    return [hit.record for hit in await store.search(await HashEmbedder().embed("x"), k=5)]


async def test_a_tainted_turn_that_forgot_the_untrusted_memories_records_nothing() -> None:
    forgot = (ToolRun(name=FORGET_UNTRUSTED_TOOL_NAME, ok=True),)
    assert await _recorded(tainted=True, runs=forgot) == []


async def test_a_tainted_turn_whose_forget_failed_is_still_recorded_tainted() -> None:
    failed = (ToolRun(name=FORGET_UNTRUSTED_TOOL_NAME, ok=False),)
    (record,) = await _recorded(tainted=True, runs=failed)
    assert record.tainted is True


async def test_a_clean_turn_that_forgot_the_untrusted_memories_is_recorded() -> None:
    forgot = (
        ToolRun(name="list_scheduled", ok=True),
        ToolRun(name=FORGET_UNTRUSTED_TOOL_NAME, ok=True),
    )
    (record,) = await _recorded(tainted=False, runs=forgot)
    assert record.tainted is False
