"""Unit tests for the session-catalog RPC helpers (ADR-0021): the rename and delete writes.

The end-to-end handler wiring is covered over a real loopback server in `test_session_reads.py`;
these pin the pieces that live below the seam: the seam-edge title bound, that `rename_session`
writes the *clamped* title through `SessionStore.set_title`, and that `delete_session` deletes the
chat and cascades to its memories in the right order (so the mutation that drops the clamp, never
writes, skips the delete, or skips the cascade each reddens exactly one test here).
"""

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
    """A SessionStore that records the `set_title` and `delete` writes it is asked to make.

    Only the writes are exercised here; the reads satisfy the port but are never called. `events`
    keeps a global order so a test can assert the session is deleted before the memory cascade runs.
    """

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
    """A MemoryStore recording each `delete_scope`, so the real cascade's call is observable.

    Only `delete_scope` is exercised; `add`/`search` satisfy the port but are never called. Wrapping
    it in a real `SessionMemoryCascade` (rather than faking the cascade) keeps the scope guard live.
    """

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

    async def delete_scope(self, scope: str) -> int:
        self.deleted_scopes.append(scope)
        self.events.append(f"cascade:{scope}")
        return 0


def test_clamp_title_passes_a_short_title_through_unchanged() -> None:
    assert clamp_title("Everything about cats") == "Everything about cats"


def test_clamp_title_keeps_an_empty_title_empty() -> None:
    # "" is the clear-the-override signal and must survive the bound intact.
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
    # The whole point of the slice: the visible chat is deleted first, then its private memories
    # are forgotten. The shared `events` list pins that order (a mutation swapping them reddens).
    # A real SessionMemoryCascade under session scoping deletes the chat's own scope ("gamma").
    events: list[str] = []
    store = RecordingStore(events)
    mem = RecordingMemoryStore(events)
    cascade = SessionMemoryCascade(mem, SessionMemoryScope())
    reply = await delete_session(store, cascade, "gamma")
    assert isinstance(reply, DeleteSessionReply)
    assert store.delete_calls == ["gamma"]
    assert mem.deleted_scopes == ["gamma"]  # the cascade forgot the session's own scope
    assert events == ["delete:gamma", "cascade:gamma"]  # session first, then the cascade


async def test_delete_session_skips_the_cascade_when_memory_is_off() -> None:
    # No memory backend wired (`cascade is None`): the chat is deleted and nothing else is called,
    # so a memory-less deployment deletes cleanly with no cascade to run.
    store = RecordingStore()
    reply = await delete_session(store, None, "delta")
    assert isinstance(reply, DeleteSessionReply)
    assert store.delete_calls == ["delta"]


async def test_set_session_pinned_writes_the_pin_through_set_pinned() -> None:
    # The handler forwards the target state straight to `SessionStore.set_pinned` (a mutation that
    # drops the write, or inverts the flag, reddens here). Pinning then unpinning both cross.
    store = RecordingStore()
    pinned_reply = await set_session_pinned(store, "epsilon", pinned=True)
    assert isinstance(pinned_reply, SetSessionPinnedReply)
    await set_session_pinned(store, "epsilon", pinned=False)
    assert store.set_pinned_calls == [("epsilon", True), ("epsilon", False)]


def test_session_pinning_is_a_user_only_seam_path_never_a_tool() -> None:
    # Structural user-only gate (ADR-0021 pinning addendum), the same as rename/delete: pinning is
    # reached ONLY from the seam (`SessionStore.set_pinned`, driven by `set_session_pinned`,
    # driven by the `BrainService.SetSessionPinned` servicer the overlay calls out of band). A
    # model's whole reach is describe/invoke on the ToolRegistry, which carries no pin verb.
    assert callable(BrainService.SetSessionPinned)  # the user-only seam method exists
    assert callable(SessionStore.set_pinned)  # the store verb it drives, not a tool
    handler_params = set(inspect.signature(set_session_pinned).parameters)
    assert handler_params == {"store", "session_id", "pinned"}  # store port, no ToolRegistry


def test_session_deletion_is_a_user_only_seam_path_never_a_tool() -> None:
    # Structural user-only gate (ADR-0021), the same as RenameSession. Session deletion is reached
    # ONLY from the seam: the `SessionStore.delete` port verb, driven by `delete_session`
    # (which takes store ports, never a ToolRegistry), driven by the `BrainService.DeleteSession`
    # servicer method the overlay calls out of band behind the seam-token interceptor. A model's
    # ENTIRE reach into the system is the ToolRegistry surface, which is exactly describe_tools/
    # invoke and carries no delete verb; deletion is a store capability, not a tool, and never runs
    # through the turn engine. So no model, tool, or tainted turn can delete a chat. If deletion is
    # ever wired as a tool (a ToolRegistry verb, or `delete_session` taking one), this reddens.
    assert callable(BrainService.DeleteSession)  # the user-only seam method exists
    assert callable(SessionStore.delete)  # the store verb it drives, not a tool
    tool_surface = {name for name in vars(ToolRegistry) if not name.startswith("_")}
    assert tool_surface == {"describe_tools", "invoke"}  # a model can only describe/invoke tools
    handler_params = set(inspect.signature(delete_session).parameters)
    assert handler_params == {"store", "cascade", "session_id"}  # store ports, no ToolRegistry
