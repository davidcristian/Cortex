import inspect
from collections.abc import Sequence

from cortex_core import (
    MemoryRecord,
    Message,
    ScoredMemory,
    SessionMemoryCascade,
    SessionMemoryScope,
    SessionStore,
    SessionSummary,
    ToolRegistry,
)
from cortex_core.sessions import HistoryRecap
from cortex_orchestrator import BrainService
from cortex_orchestrator.session_rpc import (
    MAX_TITLE_INPUT,
    clamp_title,
    delete_session,
    rename_session,
    set_session_pinned,
)
from cortex_seam import DeleteSessionReply, RenameSessionReply, SetSessionPinnedReply


class RecordingStore:
    """A SessionStore that records the `set_title` and `delete` writes it is asked to make."""

    def __init__(self, events: list[str] | None = None) -> None:
        self.set_title_calls: list[tuple[str, str]] = []
        self.delete_calls: list[str] = []
        self.set_pinned_calls: list[tuple[str, bool]] = []
        self.events = events if events is not None else []

    async def append(self, session_id: str, message: Message) -> None:
        del session_id, message

    async def history(self, session_id: str) -> Sequence[Message]:
        del session_id
        return ()

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        del limit
        return ()

    async def set_title(self, session_id: str, title: str) -> None:
        self.set_title_calls.append((session_id, title))

    async def delete(self, session_id: str) -> None:
        self.delete_calls.append(session_id)
        self.events.append(f"delete:{session_id}")

    async def set_pinned(self, session_id: str, *, pinned: bool) -> None:
        self.set_pinned_calls.append((session_id, pinned))

    async def set_recap(self, session_id: str, recap: HistoryRecap) -> None:
        del session_id, recap

    async def recap(self, session_id: str) -> HistoryRecap | None:
        del session_id
        return None


class RecordingMemoryStore:
    """A MemoryStore recording each `delete_scope`, so the real cascade's call is observable."""

    def __init__(self, events: list[str]) -> None:
        self.deleted_scopes: list[str] = []
        self.events = events

    async def add(self, record: MemoryRecord) -> None:
        del record

    async def search(
        self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
    ) -> Sequence[ScoredMemory]:
        del embedding, k, scopes
        return ()

    async def count_candidates(self, *, scopes: Sequence[str] | None = None) -> int:
        del scopes
        return 0

    async def delete_scope(self, scope: str) -> int:
        self.deleted_scopes.append(scope)
        self.events.append(f"cascade:{scope}")
        return 0


def test_clamp_title_passes_a_short_title_through_unchanged() -> None:
    assert clamp_title("Everything about cats") == "Everything about cats"


def test_clamp_title_keeps_an_empty_title_empty() -> None:
    assert clamp_title("") == ""


def test_clamp_title_bounds_an_overlong_title() -> None:
    bounded = clamp_title("x" * (MAX_TITLE_INPUT + 500))
    assert len(bounded) == MAX_TITLE_INPUT


async def test_rename_session_writes_the_clamped_title_via_set_title() -> None:
    store = RecordingStore()
    reply = await rename_session(store, "alpha", "y" * (MAX_TITLE_INPUT + 10))
    assert store.set_title_calls == [("alpha", "y" * MAX_TITLE_INPUT)]
    assert isinstance(reply, RenameSessionReply)


async def test_rename_session_passes_an_empty_title_to_clear_the_override() -> None:
    store = RecordingStore()
    await rename_session(store, "beta", "")
    assert store.set_title_calls == [("beta", "")]


async def test_delete_session_deletes_the_chat_then_cascades_to_memory() -> None:
    events: list[str] = []
    store = RecordingStore(events)
    mem = RecordingMemoryStore(events)
    cascade = SessionMemoryCascade(mem, SessionMemoryScope())
    reply = await delete_session(store, cascade, "gamma")
    assert isinstance(reply, DeleteSessionReply)
    assert store.delete_calls == ["gamma"]
    assert mem.deleted_scopes == ["gamma"]
    assert events == ["delete:gamma", "cascade:gamma"]


async def test_delete_session_skips_the_cascade_when_memory_is_off() -> None:
    store = RecordingStore()
    reply = await delete_session(store, None, "delta")
    assert isinstance(reply, DeleteSessionReply)
    assert store.delete_calls == ["delta"]


async def test_set_session_pinned_writes_the_pin_through_set_pinned() -> None:
    store = RecordingStore()
    pinned_reply = await set_session_pinned(store, "epsilon", pinned=True)
    assert isinstance(pinned_reply, SetSessionPinnedReply)
    await set_session_pinned(store, "epsilon", pinned=False)
    assert store.set_pinned_calls == [("epsilon", True), ("epsilon", False)]


def test_session_pinning_is_a_user_only_seam_path_never_a_tool() -> None:
    assert callable(BrainService.SetSessionPinned)
    assert callable(SessionStore.set_pinned)
    handler_params = set(inspect.signature(set_session_pinned).parameters)
    assert handler_params == {"store", "session_id", "pinned"}


def test_session_deletion_is_a_user_only_seam_path_never_a_tool() -> None:
    assert callable(BrainService.DeleteSession)
    assert callable(SessionStore.delete)
    tool_surface = {name for name in vars(ToolRegistry) if not name.startswith("_")}
    assert tool_surface == {"describe_tools", "invoke"}
    handler_params = set(inspect.signature(delete_session).parameters)
    assert handler_params == {"store", "cascade", "session_id"}
