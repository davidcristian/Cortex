"""The ``forget_memories`` built-in: delete the remembered exchanges that contain a named text."""

from collections.abc import Sequence

from cortex_core.errors import MemoryStoreError
from cortex_core.memory import MemoryRecord
from cortex_core.ports import MemoryStore
from cortex_core.scope import MemoryScope
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

FORGET_CHOSEN_TOOL_NAME = "forget_memories"

FORGET_CHOSEN_LIMIT = 20
_EXCERPT_CHARS = 60
_PENDING_CALLS = 32

_NONE_FOUND = (
    "nothing was forgotten: no remembered exchange contains that text, so tell the user that "
    "nothing about it was stored, and do not ask the user for the value"
)

FORGET_NOT_KEPT_NOTE = (
    "Nothing in this message is kept in memory, because it asked to forget something, so do not "
    "say that anything in it was noted, saved or remembered. If it also asked you to remember "
    "anything else, say that it was not kept and ask the user to send it again in a message of "
    "its own."
)


def _text(call: ToolCall) -> str:
    """The text the call names, stripped; empty when the argument is missing or not a string."""
    value = call.arguments.get("text")
    return value.strip() if isinstance(value, str) else ""


def _excerpt(record: MemoryRecord, text: str) -> str:
    """One line of ``record`` around the first place it contains ``text``."""
    flat = " ".join(record.text.split())
    start = max(flat.lower().find(" ".join(text.lower().split())) - _EXCERPT_CHARS, 0)
    end = start + 2 * _EXCERPT_CHARS + len(text)
    return ("..." if start else "") + flat[start:end] + ("..." if end < len(flat) else "")


class ForgetChosenTool:
    """Built-in ``forget_memories``: find the memories holding a text, list them, delete them."""

    def __init__(self, store: MemoryStore, scope: MemoryScope) -> None:
        self._store = store
        self._scope = scope
        self._shown: dict[str, tuple[str, ...] | str] = {}

    @property
    def result_note(self) -> str:
        """The note the dispatcher ends every result of a call to this tool with, run or not."""
        return FORGET_NOT_KEPT_NOTE

    @property
    def spec(self) -> ToolSpec:
        """One argument: the literal text every memory to delete contains."""
        return ToolSpec(
            name=FORGET_CHOSEN_TOOL_NAME,
            description=(
                "Delete from memory every remembered exchange that contains a given text, so no "
                "later chat recalls it. Call it whenever the user asks you to forget, delete or "
                "remove something from your memory, and never say something was forgotten unless "
                "this tool reported it. Pass the value itself when you know it, such as the "
                "number. When you do not, pass one word from the request that names it, such as "
                '"passport", and never ask the user to type the value: the user sees every match '
                "before anything is deleted."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The value, or one word from the request that names it.",
                    }
                },
                "required": ["text"],
            },
            confirm_required=True,
            private_arguments=True,
        )

    async def _found(self, call: ToolCall) -> Sequence[MemoryRecord]:
        """The memories the calling session can recall that contain the call's text."""
        return await self._store.find_text(
            _text(call),
            limit=FORGET_CHOSEN_LIMIT + 1,
            scopes=self._scope.read_scopes(call.stamp.session_id),
        )

    async def card(self, call: ToolCall) -> str | None:
        """List the stored memories the delete will remove; ``None`` when it removes none."""
        shown, card = await self._choose(call)
        self._shown[call.id] = shown
        while len(self._shown) > _PENDING_CALLS:
            del self._shown[next(iter(self._shown))]
        return card

    async def _choose(self, call: ToolCall) -> tuple[tuple[str, ...] | str, str | None]:
        """The ids to delete and the card listing them, or why nothing will be and no card."""
        if not _text(call):
            return "nothing was forgotten: the call named no text", None
        try:
            found = await self._found(call)
        except MemoryStoreError as err:
            return f"the memory store is unavailable, so nothing was forgotten: {err}", None
        if len(found) > FORGET_CHOSEN_LIMIT:
            return (
                f"nothing was forgotten: more than {FORGET_CHOSEN_LIMIT} remembered exchanges "
                "contain that text, so ask the user for a longer, more exact text"
            ), None
        if not found:
            return _NONE_FOUND, None
        lines = "\n".join(f"- {_excerpt(record, _text(call))}" for record in found)
        card = f"Deletes for good, with no undo, these {len(found)} remembered exchanges:\n{lines}"
        return tuple(record.id for record in found), card

    def _result(self, call: ToolCall, content: str, *, error: bool = True) -> ToolResult:
        """The call's result: ``content`` as one sentence."""
        return ToolResult(
            call_id=call.id,
            content=f"{content}.",
            is_error=error,
            trust=Trust.TRUSTED,
            matched_nothing=content == _NONE_FOUND,
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delete exactly the memories the card listed, then say whether any still match."""
        shown = self._shown.pop(call.id, None)
        if shown is None:
            return self._result(call, "nothing was forgotten: no card listed what to delete")
        if isinstance(shown, str):
            return self._result(call, shown, error=shown != _NONE_FOUND)
        try:
            removed = await self._store.delete_ids(shown)
            left = await self._found(call)
        except MemoryStoreError as err:
            return self._result(call, f"the memory store failed during the forget: {err}")
        if left:
            return self._result(
                call,
                f"forgot {removed} remembered exchanges, but {len(left)} written since the "
                "card was shown still contain that text, so it is not forgotten",
            )
        return self._result(
            call,
            f"forgot {removed} remembered exchanges; no remembered exchange contains that text now",
            error=False,
        )
