"""The ``forget_untrusted_memories`` built-in: the person's way out of a recall-tainted block."""

from cortex_core.errors import MemoryStoreError, PartialDeleteError
from cortex_core.ports import MemoryStore
from cortex_core.scope import MemoryScope
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

FORGET_UNTRUSTED_TOOL_NAME = "forget_untrusted_memories"

FORGET_CARD = (
    "Deletes for good, with no undo, every remembered exchange that this chat can recall and "
    "that was derived from untrusted content such as a file or an email. Other memories stay."
)


class UntrustedMemoryForget:
    """The one memory delete a tool reaches: the tainted memories a session's recall reads."""

    def __init__(self, store: MemoryStore, scope: MemoryScope) -> None:
        self._store = store
        self._scope = scope

    async def forget(self, session_id: str) -> int:
        """Delete every tainted memory ``session_id`` can recall; return how many were removed."""
        return await self._store.delete_tainted(scopes=self._scope.read_scopes(session_id))

    async def any_to_forget(self, session_id: str) -> bool:
        """Whether ``session_id`` can recall at least one tainted memory."""
        return await self._store.count_tainted(scopes=self._scope.read_scopes(session_id)) > 0


class ForgetUntrustedTool:
    """Built-in ``forget_untrusted_memories``: delete the tainted memories a chat can recall."""

    def __init__(self, memory: UntrustedMemoryForget) -> None:
        self._memory = memory

    @property
    def spec(self) -> ToolSpec:
        """Takes no arguments, so nothing the model writes reaches the card or the delete."""
        return ToolSpec(
            name=FORGET_UNTRUSTED_TOOL_NAME,
            description=(
                "Forget every remembered exchange that was derived from untrusted content (a "
                "file, an email), so later messages no longer recall it. Call it only when the "
                "user asks to forget such memories, for example after an action was blocked "
                "because of one."
            ),
            parameters={"type": "object", "properties": {}},
            confirm_required=True,
        )

    async def offered(self, session_id: str) -> bool:
        """Offer the tool only to a chat that can recall a tainted memory, or when no count came."""
        try:
            return await self._memory.any_to_forget(session_id)
        except MemoryStoreError:
            return True

    async def card(self, call: ToolCall) -> str:
        """The confirmation card's text, written here and never by the model."""
        del call
        return FORGET_CARD

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delete the tainted memories the calling session can recall, and say how many."""
        try:
            removed = await self._memory.forget(call.stamp.session_id)
        except PartialDeleteError as err:
            return ToolResult(
                call_id=call.id,
                content=(
                    f"forgot {err.removed} remembered exchanges derived from untrusted content, "
                    f"then the memory store failed, so the forget did not finish and more may "
                    f"remain: {err}"
                ),
                is_error=True,
                trust=Trust.TRUSTED,
            )
        except MemoryStoreError as err:
            return ToolResult(
                call_id=call.id,
                content=f"the memory store is unavailable, so nothing was forgotten: {err}",
                is_error=True,
                trust=Trust.TRUSTED,
            )
        return ToolResult(
            call_id=call.id,
            content=(
                f"forgot {removed} remembered exchanges derived from untrusted content. An "
                "action blocked because of them can run when the user asks for it in a new message."
            ),
            trust=Trust.TRUSTED,
        )
