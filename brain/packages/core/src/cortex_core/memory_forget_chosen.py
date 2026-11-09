"""The ``forget_memories`` built-in: delete the remembered exchanges that contain a named text."""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from cortex_core.errors import MemoryStoreError
from cortex_core.forget_results import (
    ALREADY_DELETED,
    FORGET_CHOSEN_LIMIT,
    FORGET_NOT_KEPT_NOTE,
    LEFT_OUT_LINE,
    NONE_FOUND,
    TOO_MANY,
    outlasted,
    unavailable,
    unlisted,
)
from cortex_core.forget_unnamed import KEPT_ALL, KEPT_LINE, KeptRows, asks_to_keep, forgot, unnamed
from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import code_runs, digit_runs, value_searches, whole_values
from cortex_core.ports import MemoryStore
from cortex_core.scope import MemoryScope
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

FORGET_CHOSEN_TOOL_NAME = "forget_memories"

_EXCERPT_CHARS = 60
_PENDING_CALLS = 32
_TOKEN = re.compile(r"[^\W_]+")
_WORD = re.compile(r"[^\W\d_]{4,}")


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


def _tokens(text: str) -> set[str]:
    """The runs of letters and digits in ``text``, lower case."""
    return {token.lower() for token in _TOKEN.findall(text)}


def _flat(text: str) -> str:
    """``text`` in lower case with every run of white space one space."""
    return " ".join(text.lower().split())


def _values(records: Sequence[MemoryRecord]) -> dict[str, str]:
    """The whole values of ``records``, such as a code or a phone number, in order."""
    values: dict[str, str] = {}
    for record in records:
        for key, form in whole_values(record.text).items():
            values.setdefault(key, form)
    return values


def _repeats(record: MemoryRecord, key: str, words: set[str]) -> bool:
    """Whether ``record`` holds the whole value ``key`` and a word of ``words``, if any."""
    held = key in whole_values(record.text)
    return held and (not words or not _tokens(record.text).isdisjoint(words))


def _about(text: str, deleted: tuple[str, ...]) -> bool:
    """Whether ``text`` names what a deleted row or the text that deleted it held."""
    asked, keys = _flat(text), whole_values(text).keys()
    return any(
        asked in _flat(held) or _flat(held) in asked or not keys.isdisjoint(whole_values(held))
        for held in deleted
    )


@dataclass(frozen=True)
class _Chosen:
    """The rows a card listed by id and text, whether rows holding a value stayed, the rows kept."""

    ids: tuple[str, ...]
    texts: tuple[str, ...]
    left_out: bool
    kept: frozenset[str] = frozenset()


class ForgetChosenTool:
    """Built-in ``forget_memories``: find the memories holding a text, list them, delete them."""

    def __init__(self, store: MemoryStore, scope: MemoryScope) -> None:
        self._store = store
        self._scope = scope
        self._shown: dict[str, _Chosen | str] = {}
        self._deleted_turns: dict[str, tuple[str, ...]] = {}
        self._deleted_rows: dict[str, tuple[str, ...]] = {}
        self._kept = KeptRows()
        self._spared = KeptRows()

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

    async def _repeating(
        self, call: ToolCall, found: Sequence[MemoryRecord]
    ) -> list[tuple[MemoryRecord, str, str]]:
        """Other memories holding a value of ``found`` and a word of the call or the value named."""
        words = {word.lower() for word in _WORD.findall(_text(call))}
        named = whole_values(_text(call)).keys()
        seen = {record.id for record in found}
        extra: list[tuple[MemoryRecord, str, str]] = []
        values = [(key, form) for key, form in _values(found).items() if words or key in named]
        for key, form in values:
            for search in value_searches(key, form):
                for record in await self._store.find_text(
                    search,
                    limit=FORGET_CHOSEN_LIMIT + 1,
                    scopes=self._scope.read_scopes(call.stamp.session_id),
                ):
                    if record.id not in seen and _repeats(record, key, words):
                        seen.add(record.id)
                        extra.append((record, form, whole_values(record.text)[key]))
        return extra

    async def _holding(self, call: ToolCall) -> int:
        """How many remaining rows not asked to keep hold four or more digits a deleted row held."""
        deleted = self._deleted_rows.get(call.stamp.turn_id, ())
        runs = {key: form for text in deleted for key, form in code_runs(text).items()}
        holders: set[str] = set()
        for search in {text for key, form in runs.items() for text in value_searches(key, form)}:
            for record in await self._store.find_text(
                search,
                limit=FORGET_CHOSEN_LIMIT + 1,
                scopes=self._scope.read_scopes(call.stamp.session_id),
            ):
                held = not runs.keys().isdisjoint(digit_runs(record.text))
                if held and not asks_to_keep(record.text, call.stamp.query):
                    holders.add(record.id)
        return len(holders)

    async def card(self, call: ToolCall) -> str | None:
        """List the stored memories the delete will remove; ``None`` when it removes none."""
        shown, card = await self._choose(call)
        self._shown[call.id] = shown
        while len(self._shown) > _PENDING_CALLS:
            del self._shown[next(iter(self._shown))]
        return card

    async def _choose(self, call: ToolCall) -> tuple[_Chosen | str, str | None]:
        """The rows to delete and the card listing them, or why nothing will be and no card."""
        if not _text(call):
            return "nothing was forgotten: the call named no text", None
        try:
            found = await self._found(call)
            extra = await self._repeating(call, found) if len(found) <= FORGET_CHOSEN_LIMIT else []
        except MemoryStoreError as err:
            return unavailable(err), None
        if len(found) > FORGET_CHOSEN_LIMIT:
            return TOO_MANY, None
        if not found:
            deleted = self._deleted_turns.get(call.stamp.turn_id, ())
            return (ALREADY_DELETED if _about(_text(call), deleted) else NONE_FOUND), None
        left_out = len(found) + len(extra) > FORGET_CHOSEN_LIMIT
        rows = [*found, *(row for row, _, _ in extra)]
        deleted = self._deleted_rows.get(call.stamp.turn_id, ())
        kept = unnamed(rows, _text(call), call.stamp.query, deleted, call.stamp.session_id)
        held = {record.id for record in kept}
        self._spared.keep(call.stamp.turn_id, {row.id: _excerpt(row, _text(call)) for row in kept})
        found = [record for record in found if record.id not in held]
        repeats = [] if left_out else [row for row in extra if row[0].id not in held]
        if not found and not repeats:
            excerpts = {record.id: _excerpt(record, _text(call)) for record in kept}
            self._kept.keep(call.stamp.turn_id, excerpts)
            return KEPT_ALL, None
        listed = [*found, *(record for record, _, _ in repeats)]
        lines = [f"- {_excerpt(record, _text(call))}" for record in found]
        for form in dict.fromkeys(form for _, form, _ in repeats):
            lines.append(f"Listed because they also hold {form}:")
            lines.extend(
                f"- {_excerpt(record, own)}" for record, held, own in repeats if held == form
            )
        if left_out:
            lines.append(LEFT_OUT_LINE)
        if kept:
            lines.extend([KEPT_LINE, *(f"- {_excerpt(record, _text(call))}" for record in kept)])
        card = "\n".join(
            [f"Deletes for good, with no undo, these {len(listed)} remembered exchanges:", *lines]
        )
        chosen = _Chosen(
            tuple(record.id for record in listed),
            tuple(record.text for record in listed),
            left_out,
            frozenset(held),
        )
        return chosen, card

    def _result(
        self, call: ToolCall, content: str, *, error: bool = True, holding: int | None = None
    ) -> ToolResult:
        """The call's result: ``content`` as one sentence."""
        return ToolResult(
            call_id=call.id,
            content=f"{content}.",
            is_error=error,
            trust=Trust.TRUSTED,
            matched_nothing=content == NONE_FOUND,
            numbers_left=None if holding is None else holding > 0,
            kept=self._kept.held(call.stamp.turn_id),
            spared=self._spared.held(call.stamp.turn_id),
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delete exactly the memories the card listed, then say whether any still match."""
        shown = self._shown.pop(call.id, None)
        if shown is None:
            return self._result(call, "nothing was forgotten: no card listed what to delete")
        if isinstance(shown, str):
            return self._result(call, shown, error=shown not in (NONE_FOUND, ALREADY_DELETED))
        try:
            removed = await self._store.delete_ids(shown.ids)
            turn = call.stamp.turn_id
            self._kept.drop(turn, shown.ids)
            self._spared.drop(turn, shown.ids)
            for ledger, texts in (
                (self._deleted_turns, (*shown.texts, _text(call))),
                (self._deleted_rows, shown.texts),
            ):
                ledger[turn] = (*ledger.get(turn, ()), *texts)
                while len(ledger) > _PENDING_CALLS:
                    del ledger[next(iter(ledger))]
            left = [record for record in await self._found(call) if record.id not in shown.kept]
            holding = 0 if left or shown.left_out else await self._holding(call)
        except MemoryStoreError as err:
            return self._result(call, f"the memory store failed during the forget: {err}")
        if left:
            said = outlasted(removed, len(left))
        elif shown.left_out:
            said = unlisted(removed)
        else:
            said = forgot(removed, holding, len(shown.kept))
        error = bool(left) or shown.left_out
        result = self._result(call, said, error=error, holding=None if error else holding)
        return replace(result, forgot=removed)
